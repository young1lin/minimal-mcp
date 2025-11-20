import httpx
import os
import json
import asyncio
import re
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("DEEPSEEK_API_KEY")
if not api_key:
    raise ValueError("DEEPSEEK_API_KEY not found in .env file")

LLM_URL = "https://api.deepseek.com/chat/completions"
LLM_MODEL = "deepseek-chat"
MAX_ROUNDS = 10  # 最多保存10轮对话

DEFAULT_SYSTEM_PROMPT = """
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
用户询问北京的天气情况。我需要使用 fake-weather-server 的 get_weather 工具来获取天气信息。该工具需要 city 参数，我应该传入 "北京"。
</thinking>

<use_mcp_tool>
<server_name>fake-weather-server</server_name>
<tool_name>get_weather</tool_name>
<arguments>
{
  "city": "北京"
}
</arguments>
</use_mcp_tool>

使用 MCP Tool 样例1：
<use_mcp_tool>
<server_name>weather-server</server_name>
<tool_name>get_forecast</tool_name>
<arguments>
{
  "city": "San Francisco",
  "days": 5
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
现在你有这些 MCP Server 可以调用：

## fake-weather-server
### 可用工具如下
- get_weather：根据输入的城市名称，返回该城市的天气信息
  输入参数：
    - city：城市名称
  输出：
    - weather：天气信息
    - temperature：温度
    - humidity：湿度
    - wind：风速

- list_get_weather_records：返回查询过的所有的天气记录
  输入参数：无
  输出：
    - weather_records：天气记录
      - city：城市名称
      - weather：天气信息
      - temperature：温度
      - humidity：湿度
      - wind：风速
"""


class ChatBot:

    def __init__(self, api_key: str, system_prompt: str):
        self.api_key = api_key
        self.system_prompt = system_prompt
        self.client = httpx.AsyncClient()
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
    system_prompt = DEFAULT_SYSTEM_PROMPT
    chatbot = ChatBot(api_key, system_prompt)

    async for content in chatbot.chat("列出当前目录有什么"):
        print(content, end="", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
