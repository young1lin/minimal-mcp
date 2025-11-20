import httpx
import os
import json
import asyncio
import re
from pathlib import Path
from typing import Any
from dotenv import load_dotenv
import sys
import time

# 添加父目录到路径，以便导入 dto
sys.path.insert(0, str(Path(__file__).parent.parent))
from dto import (
    InitializeJSONRPCRequest,
    InitializeJSONRPCResult,
    ListToolsJSONRPCRequest,
    ListToolsJSONRPCResult,
    ToolDefinition,
    CallToolJSONRPCRequest,
    CallToolJSONRPCResult,
    JSONRPCResult,
)

load_dotenv()

api_key = os.getenv("DEEPSEEK_API_KEY")
if not api_key:
    raise ValueError("DEEPSEEK_API_KEY not found in .env file")

LLM_URL = "https://api.deepseek.com/chat/completions"
LLM_MODEL = "deepseek-chat"
MAX_ROUNDS = 10  # 最多保存10轮对话

BASE_SYSTEM_PROMPT = """
你是D-Cline，是一个优秀的Agent，你精通软件工程，精通各种编程语言、框架、设计模式以及代码的最佳实践。

===
你有一系列的工具可以使用，你每个消息可以使用一个工具，并且会接收到用户响应调用工具的结果，在调用工具前，你必须 thinking step by step。

# 输出格式要求

你的回复必须严格遵循以下 XML 格式：

**第一步：思考过程**
首先，你必须使用 `<thinking></thinking>` 标签包裹你的思考过程，格式如下：

<thinking>
[在这里详细说明你的思考过程，包括：
- 分析用户的需求
- 确定需要使用的工具
- 说明为什么选择这个工具
- 准备工具调用所需的参数]
</thinking>

**第二步：工具调用或最终答案**
在思考过程之后，你可以选择：
1. 调用工具获取更多信息
2. 使用 final_answer 工具返回最终答案

**重要**：
1. 思考过程必须使用 `<thinking></thinking>` 标签包裹
2. 思考过程和工具调用必须分开展示，先思考后调用
3. 所有 XML 标签必须正确闭合
4. 当你已经收集到足够的信息可以回答用户问题时，必须使用 final_answer 工具

# 工具使用格式

工具调用使用 XML 格式，XML 格式必须和下面一致。

<tool_name>
<parameter1_name>value1</parameter1_name>
<parameter2_name>value2</parameter2_name>
...
</tool_name>

样例1：
<read_file>
<path>src/main.js</path>
<task_progress>Checklist here (optional)</task_progress>
</read_file>

样例2：
<final_answer>
<answer>这是我的最终答案，已经完成了用户的所有要求。</answer>
</final_answer>

# Tools
你将有以下工具可以调用

## ls
描述：列出目录内容
参数：
- path：目录路径
使用：

<ls>
<path>目录路径</path>
</ls>

## read_file
描述：读取文件内容
参数：
- path：文件路径
- task_progress：任务进度（可选）
使用：

<read_file>
<path>文件路径</path>
<task_progress>任务进度（可选）</task_progress>
</read_file>

## append_file
描述：追加文件内容
参数：
- path：文件路径
- content：文件内容
使用：

<append_file>
<path>文件路径</path>
<content>文件内容</content>
</append_file>

## delete_file
描述：删除文件
参数：
- path：文件路径
使用：

<delete_file>
<path>文件路径</path>
</delete_file>

## final_answer
描述：当你已经完成任务或收集到足够信息回答用户问题时，使用此工具返回最终答案
参数：
- answer：你的最终答案内容
使用：

<final_answer>
<answer>你的最终答案</answer>
</final_answer>

**重要**: 当你完成了用户的任务或者已经有足够的信息回答用户问题时，你必须调用 final_answer 工具。不要重复调用其他工具。

# 使用 MCP tool
描述：请求使用由连接的 MCP 服务器提供的工具。每个 MCP 服务器可以提供多个具有不同功能的工具。工具具有定义的输入模式，用于指定必需和可选参数。
参数：
- server_name: (必需) 提供工具的 MCP 服务器名称
- tool_name: (必需) 要执行的工具名称
- arguments: (必需) 包含工具输入参数的 JSON 对象，遵循工具的输入模式
用法：

<use_mcp_tool>
<server_name>server name here</server_name>
<tool_name>tool name here</tool_name>
<arguments>
{
  "param1": "value1",
  "param2": "value2"
}
</arguments>
</use_mcp_tool>

完整输出格式示例（包含思考过程和工具调用）：

<thinking>
用户询问 redis 查询 key user:token。我需要使用 redis-server 的 get_value 工具来获取值。
</thinking>

<use_mcp_tool>
<server_name>redis-server</server_name>
<tool_name>get_value</tool_name>
<arguments>
{
  "key": "user:token"
}
</arguments>
</use_mcp_tool>

使用 MCP Tool 样例1：
<use_mcp_tool>
<server_name>redis-server</server_name>
<tool_name>get_value</tool_name>
<arguments>
{
  "key": "user:token"
}
</arguments>
</use_mcp_tool>


使用 MCP Tool 样例2：
<use_mcp_tool>
<server_name>github.com/modelcontextprotocol/servers/tree/main/src/github</server_name>
<tool_name>create_issue</tool_name>
<arguments>
{
  "owner": "octocat",
  "repo": "hello-world",
  "title": "Found a bug",
  "body": "I'm having a problem with this.",
  "labels": ["bug", "help wanted"],
  "assignees": ["octocat"]
}
</arguments>
</use_mcp_tool>
===
# MCP Server
{MCP_SERVERS_SECTION}
"""


class MCPClient:
    """MCP 客户端，用于连接 MCP 服务器并获取工具列表"""

    def __init__(
        self,
        server_name: str,
        command: str,
        args: list[str],
        env: dict[str, str] | None = None,
    ):
        self.server_name = server_name
        self.command = command
        self.args = args
        self.env = env or {}
        self.process: asyncio.subprocess.Process | None = None
        self.tools: list[ToolDefinition] = []

    async def connect(self):
        """连接到 MCP 服务器并初始化"""
        # 准备环境变量
        env = os.environ.copy()
        env.update(self.env)
        # 在 Windows 上强制使用 UTF-8 编码
        if sys.platform == "win32":
            env["PYTHONIOENCODING"] = "utf-8"

        # 使用异步 subprocess
        self.process = await asyncio.create_subprocess_exec(
            self.command,
            *self.args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )

        # 发送 initialize 请求
        init_request = InitializeJSONRPCRequest()
        request_json = init_request.to_json() + "\n"
        self.process.stdin.write(request_json.encode("utf-8"))
        await self.process.stdin.drain()

        # 读取 initialize 响应
        response_line_bytes = await self.process.stdout.readline()
        if response_line_bytes:
            try:
                response_line = response_line_bytes.decode("utf-8").strip()
            except UnicodeDecodeError:
                # 如果 UTF-8 解码失败，尝试使用错误处理
                response_line = response_line_bytes.decode(
                    "utf-8", errors="replace"
                ).strip()
            init_response = InitializeJSONRPCResult.from_json(response_line)
            if init_response.is_error:
                raise Exception(f"Initialize failed: {init_response.error}")

        # 发送 initialized 通知
        initialized_notification = (
            json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n"
        )
        self.process.stdin.write(initialized_notification.encode("utf-8"))
        await self.process.stdin.drain()

        # 获取工具列表
        await self.list_tools()

    async def list_tools(self):
        """获取工具列表"""
        list_request = ListToolsJSONRPCRequest(id="list_tools")
        request_json = list_request.to_json() + "\n"
        self.process.stdin.write(request_json.encode("utf-8"))
        await self.process.stdin.drain()

        # 读取响应
        response_line_bytes = await self.process.stdout.readline()
        if response_line_bytes:
            try:
                response_line = response_line_bytes.decode("utf-8").strip()
            except UnicodeDecodeError:
                # 如果 UTF-8 解码失败，尝试使用错误处理
                response_line = response_line_bytes.decode(
                    "utf-8", errors="replace"
                ).strip()
            list_response = ListToolsJSONRPCResult.from_json(response_line)
            if list_response.is_error:
                raise Exception(f"List tools failed: {list_response.error}")
            if list_response.result and "tools" in list_response.result:
                tools_data = list_response.result["tools"]
                self.tools = [ToolDefinition(**tool) for tool in tools_data]

    async def call_tool(
        self, tool_name: str, arguments: dict[str, Any] | None = None
    ) -> str:
        """调用工具"""
        call_request = CallToolJSONRPCRequest(name=tool_name, arguments=arguments)
        request_json = call_request.to_json() + "\n"
        self.process.stdin.write(request_json.encode("utf-8"))
        await self.process.stdin.drain()

        # 读取响应
        response_line_bytes = await self.process.stdout.readline()
        if response_line_bytes:
            try:
                response_line = response_line_bytes.decode("utf-8").strip()
            except UnicodeDecodeError:
                # 如果 UTF-8 解码失败，尝试使用错误处理
                response_line = response_line_bytes.decode(
                    "utf-8", errors="replace"
                ).strip()
            call_response = CallToolJSONRPCResult.from_json(response_line)
            if call_response.is_error:
                raise Exception(f"Call tool failed: {call_response.error}")
            if call_response.result and "content" in call_response.result:
                content_list = call_response.result["content"]
                # 提取文本内容
                texts = []
                for item in content_list:
                    if item.get("type") == "text":
                        texts.append(item.get("text", ""))
                return "\n".join(texts)
        return ""

    async def close(self):
        """关闭连接"""
        if self.process:
            self.process.stdin.close()
            await self.process.wait()


def parse_mcp_config(config_path: str) -> dict[str, Any]:
    """解析 mcp.json 配置文件"""
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)
    return config.get("mcpServers", {})


def build_mcp_servers_section(mcp_clients: dict[str, MCPClient]) -> str:
    """构建 MCP 服务器部分的 system prompt"""
    if not mcp_clients:
        return "当前没有可用的 MCP Server。"

    sections = []
    sections.append("现在你有这些 MCP Server 可以调用：\n")

    for server_name, client in mcp_clients.items():
        sections.append(f"## {server_name}")
        if not client.tools:
            sections.append("### 可用工具：无")
        else:
            sections.append("### 可用工具如下")
            for tool in client.tools:
                sections.append(f"- {tool.name}：{tool.description}")
                if tool.inputSchema and tool.inputSchema.properties:
                    sections.append("  输入参数：")
                    required = tool.inputSchema.required or []
                    for param_name, param_prop in tool.inputSchema.properties.items():
                        required_mark = "(必需)" if param_name in required else "(可选)"
                        sections.append(
                            f"    - {param_name}：{param_prop.description} {required_mark}"
                        )
                else:
                    sections.append("  输入参数：无")
                sections.append("")  # 空行分隔

    return "\n".join(sections)


async def initialize_mcp_servers(config_path: str) -> dict[str, MCPClient]:
    """初始化所有 MCP 服务器"""
    config = parse_mcp_config(config_path)
    mcp_clients: dict[str, MCPClient] = {}
    config_dir = Path(config_path).parent

    for server_name, server_config in config.items():
        if server_config.get("type") != "stdio":
            print(f"跳过服务器 {server_name}：仅支持 stdio 类型")
            continue

        command = server_config.get("command")
        args = server_config.get("args", [])
        env = server_config.get("env", {})

        if not command:
            print(f"跳过服务器 {server_name}：缺少 command 配置")
            continue

        # 处理相对路径参数（相对于 config 文件所在目录）
        processed_args = []
        for arg in args:
            # 如果参数看起来像文件路径，尝试解析为相对于 config 目录的路径
            if arg.startswith("..") or (
                not os.path.isabs(arg) and ("/" in arg or "\\" in arg)
            ):
                # 尝试解析为相对于 config 目录的路径
                potential_path = (config_dir / arg).resolve()
                if potential_path.exists():
                    processed_args.append(str(potential_path))
                else:
                    processed_args.append(arg)
            else:
                processed_args.append(arg)

        try:
            client = MCPClient(server_name, command, processed_args, env)
            await client.connect()
            mcp_clients[server_name] = client
            print(f"成功连接 MCP 服务器: {server_name}, 工具数量: {len(client.tools)}")
        except Exception as e:
            print(f"连接 MCP 服务器 {server_name} 失败: {e}")
            import traceback

            traceback.print_exc()

    return mcp_clients


def build_system_prompt(mcp_clients: dict[str, MCPClient]) -> str:
    """动态构建 system prompt"""
    mcp_servers_section = build_mcp_servers_section(mcp_clients)
    print("注入的 MCP Server 及其工具：")
    time.sleep(1)
    for line in mcp_servers_section.splitlines():
        print(line)
        time.sleep(1)
    return BASE_SYSTEM_PROMPT.replace("{MCP_SERVERS_SECTION}", mcp_servers_section)


class ChatBot:

    def __init__(
        self,
        api_key: str,
        system_prompt: str,
        mcp_clients: dict[str, MCPClient] | None = None,
    ):
        self.api_key = api_key
        self.system_prompt = system_prompt
        self.client = httpx.AsyncClient()
        self.mcp_clients = mcp_clients or {}
        # 初始化 message 用于保存相应的对话记录
        self.messages = [{"role": "system", "content": system_prompt}]

    def _limit_messages(self):
        """限制消息数量，最多保留10轮对话（20条消息，不包括system）"""
        # 计算非system消息的数量
        non_system_messages = [msg for msg in self.messages if msg["role"] != "system"]
        max_messages = MAX_ROUNDS * 2  # 每轮包括user和assistant两条消息

        if len(non_system_messages) > max_messages:
            # 保留system消息，然后保留最新的max_messages条非system消息
            system_msg = [msg for msg in self.messages if msg["role"] == "system"]
            self.messages = system_msg + non_system_messages[-max_messages:]

    def _parse_xml_tool(self, content: str):
        """解析 XML 格式的工具调用，返回 (tool_name, params) 或 (None, None)"""
        # 匹配工具调用标签：<tool_name>...</tool_name>
        pattern = r"<(\w+)>(.*?)</\1>"
        matches = re.findall(pattern, content, re.DOTALL)

        for tool_name, tool_content in matches:
            if tool_name in ["read_file", "ls", "final_answer", "use_mcp_tool"]:
                # 解析参数
                params = {}
                param_pattern = r"<(\w+)>(.*?)</\1>"
                param_matches = re.findall(param_pattern, tool_content, re.DOTALL)
                for param_name, param_value in param_matches:
                    params[param_name] = param_value.strip()

                return tool_name, params

        return None, None

    async def _execute_tool(self, tool_name: str, params: dict):
        """执行工具调用，返回 (result, is_final)"""
        if tool_name == "final_answer":
            answer = params.get("answer", "")
            return answer, True  # 返回最终答案，标记为结束

        if tool_name == "read_file":
            path = params.get("path", "")
            if path:
                try:
                    result = await read_file(path)
                    return f"文件内容：\n{result}", False
                except Exception as e:
                    return f"读取文件失败：{str(e)}", False

        elif tool_name == "ls":
            path = params.get("path", ".")
            try:
                items = os.listdir(path)
                result = "\n".join(items)
                return f"\n{result}", False
            except Exception as e:
                return f"列出目录失败：{str(e)}", False

        elif tool_name == "use_mcp_tool":
            server_name = params.get("server_name", "").strip()
            tool_name_mcp = params.get("tool_name", "").strip()
            arguments_str = params.get("arguments", "{}").strip()

            if not server_name:
                return "错误：缺少 server_name 参数", False
            if not tool_name_mcp:
                return "错误：缺少 tool_name 参数", False

            if server_name not in self.mcp_clients:
                return f"错误：找不到 MCP 服务器 '{server_name}'", False

            try:
                # 解析 arguments JSON
                arguments = json.loads(arguments_str) if arguments_str else {}
            except json.JSONDecodeError as e:
                return f"错误：arguments 参数不是有效的 JSON: {e}", False

            try:
                mcp_client = self.mcp_clients[server_name]
                result = await mcp_client.call_tool(tool_name_mcp, arguments)
                return result, False
            except Exception as e:
                return f"调用 MCP 工具失败：{str(e)}", False

        return None, False

    def _extract_tool_xml(self, content: str):
        """提取工具调用的完整XML内容"""
        # 匹配工具调用标签：<tool_name>...</tool_name>
        pattern = r"(<(\w+)>.*?</\2>)"
        matches = re.findall(pattern, content, re.DOTALL)

        for full_xml, tool_name in matches:
            if tool_name in ["read_file", "ls", "final_answer", "use_mcp_tool"]:
                return full_xml
        return None

    def _process_sse_line(self, line: str):
        """处理单行SSE数据，返回内容"""
        if not line.strip() or not line.startswith("data: "):
            return None

        data_str = line[6:]  # 移除 "data: " 前缀
        if data_str == "[DONE]":
            return None

        try:
            data = json.loads(data_str)
            choices = data.get("choices", [])
            if choices:
                delta = choices[0].get("delta", {})
                return delta.get("content", "")
        except json.JSONDecodeError:
            pass

        return None

    async def _handle_tool_call(self, content: str, tool_name: str, params: dict):
        """处理工具调用：输出XML、执行工具、添加结果到历史
        返回 (是否是最终答案, 最终答案内容)
        """
        # 提取完整的工具调用XML并输出
        tool_xml = self._extract_tool_xml(content)
        if tool_xml:
            yield f"\n\n[tool_call]\n{tool_xml}\n\n"

        # 执行工具
        tool_result, is_final = await self._execute_tool(tool_name, params)

        if is_final:
            # 如果是最终答案，输出并返回
            yield f"[final_answer]\n{tool_result}\n"
            yield (True, tool_result)  # 标记为最终答案
        elif tool_result:
            # 输出工具执行结果
            yield f"[tool_result]\n{tool_result}\n\n"
            # 将工具结果添加到对话历史
            self.messages.append(
                {
                    "role": "user",
                    "content": f"工具 {tool_name} 的执行结果：{tool_result}",
                }
            )
            self._limit_messages()
            yield (False, None)  # 标记为普通工具调用

    async def _process_stream_response(self):
        """处理流式响应，返回异步生成器
        返回: (content, is_final, final_answer)
        """
        full_content = ""
        buffer = ""
        tool_executed = False
        is_final = False
        final_answer = None

        async with self.client.stream(
            "POST",
            url=LLM_URL,
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={"model": LLM_MODEL, "messages": self.messages, "stream": True},
        ) as response:
            response.raise_for_status()

            async for line in response.aiter_lines():
                content = self._process_sse_line(line)
                if content is None:
                    continue

                full_content += content
                buffer += content
                yield content

                # 流式检测完整的工具调用
                if not tool_executed:
                    tool_name, params = self._parse_xml_tool(buffer)
                    if tool_name and params:
                        tool_executed = True
                        # 先将assistant的回复添加到消息历史
                        if full_content:
                            self.messages.append(
                                {
                                    "role": "assistant",
                                    "content": full_content,
                                }
                            )
                            self._limit_messages()

                        # 处理工具调用
                        async for output in self._handle_tool_call(
                            buffer, tool_name, params
                        ):
                            if isinstance(output, tuple):
                                # 这是最终答案标记，通过yield传递
                                yield output
                                return  # 结束生成器
                            else:
                                yield output

                        # 检测到工具调用但不是final_answer，直接返回让生成器结束
                        # chat方法会继续循环处理工具结果
                        return

        # 将完整的回复添加到消息历史中（如果还没有添加）
        if full_content and not tool_executed:
            self.messages.append({"role": "assistant", "content": full_content})
            self._limit_messages()

            # 最后再检查一次是否有工具调用（防止流式解析遗漏）
            tool_name, params = self._parse_xml_tool(full_content)
            if tool_name and params:
                async for output in self._handle_tool_call(
                    full_content, tool_name, params
                ):
                    if isinstance(output, tuple):
                        # 这是最终答案标记，通过yield传递
                        yield output
                        return  # 结束生成器
                    else:
                        yield output

    async def chat(self, message: str):
        """流式对话，返回异步生成器"""
        self.messages.append({"role": "user", "content": message})
        self._limit_messages()

        max_iterations = 20  # 防止无限循环
        iteration = 0

        while iteration < max_iterations:
            iteration += 1

            # 处理流式响应
            is_final = False
            final_answer = None

            async for content in self._process_stream_response():
                if isinstance(content, tuple):
                    # 这是返回的状态标记
                    is_final, final_answer = content
                else:
                    # 这是实际的输出内容
                    yield content

            # 如果收到 final_answer，结束对话
            if is_final:
                break

            # 检查是否有新的工具调用需要处理
            # 如果消息历史中最后一条是assistant的回复，说明没有工具调用，应该结束
            if self.messages[-1]["role"] == "assistant":
                break


async def read_file(path: str) -> str:
    """读取文件内容"""
    with open(path, "r", encoding="utf-8") as file:
        return file.read()


async def main():
    # 获取 mcp.json 路径
    config_path = Path(__file__).parent / "mcp.json"

    # 初始化 MCP 服务器
    print("正在初始化 MCP 服务器...")
    mcp_clients = await initialize_mcp_servers(str(config_path))

    # 动态构建 system prompt
    system_prompt = build_system_prompt(mcp_clients)

    print(f"{'='*50}")

    # 创建 ChatBot
    chatbot = ChatBot(api_key, system_prompt, mcp_clients)

    try:
        async for content in chatbot.chat("北京天气如何"):
            print(content, end="", flush=True)
    finally:
        # 关闭所有 MCP 连接
        for client in mcp_clients.values():
            await client.close()


if __name__ == "__main__":
    asyncio.run(main())
