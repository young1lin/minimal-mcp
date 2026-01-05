import httpx
import os
import json
import asyncio
from pathlib import Path
from typing import Any
from dotenv import load_dotenv
import sys
import shutil

# ANSI 颜色代码
GREEN = "\033[32m"
RESET = "\033[0m"
GREEN_CIRCLE = f"{GREEN}●{RESET}"

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
)

load_dotenv()

api_key = os.getenv("DEEPSEEK_API_KEY")
if not api_key:
    raise ValueError("DEEPSEEK_API_KEY not found in .env file")

LLM_URL = "https://api.deepseek.com/chat/completions"
LLM_MODEL = "deepseek-reasoner"
MAX_ROUNDS = 200


# 删除重复的函数定义，使用下面带 server_name 参数的版本


class MCPClient:
    """MCP 客户端（复用之前的实现）"""

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
        self._roots: list[dict[str, str]] = []  # 保存 roots 列表

    async def _read_stderr(self):
        """读取并打印 stderr 输出"""
        if not self.process or not self.process.stderr:
            return

        try:
            while True:
                line = await self.process.stderr.readline()
                if not line:
                    break
                error_msg = line.decode("utf-8", errors="replace").strip()
                if error_msg:
                    print(f"  [{self.server_name} stderr] {error_msg}")
        except Exception:
            pass

    async def _handle_server_request(self, request: dict):
        """处理单个服务器请求"""
        method = request.get("method")
        request_id = request.get("id")

        if method == "roots/list":
            # 响应 roots/list 请求
            response = {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {"roots": self._roots},
            }
            response_json = json.dumps(response) + "\n"
            if self.process and self.process.stdin:
                self.process.stdin.write(response_json.encode("utf-8"))
                await self.process.stdin.drain()
                print(
                    f"  [{self.server_name}] 响应 roots/list: {len(self._roots)} 个根目录"
                )

    async def connect(self):
        """连接到 MCP 服务器并初始化"""
        # 准备环境变量
        env = os.environ.copy()
        env.update(self.env)
        # 在 Windows 上强制使用 UTF-8 编码
        if sys.platform == "win32":
            env["PYTHONIOENCODING"] = "utf-8"

        # 在 Windows 上处理 Node.js 命令（npx, npm, node）
        command = self.command
        if sys.platform == "win32":
            # Node.js 相关命令在 Windows 上通常是 .cmd 文件
            node_commands = ["npx", "npm", "node"]
            if command in node_commands:
                # 尝试查找命令的实际路径
                cmd_path = shutil.which(f"{command}.cmd")
                if cmd_path:
                    command = cmd_path
                elif shutil.which(command):
                    # 如果找不到 .cmd，使用原始命令（可能已经配置好 PATH）
                    command = shutil.which(command) or command
                else:
                    # 如果都找不到，尝试直接使用 .cmd 扩展名
                    command = f"{command}.cmd"

        # 使用异步 subprocess
        self.process = await asyncio.create_subprocess_exec(
            command,
            *self.args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )

        # 从 args 中提取路径并保存为 roots
        import pathlib

        for arg in self.args:
            # 跳过选项参数（以 - 开头）和非路径参数
            if arg.startswith("-"):
                continue
            # 检查是否看起来像路径
            if "/" in arg or "\\" in arg or (len(arg) > 1 and arg[1] == ":"):
                try:
                    path = pathlib.Path(arg).resolve()
                    if path.exists():
                        uri = path.as_uri()
                        self._roots.append({"uri": uri, "name": path.name})
                except Exception:
                    pass

        # 启动任务来读取 stderr
        asyncio.create_task(self._read_stderr())

        # 发送 initialize 请求
        init_request = InitializeJSONRPCRequest()
        request_json = init_request.to_json() + "\n"
        self.process.stdin.write(request_json.encode("utf-8"))
        await self.process.stdin.drain()

        # 读取 initialize 响应
        init_response_dict = await self._read_response()
        if init_response_dict:
            init_response = InitializeJSONRPCResult.model_validate(init_response_dict)
            if init_response.is_error:
                raise Exception(f"Initialize failed: {init_response.error}")

        # 发送 initialized 通知
        initialized_notification = (
            json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n"
        )
        self.process.stdin.write(initialized_notification.encode("utf-8"))
        await self.process.stdin.drain()

        # 等待一小段时间让服务器处理 initialized 通知
        await asyncio.sleep(0.1)

        # 获取工具列表
        await self.list_tools()

    async def _read_response(self, expected_id: str | None = None) -> dict | None:
        """读取响应，处理服务器请求"""
        while True:
            response_line_bytes = await self.process.stdout.readline()
            if not response_line_bytes:
                return None

            response_line = response_line_bytes.decode(
                "utf-8", errors="replace"
            ).strip()
            if not response_line:
                continue

            try:
                msg = json.loads(response_line)

                # 如果是服务器发来的请求（有 method 且有 id），处理它
                if "method" in msg and "id" in msg:
                    await self._handle_server_request(msg)
                    continue  # 继续等待真正的响应

                # 如果是响应，返回它
                if expected_id is None or msg.get("id") == expected_id:
                    return msg

            except json.JSONDecodeError:
                continue

    async def list_tools(self):
        """获取工具列表"""
        list_request = ListToolsJSONRPCRequest(id="list_tools")
        request_json = list_request.to_json() + "\n"
        self.process.stdin.write(request_json.encode("utf-8"))
        await self.process.stdin.drain()

        response = await self._read_response(expected_id="list_tools")
        if not response:
            print(f"  [{self.server_name}] 警告: list_tools 响应为空")
            return

        try:
            list_response = ListToolsJSONRPCResult.model_validate(response)
        except Exception as e:
            print(f"  [{self.server_name}] 解析 list_tools 响应失败: {e}")
            print(f"  [{self.server_name}] 原始响应: {str(response)[:200]}")
            return

        if list_response.is_error:
            raise Exception(f"List tools failed: {list_response.error}")
        if list_response.result and "tools" in list_response.result:
            tools_data = list_response.result["tools"]
            self.tools = [ToolDefinition(**tool) for tool in tools_data]
        else:
            print(f"  [{self.server_name}] 响应中没有 tools 字段")
            print(f"  [{self.server_name}] result 内容: {list_response.result}")

    async def call_tool(
        self, tool_name: str, arguments: dict[str, Any] | None = None
    ) -> str:
        """调用工具"""
        call_request = CallToolJSONRPCRequest(name=tool_name, arguments=arguments)
        request_json = call_request.to_json() + "\n"
        self.process.stdin.write(request_json.encode("utf-8"))
        await self.process.stdin.drain()

        response = await self._read_response()
        if response:
            call_response = CallToolJSONRPCResult.model_validate(response)
            if call_response.is_error:
                raise Exception(f"Call tool failed: {call_response.error}")
            if call_response.result and "content" in call_response.result:
                content_list = call_response.result["content"]
                texts = []
                for item in content_list:
                    if item.get("type") == "text":
                        texts.append(item.get("text", ""))
                return "\n".join(texts)
        return ""

    async def close(self):
        """关闭连接"""
        if self.process:
            try:
                # 关闭 stdin
                if self.process.stdin:
                    self.process.stdin.close()

                # 尝试等待进程结束（带超时）
                try:
                    await asyncio.wait_for(self.process.wait(), timeout=2.0)
                except asyncio.TimeoutError:
                    # 超时后强制终止
                    self.process.terminate()
                    try:
                        await asyncio.wait_for(self.process.wait(), timeout=1.0)
                    except asyncio.TimeoutError:
                        # 如果还不退出，强制杀死
                        self.process.kill()
                        await self.process.wait()
            except Exception:
                # 忽略所有关闭时的异常
                pass


def tool_definition_to_function(tool: ToolDefinition, server_name: str) -> dict:
    """将 MCP ToolDefinition 转换为 Function Calling 格式

    工具名称格式: {server_name}__{tool_name}
    这样可以区分不同 MCP Server 的同名工具
    """
    # 使用 server_name__tool_name 作为函数名，避免冲突
    # 注意：函数名只能包含 a-zA-Z0-9_-，所以用双下划线连接
    safe_server_name = server_name.replace("-", "_").replace(":", "_")
    function_name = f"{safe_server_name}__{tool.name}"

    # 确保 description 不为空
    description = tool.description or f"Tool from {server_name}"
    if server_name:
        description = f"[{server_name}] {description}"

    function_def = {
        "type": "function",
        "function": {
            "name": function_name,
            "description": description,
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    }

    # 转换参数定义
    if tool.inputSchema and tool.inputSchema.properties:
        for param_name, param_prop in tool.inputSchema.properties.items():
            function_def["function"]["parameters"]["properties"][param_name] = {
                "type": param_prop.type or "string",
                "description": param_prop.description or f"Parameter {param_name}",
            }

        # 添加必需参数
        if tool.inputSchema.required:
            function_def["function"]["parameters"][
                "required"
            ] = tool.inputSchema.required

    return function_def


class FunctionCallingChatBot:
    """使用原生 Function Calling 的 ChatBot"""

    def __init__(
        self,
        api_key: str,
        mcp_clients: dict[str, MCPClient] | None = None,
    ):
        self.api_key = api_key
        self.client = httpx.AsyncClient()
        self.mcp_clients = mcp_clients or {}

        # 构建 Function Calling 工具列表
        self.tools = []
        self.tool_mapping = {}  # function_name -> (server_name, tool_name)

        for server_name, mcp_client in self.mcp_clients.items():
            for tool in mcp_client.tools:
                function_def = tool_definition_to_function(tool, server_name)
                self.tools.append(function_def)

                # 建立映射关系
                function_name = function_def["function"]["name"]
                self.tool_mapping[function_name] = (server_name, tool.name)

        # 初始化消息历史
        self.messages = [
            {
                "role": "system",
                "content": "你是一个优秀的 AI 助手，可以使用多种工具来帮助用户完成任务。",
            }
        ]

    def _limit_messages(self):
        """限制消息数量，确保不会单独保留 tool 消息而删除其对应的 assistant 消息"""
        system_messages = [msg for msg in self.messages if msg["role"] == "system"]
        other_messages = [msg for msg in self.messages if msg["role"] != "system"]

        if len(other_messages) <= MAX_ROUNDS * 2:
            return

        # 从后往前保留完整的对话轮次
        # 一轮可能包含：assistant(tool_calls) + tool(response)
        kept_messages = []
        i = len(other_messages) - 1

        while len(kept_messages) < MAX_ROUNDS * 2 and i >= 0:
            msg = other_messages[i]

            if msg["role"] == "tool":
                # 如果是 tool 消息，需要找到对应的 assistant 消息
                if (
                    i > 0
                    and other_messages[i - 1].get("role") == "assistant"
                    and "tool_calls" in other_messages[i - 1]
                ):
                    # 把 pair 一起加入（注意是 prepend，所以顺序要对）
                    kept_messages.insert(0, other_messages[i - 1])
                    kept_messages.insert(1, msg)
                    i -= 1  # 跳过已处理的 assistant 消息
                else:
                    # 没有对应的 assistant，单独保留（但可能仍会被后面的逻辑移除）
                    kept_messages.insert(0, msg)
            elif msg["role"] == "assistant" and "tool_calls" in msg:
                # 如果有对应的 tool 消息，需要一起保留
                if (
                    i + 1 < len(other_messages)
                    and other_messages[i + 1]["role"] == "tool"
                ):
                    # 把 pair 一起加入
                    kept_messages.insert(0, other_messages[i + 1])
                    kept_messages.insert(0, msg)
                    i += 1  # 跳过已处理的 tool 消息
                else:
                    kept_messages.insert(0, msg)
            else:
                kept_messages.insert(0, msg)

            i -= 1

        # 如果还是超了，从头部开始截断
        if len(kept_messages) > MAX_ROUNDS * 2:
            kept_messages = kept_messages[-MAX_ROUNDS * 2 :]

        self.messages = system_messages + kept_messages

    async def _call_llm_stream(self):
        """流式调用 LLM，yield 输出内容，处理 tool_calls"""
        request_data = {
            "model": LLM_MODEL,
            "messages": self.messages,
            "tools": self.tools,
            "stream": True,
        }

        # 用于收集完整响应
        full_content = ""
        full_reasoning_content = ""  # 收集 reasoning content
        thinking_prefix = "🤔 "  # 推理内容前缀，输出后设为 None
        tool_calls_data = []
        finish_reason = None

        async with self.client.stream(
            "POST",
            LLM_URL,
            headers={"Authorization": f"Bearer {self.api_key}"},
            json=request_data,
            timeout=60.0,
        ) as response:
            if response.status_code != 200:
                error_text = await response.aread()
                print(f"\n[错误] API 返回状态码: {response.status_code}")
                print(f"[错误] 响应内容: {error_text.decode('utf-8')}")
                response.raise_for_status()

            async for line in response.aiter_lines():
                if not line.strip() or not line.startswith("data: "):
                    continue

                data_str = line[6:]
                if data_str == "[DONE]":
                    break

                try:
                    data = json.loads(data_str)
                    choice = data.get("choices", [{}])[0]
                    delta = choice.get("delta", {})
                    finish_reason = choice.get("finish_reason")

                    # 处理 reasoning_content（推理模型的 thinking 过程）
                    if "reasoning_content" in delta and delta["reasoning_content"]:
                        reasoning_content = delta["reasoning_content"]
                        full_reasoning_content += reasoning_content
                        # 第一次：输出换行、打开灰色颜色、前缀
                        if thinking_prefix:
                            yield f"\n\033[90m{thinking_prefix}{reasoning_content}"
                            thinking_prefix = None  # 标记前缀已输出
                        else:
                            yield reasoning_content  # 后续直接追加内容

                    # 处理普通内容（开始输出正式回答时，关闭 thinking 颜色）
                    if "content" in delta and delta["content"]:
                        # 如果之前有 thinking 内容，先关闭灰色颜色
                        if full_reasoning_content and not full_content:
                            yield "\033[0m"
                        content = delta["content"]
                        full_content += content
                        # 第一个内容块前面加换行和绿色圆圈
                        if not full_content.replace(content, ""):
                            yield f"\n{GREEN_CIRCLE} "
                        yield content  # 流式输出

                    # 处理 tool_calls
                    if "tool_calls" in delta:
                        for tc_delta in delta["tool_calls"]:
                            index = tc_delta.get("index", 0)
                            # 确保列表足够长
                            while len(tool_calls_data) <= index:
                                tool_calls_data.append(
                                    {
                                        "id": "",
                                        "type": "function",
                                        "function": {"name": "", "arguments": ""},
                                    }
                                )

                            if "id" in tc_delta:
                                tool_calls_data[index]["id"] = tc_delta["id"]
                            if "function" in tc_delta:
                                if "name" in tc_delta["function"]:
                                    tool_calls_data[index]["function"]["name"] = (
                                        tc_delta["function"]["name"]
                                    )
                                if "arguments" in tc_delta["function"]:
                                    tool_calls_data[index]["function"][
                                        "arguments"
                                    ] += tc_delta["function"]["arguments"]

                except json.JSONDecodeError:
                    continue

        # 构建完整的 message 对象
        message_obj = {"role": "assistant"}
        if full_reasoning_content:
            message_obj["reasoning_content"] = full_reasoning_content
        if full_content:
            message_obj["content"] = full_content
        if tool_calls_data:
            message_obj["tool_calls"] = tool_calls_data

        # 添加到消息历史
        self.messages.append(message_obj)

        # 如果有 tool_calls，执行工具
        if tool_calls_data and finish_reason == "tool_calls":
            # 输出每个工具调用的详细信息
            for tc in tool_calls_data:
                function_name = tc["function"]["name"]
                arguments = tc["function"]["arguments"]

                # 从 tool_mapping 获取原始的 tool_name
                if function_name in self.tool_mapping:
                    _, tool_name = self.tool_mapping[function_name]
                else:
                    tool_name = function_name

                # 格式化参数
                if arguments:
                    try:
                        args_json = (
                            json.loads(arguments)
                            if isinstance(arguments, str)
                            else arguments
                        )
                        args_str = json.dumps(args_json, ensure_ascii=False)
                        yield f"\n{GREEN_CIRCLE} MCPTool({tool_name}({args_str}))\n"
                    except:
                        yield f"\n{GREEN_CIRCLE} MCPTool({tool_name}({arguments}))\n"
                else:
                    yield f"\n{GREEN_CIRCLE} MCPTool({tool_name}())\n"

            # 并行执行工具
            tool_results = await self._execute_tool_calls(tool_calls_data)

            # 打印工具结果（带缩进和 ⎿ 符号）
            for i, tr in enumerate(tool_results):
                yield f"    ⎿ {tr['content']}\n"

            # 添加工具结果到消息历史
            self.messages.extend(tool_results)
            self._limit_messages()

            # 标记需要继续对话
            yield "__CONTINUE__"

    async def _execute_tool_calls(self, tool_calls: list[dict]) -> list[dict]:
        """并行执行多个工具调用"""

        async def execute_single_tool(tool_call: dict) -> dict:
            """执行单个工具调用"""
            function_name = tool_call["function"]["name"]
            arguments_str = tool_call["function"]["arguments"]

            try:
                arguments = json.loads(arguments_str) if arguments_str else {}
            except json.JSONDecodeError:
                return {
                    "tool_call_id": tool_call["id"],
                    "role": "tool",
                    "content": f"错误：参数不是有效的 JSON: {arguments_str}",
                }

            # 从函数名解析 server_name 和 tool_name
            # 格式: {safe_server_name}__{tool_name}
            if "__" not in function_name:
                return {
                    "tool_call_id": tool_call["id"],
                    "role": "tool",
                    "content": f"错误：函数名格式错误 {function_name}",
                }

            # 查找对应的 MCP Server 和工具
            if function_name not in self.tool_mapping:
                return {
                    "tool_call_id": tool_call["id"],
                    "role": "tool",
                    "content": f"错误：未找到工具 {function_name}",
                }

            server_name, tool_name = self.tool_mapping[function_name]
            mcp_client = self.mcp_clients.get(server_name)

            if not mcp_client:
                return {
                    "tool_call_id": tool_call["id"],
                    "role": "tool",
                    "content": f"错误：MCP Server {server_name} 未连接",
                }

            try:
                # 调用 MCP 工具
                result = await mcp_client.call_tool(tool_name, arguments)
                return {
                    "tool_call_id": tool_call["id"],
                    "role": "tool",
                    "content": result,
                }
            except Exception as e:
                return {
                    "tool_call_id": tool_call["id"],
                    "role": "tool",
                    "content": f"错误：工具执行失败 - {str(e)}",
                }

        # 并行执行所有工具调用
        tasks = [execute_single_tool(tc) for tc in tool_calls]
        results = await asyncio.gather(*tasks)
        return results

    async def chat(self, message: str):
        """流式对话，返回异步生成器"""
        # 添加用户消息
        self.messages.append({"role": "user", "content": message})
        self._limit_messages()

        max_iterations = 200
        iteration = 0

        while iteration < max_iterations:
            iteration += 1
            should_continue = False

            # 流式调用 LLM
            async for chunk in self._call_llm_stream():
                if chunk == "__CONTINUE__":
                    should_continue = True
                else:
                    yield chunk

            # 如果没有收到继续标记，说明对话结束
            if not should_continue:
                break


def parse_mcp_config(config_path: str) -> dict[str, Any]:
    """解析 mcp.json 配置文件"""
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)
    return config.get("mcpServers", {})


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

        # 处理相对路径
        processed_args = []
        for arg in args:
            if arg.startswith("..") or (
                not os.path.isabs(arg) and ("/" in arg or "\\" in arg)
            ):
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
            print(
                f"✓ 成功连接 MCP 服务器: {server_name}, 工具数量: {len(client.tools)}"
            )
        except Exception as e:
            print(f"✗ 连接 MCP 服务器 {server_name} 失败: {e}")

    return mcp_clients


async def main():
    """主函数"""
    # 获取 mcp.json 路径
    config_path = Path(__file__).parent / "mcp.json"

    # 初始化 MCP 服务器
    print("正在初始化 MCP 服务器...\n")
    mcp_clients = await initialize_mcp_servers(str(config_path))

    if not mcp_clients:
        print("没有可用的 MCP 服务器，退出。")
        return

    # 创建 ChatBot
    chatbot = FunctionCallingChatBot(api_key, mcp_clients)

    print(f"\n{'='*60}")
    print(f"已加载 {len(chatbot.tools)} 个工具:")
    for tool in chatbot.tools:
        print(f"  - {tool['function']['name']}: {tool['function']['description']}")
    print(f"{'='*60}\n")

    try:
        # 交互式对话
        while True:
            user_input = input("> ").strip()

            if user_input.lower() in ["exit", "quit", "退出"]:
                print("\n再见！")
                break

            if not user_input:
                continue

            async for chunk in chatbot.chat(user_input):
                print(chunk, end="", flush=True)
            print()  # 换行

    except KeyboardInterrupt:
        print("\n\n程序被用户中断")
    finally:
        # 关闭所有 MCP 连接
        print("\n正在关闭 MCP 连接...")
        close_tasks = [client.close() for client in mcp_clients.values()]
        if close_tasks:
            await asyncio.gather(*close_tasks, return_exceptions=True)
        print("已关闭所有连接")


if __name__ == "__main__":
    # Windows 上设置事件循环策略以避免子进程清理问题
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass  # 静默处理 Ctrl+C
