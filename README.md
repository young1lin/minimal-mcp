# LLM
简单介绍一下 LLM（Large Language Model），就是你输入一段文字，机器猜你下一个词是什么，就这么简单。
详细了解，看我上一篇文章（TODO 放链接），大模型并没有“记住”你的事情，看下面演示。

这里做一些非常简单的调用

## 单一调用

请求
```http
POST https://api.deepseek.com/chat/completions HTTP/1.1
Content-Type: application/json
Accept: application/json
Authorization: Bearer {{$dotenv DEEPSEEK_API_KEY}}

{
  "messages": [
    {
      "content": "You are an intelligent customer service agent named Alice. Your main role is to help users answer their questions.",
      "role": "system"
    },
    {
      "content": "Hello, who are you?",
      "role": "user"
    }
  ],
  "model": "deepseek-chat",
  "stream": false,
  "temperature": 0
}
```

response body
```json
{
  "id": "e479b679-84d4-48c1-bf6f-ad7f56c87682",
  "object": "chat.completion",
  "created": 1756429739,
  "model": "deepseek-chat",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "Hello! I'm Alice, your intelligent customer service agent. How can I assist you today?"
      },
      "logprobs": null,
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 31,
    "completion_tokens": 19,
    "total_tokens": 50,
    "prompt_tokens_details": {
      "cached_tokens": 0
    },
    "prompt_cache_hit_tokens": 0,
    "prompt_cache_miss_tokens": 31
  },
  "system_fingerprint": "fp_feb633d1f5_prod0820_fp8_kvcache"
}
```

## 多轮对话

```http
POST https://api.deepseek.com/chat/completions HTTP/1.1
Content-Type: application/json
Accept: application/json
Authorization: Bearer {{$dotenv DEEPSEEK_API_KEY}}

{
  "messages": [
    {
      "content": "You are an intelligent customer service agent named Alice. Your main role is to help users answer their questions. The company's main business is quantitative trading.",
      "role": "system"
    },
    {
      "content": "Hello, who are you?",
      "role": "user"
    },
    {
      "content": "Hello! I'm Alice, your intelligent customer service agent. How can I assist you today?",
      "role": "assistant"
    },
    {
      "content": "I would like to inquire about your company's business.",
      "role": "user"
    }
  ],
  "model": "deepseek-chat",
  "stream": false,
  "temperature": 0
}
```
response body
```json
{
  "id": "f21a4cd8-baad-449c-a91a-8ac38a674715",
  "object": "chat.completion",
  "created": 1756429876,
  "model": "deepseek-chat",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "Of course! Our company specializes in quantitative trading, which involves using mathematical models, algorithms, and data analysis to make trading decisions in financial markets. We leverage technology and data to identify patterns, manage risk, and execute trades efficiently. \n\nIs there a specific aspect of quantitative trading you'd like to learn more about?"
      },
      "logprobs": null,
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 74,
    "completion_tokens": 63,
    "total_tokens": 137,
    "prompt_tokens_details": {
      "cached_tokens": 0
    },
    "prompt_cache_hit_tokens": 0,
    "prompt_cache_miss_tokens": 74
  },
  "system_fingerprint": "fp_feb633d1f5_prod0820_fp8_kvcache"
}
```

## 使用 Function Calling

请求
```http
POST https://api.deepseek.com/chat/completions HTTP/1.1
Content-Type: application/json
Accept: application/json
Authorization: Bearer {{$dotenv DEEPSEEK_API_KEY}}

{
  "messages": [
    {
      "content": "你是一个智能客服 Alice，你的主要作用就是帮用户解答疑问",
      "role": "system"
    },
    {
      "content": "你好，查一下北京的天气",
      "role": "user"
    }
  ],
  "model": "deepseek-chat",
  "tools": [
    {
      "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get weather of a location, the user should supply a location first.",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "The city and state, e.g. San Francisco, CA"
                    }
                },
                "required": ["location"]
            }
        }
    }
  ],
  "stream": false,
  "temperature": 0
}
```

response body
```json
{
  "id": "2e85bf30-d509-4ee6-bc18-b65d1b8e02df",
  "object": "chat.completion",
  "created": 1756430135,
  "model": "deepseek-chat",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "I'll check the weather in Hangzhou for you right away.",
        "tool_calls": [
          {
            "index": 0,
            "id": "call_0_c9f112b0-766e-48ee-8b7d-a70c14f16b43",
            "type": "function",
            "function": {
              "name": "get_weather",
              "arguments": "{\"location\": \"hangzhou\"}"
            }
          }
        ]
      },
      "logprobs": null,
      "finish_reason": "tool_calls"
    }
  ],
  "usage": {
    "prompt_tokens": 212,
    "completion_tokens": 28,
    "total_tokens": 240,
    "prompt_tokens_details": {
      "cached_tokens": 192
    },
    "prompt_cache_hit_tokens": 192,
    "prompt_cache_miss_tokens": 20
  },
  "system_fingerprint": "fp_feb633d1f5_prod0820_fp8_kvcache"
}
```

### Function Calling conversation

request

```http
POST https://api.deepseek.com/chat/completions HTTP/1.1
Content-Type: application/json
Accept: application/json
Authorization: Bearer {{$dotenv DEEPSEEK_API_KEY}}

{
  "messages": [
    {
      "role": "system",
      "content": "You are an intelligent customer service agent named Alice. Your main role is to help users answer their questions."
    },
    {
      "role": "user",
      "content": "Hello, please check the weather in Beijing."
    },
    {
      "role": "assistant",
      "content": "I'll check the weather in Hangzhou for you right away.",
      "tool_calls": [
        {
          "index": 0,
          "id": "call_0_c9f112b0-766e-48ee-8b7d-a70c14f16b43",
          "type": "function",
          "function": {
            "name": "get_weather",
            "arguments": "{\"location\": \"hangzhou\"}"
          }
        }
      ]
    },
    {
      "role": "tool",
      "tool_call_id": "call_0_c9f112b0-766e-48ee-8b7d-a70c14f16b43",
      "content": "Sunny, 29°C"
    }
  ],
  "model": "deepseek-chat",
  "tools": [
    {
      "type": "function",
      "function": {
        "name": "get_weather",
        "description": "Get weather information for a location.",
        "parameters": {
          "type": "object",
          "properties": {
            "location": {
              "type": "string",
              "description": "The name of the city to get weather for. Only support low case location name, like beijing, shanghai, hangzhou, newyork"
            }
          },
          "required": [
            "location"
          ]
        }
      }
    }
  ],
  "stream": false,
  "temperature": 0
}
```

response body

```json
{
  "id": "2ef2e44e-8540-4798-8530-77b63209e1a9",
  "object": "chat.completion",
  "created": 1756430434,
  "model": "deepseek-chat",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "The weather in Hangzhou is currently sunny with a temperature of 29°C. It's a beautiful day there! Is there anything else you'd like to know about the weather or any other assistance I can provide?"
      },
      "logprobs": null,
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 238,
    "completion_tokens": 44,
    "total_tokens": 282,
    "prompt_tokens_details": {
      "cached_tokens": 0
    },
    "prompt_cache_hit_tokens": 0,
    "prompt_cache_miss_tokens": 238
  },
  "system_fingerprint": "fp_feb633d1f5_prod0820_fp8_kvcache"
}
```

这就是大模型，就是猜你下一段词是什么，就这么简单。

# 背景介绍

一开始 OpenAI 的 GPT 接口出来的时候，并没有提供 Function Calling 这样的功能，但是为了和现实世界进行交互，LangChain, Smolagents 这种框架，又想要和
现实世界进行交互，并获得相应的信息，它就只能在返回的文本上，自定义格式，通过装饰器 @tool（Java 里可以用注解）解析成一个 Tool 对象，这个对象有入参，及其参数描述，
有这个方法的描述。在调用大模型的时候，只需要 Tool 解析成 System prompt 文本，并且以特定的格式返回，进行是否调用工具，然后执行下一步。这里我们暂且按下不表，
后面会介绍 Cline 是如何实现的，详细解释通过控制 system prompt 来实现结构化返回，并且解析结构化返回内容实现“智能”调用工具。

这样说有点抽象，写一个例子，这里我是用 uv 来管理包。我并不推荐使用 LangChain 用于生产环境，变更太多了，本来就是一件简单的事情，越搞越复杂，已经过于臃肿了，
LangChain Community，文档也更新不及时，对新人来说很不友好，什么 LangSmith，LangGraph 干什么呢。

## Python part

prepare install uv, langchain, langchain-openai, python-dotenv.

```shell
python -m pip install uv
uv init langchain-weather
cd langchain-weather && uv add langchain langchain-openai python-dotenv

# replace this api_key with your own
echo "DEEPSEEK_API_KEY=your_deepseek_api_key_here" > .env
```

main.py
```python
import os
import asyncio
import warnings

# 禁用 LangSmith 追踪和警告
os.environ["LANGCHAIN_TRACING_V2"] = "false"
warnings.filterwarnings("ignore", category=UserWarning, module="langsmith")

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain.agents import create_react_agent, AgentExecutor
from langchain.prompts import ChatPromptTemplate
from langchain.tools import tool

load_dotenv()

api_key = os.getenv("DEEPSEEK_API_KEY")
if not api_key:
    raise ValueError("DEEPSEEK_API_KEY not found in .env file")

llm = ChatOpenAI(
    model="deepseek-chat",
    base_url="https://api.deepseek.com/v1",
    api_key=api_key,
    streaming=True,
    temperature=0.1,
)


@tool
def get_weather(location: str) -> str:
    """
    Get weather information for a location.

    Args:
        location (str): The name of the city to get weather for. Only support low case location name, like beijing, shanghai, hangzhou, newyork'.

    Returns:
        str: Weather information for the specified location.
    """
    match location:
        case "beijing":
            return "北京今日天气：晴天，气温 25°C，湿度 45%，微风"
        case "shanghai":
            return "上海今日天气：多云，气温 28°C，湿度 55%，微风"
        case "hangzhou":
            return "杭州今日天气：小雨转大雨，气温 22°C 到 28°C，湿度 70%，微风"
        case "newyork":
            return "纽约今日天气：小雨，气温 15°C，湿度 40%，微风"
        case _:
            return f"抱歉，暂时无法查询到 '{location}' 的天气信息。目前仅支持查询北京的天气。"


# ReAct 提示模板
from langchain import hub

prompt = hub.pull("hwchase17/react")

# 创建 ReAct agent
agent = create_react_agent(llm, [get_weather], prompt)
agent_executor = AgentExecutor(agent=agent, tools=[get_weather], verbose=False)


async def main():
    user_input = "查询纽约天气"
    print(f"用户输入: {user_input}\n")

    try:
        # 使用 astream_events 获取真正的流式输出
        current_content = ""
        
        async for event in agent_executor.astream_events(
            {"input": user_input}, 
            version="v1"
        ):
            kind = event["event"]
            
            # 流式输出 LLM 内容
            if kind == "on_chat_model_stream":
                content = event["data"]["chunk"].content
                if content:
                    current_content += content
                    print(content, end="", flush=True)
                    
            # 工具开始执行时
            elif kind == "on_tool_start":
                if event["name"] == "get_weather":
                    # 从当前累积的内容中提取工具参数
                    lines = current_content.split('\n')
                    action_input = ""
                    for line in lines:
                        if "Action Input:" in line:
                            action_input = line.split("Action Input:")[-1].strip()
                            break
                    print(f"\n\n🔧 开始调用工具: {event['name']}")
                    print(f"   输入参数: {action_input}")
                    
            # 工具执行完成时
            elif kind == "on_tool_end":
                if event["name"] == "get_weather":
                    tool_output = event["data"].get("output", "")
                    print(f"\n📝 工具返回结果: {tool_output}\n")
                
        print(f"\n\n{'-'*50}")
    except Exception as e:
        print(f"❌ 错误: {e}")


if __name__ == "__main__":
    asyncio.run(main())
```

execute main.py

```shell
uv run main.py
```

response
```plaintext
用户输入: 查询纽约天气

Thought: The user is asking for the weather in New York. I need to use the get_weather function to retrieve this information. The function requires the location name in lowercase, so I should use "newyork".

Action: get_weather
Action Input: newyork

🔧 开始调用工具: get_weather
   输入参数: newyork

📝 工具返回结果: 纽约今日天气：小雨，气温 15°C，湿度 40%，微风

I now know the final answer

Final Answer: 纽约今日天气：小雨，气温 15°C，湿度 40%，微风
--------------------------------------------------
```

可以从上面看出来，可以通过 LangChain 这样的框架，是可以通过调用 “代码” 来返回实时的内容加入到对话中。这里用到的是比较早期的 ReAct 形式，通过
编写合适的系统提示词，来决定调用什么工具，下一步如何执行。在上一节展示的 Function Calling 是比较后面才出的，我 23 年刚做这块的时候，OpenAI 还没有
推出 Function Calling。

两者呢，本质上，都是通过调用项内的方法/函数来实现和现实世界交互，获取最新的信息，并且返回给大模型，让大模型继续猜下一个 Token，下下一个 Token 是什么，然后返回给你
的一个过程。

你 Python 有 LangChain，Java 有 Spring AI，基于 TypeScript 写的 AI 客户端有 Cline，有 Continue，有 Claude Desktop，有 Copilot，每个语言，每个框架都有自己的实现，那我想实现一个
获取当前天气，或者操作 Redis，MongoDB 插入数据，更新数据这些 tool（工具）怎么办？每个客户端都写一遍？重复造轮子，还要改它们对应的源码，这样对不了解大模型，不了解
代码的人来说不太友好，而且都是重复的工作，每个语言都实现一遍，不好。

这个时候，也就是 2024 年 11 月，Claude 牵头提出了 MCP Model Context Protocol 一个概念，我们先不用管里面的其他组件，例如 prompts, resources, 如何握手，JSON RPC 这些东西。
你只需要知道，MCP 就是为了解决重复造轮子，大家只要配置相应的内容，就可以直接调用这些封装好的 tools 就行了。Claude 让大家都来接这个协议，至于你怎么调用
怎么在 IPC（Internet Process Communication） 中协商在协议里面都写了。

相信你或多或少用过 MCP，或者听过，就下面这些配置就能让 LLM 客户端自动调用这些工具，像下面这样配置。

```json
{
  "mcpServers": {
    "figma-mcp": {
      "command": "npx",
      "args": ["figma-mcp"],
      "env": {
        "FIGMA_API_KEY": "<YOUR_API_KEY>"
      }
    }
  }
}
```

我就这么一配置，诶，我就能实现通过 Copilot 或者 Cursor 或者任何一个支持 MCP 的客户端，就用自然语言描述，就能调用这个工具。

接下来，我会通过从零开始，只调用最基础的库，任何语言的 HTTP 库来实现 MCP Client，Server，Host。并且接入 Cursor，Cline，Copilot，Qwen Coder 这些工具。
很简单，一步步来，你也是了解 MCP，LLM 的 “专家”。

# 实现 MCP Client

## Python

## Java

## Go

## Node.js