# LLM
简单介绍一下 LLM（Large Language Model），就是你输入一段文字，机器猜你下一个词是什么，就这么简单。
详细了解，看我上一篇文章（TODO 放链接）。

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

一开始 OpenAI 的 GPT 出来的时候，并没有提供 Function Calling 这样的功能，但是为了和现实世界进行交互，LangChain, Smolagents 这种框架，又想要和
现实世界进行交互，并获得相应的信息，它就只能在返回的文本上，自定义格式，通过装饰器 @tool（Java 里可以用注解）解析成一个 Tool 对象，这个对象有入参，及其参数描述，
有这个方法的描述。在调用大模型的时候，只需要 Tool 解析成 System prompt 文本，并且以特定的格式返回，进行是否调用工具，然后执行下一步。

这样说有点抽象，写一个例子，这里我是用 uv 来管理包

```python

```