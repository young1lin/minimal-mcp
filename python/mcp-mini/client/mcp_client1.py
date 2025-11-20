import httpx
import os
import json
import asyncio
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("DEEPSEEK_API_KEY")
if not api_key:
    raise ValueError("DEEPSEEK_API_KEY not found in .env file")

LLM_URL = "https://api.deepseek.com/chat/completions"
LLM_MODEL = "deepseek-chat"
MAX_ROUNDS = 10  # 最多保存10轮对话

DEFAULT_SYSTEM_PROMPT = (
    system_prompt
) = """
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

**第二步：工具调用**
在思考过程之后，立即展示工具调用，使用下面的 XML 格式。

**重要**：
1. 思考过程必须使用 `<thinking></thinking>` 标签包裹
2. 思考过程和工具调用必须分开展示，先思考后调用
3. 所有 XML 标签必须正确闭合

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

    async def chat(self, message: str):
        """流式对话，返回异步生成器"""
        self.messages.append({"role": "user", "content": message})
        self._limit_messages()

        async with self.client.stream(
            "POST",
            url=LLM_URL,
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={"model": LLM_MODEL, "messages": self.messages, "stream": True},
        ) as response:
            response.raise_for_status()

            full_content = ""
            async for line in response.aiter_lines():
                if not line.strip():
                    continue

                # 处理SSE格式的数据
                if line.startswith("data: "):
                    data_str = line[6:]  # 移除 "data: " 前缀
                    if data_str == "[DONE]":
                        break

                    try:
                        data = json.loads(data_str)
                        choices = data.get("choices", [])
                        if choices:
                            delta = choices[0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                full_content += content
                                yield content
                    except json.JSONDecodeError:
                        continue

            # 将完整的回复添加到消息历史中
            if full_content:
                self.messages.append({"role": "assistant", "content": full_content})
                self._limit_messages()


async def main():
    system_prompt = DEFAULT_SYSTEM_PROMPT
    chatbot = ChatBot(api_key, system_prompt)
    async for content in chatbot.chat("今天北京天气如何？"):
        print(content, end="", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
