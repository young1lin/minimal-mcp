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
      "content": "你是一个智能客服 Alice，你的主要作用就是帮用户解答疑问",
      "role": "system"
    },
    {
      "content": "你好，你是谁？",
      "role": "user"
    }
  ],
  "model": "deepseek-chat",
  "stream": false,
  "temperature": 0
}
```

响应
```http
HTTP/1.1 200 OK
Date: Wed, 06 Aug 2025 08:21:59 GMT
Content-Type: application/json
Transfer-Encoding: chunked
Connection: close
vary: origin, access-control-request-method, access-control-request-headers
access-control-allow-credentials: true
x-ds-trace-id: 4f241ebb167c3c01b3a97ed15dccc06a
Strict-Transport-Security: max-age=31536000; includeSubDomains; preload
X-Content-Type-Options: nosniff
Server: CW
Content-Encoding: gzip

{
  "id": "379e029d-6fe0-4c17-8b1b-a834033f810e",
  "object": "chat.completion",
  "created": 1754468519,
  "model": "deepseek-chat",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "你好！我是智能客服Alice，很高兴为你服务。我是一个AI助手，可以帮助解答问题、提供信息或协助处理各种事务。有什么我可以帮你的吗？"
      },
      "logprobs": null,
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 21,
    "completion_tokens": 33,
    "total_tokens": 54,
    "prompt_tokens_details": {
      "cached_tokens": 0
    },
    "prompt_cache_hit_tokens": 0,
    "prompt_cache_miss_tokens": 21
  },
  "system_fingerprint": "fp_8802369eaa_prod0623_fp8_kvcache"
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
      "content": "你是一个智能客服 Alice，你的主要作用就是帮用户解答疑问，公司的主要业务就是做量化交易",
      "role": "system"
    },
    {
      "content": "你好，你是谁？",
      "role": "user"
    },
    {
      "content": "你好！我是智能客服Alice，很高兴为你服务。我是一个AI助手，可以帮助解答问题、提供信息或协助处理各种事务。有什么我可以帮你的吗？",
      "role": "assistant"
    },
    {
      "content": "我想咨询下你们公司的业务",
      "role": "user"
    }
  ],
  "model": "deepseek-chat",
  "stream": false,
  "temperature": 0
}
```
响应
```http
{
  "id": "bb4143e9-0411-4c57-bb8f-a6c6723eafc1",
  "object": "chat.completion",
  "created": 1754469182,
  "model": "deepseek-chat",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "你好！我们公司专注于量化交易领域，主要业务包括：  \n\n1. **量化策略开发**——基于数学、统计学和算法模型，设计自动化交易策略。  \n2. **高频交易（HFT）**——利用超低延迟技术进行毫秒级市场套利。  \n3. **资产管理**——通过量化模型管理基金或客户投资组合，优化风险收益比。  \n4. **数据与技术服务**——提供金融数据清洗、因子挖掘、回测平台等支持。  \n\n如果你对某个方向感兴趣，或想了解具体案例/合作方式，可以告诉我，我会进一步解答！ 😊"
      },
      "logprobs": null,
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 71,
    "completion_tokens": 130,
    "total_tokens": 201,
    "prompt_tokens_details": {
      "cached_tokens": 0
    },
    "prompt_cache_hit_tokens": 0,
    "prompt_cache_miss_tokens": 71
  },
  "system_fingerprint": "fp_8802369eaa_prod0623_fp8_kvcache"
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

响应
```http
HTTP/1.1 200 OK
Date: Tue, 26 Aug 2025 16:41:47 GMT
Content-Type: application/json
Transfer-Encoding: chunked
Connection: close
vary: origin, access-control-request-method, access-control-request-headers
access-control-allow-credentials: true
x-ds-trace-id: dd0e40b7e32ea960c5f6eedace6da45f
Strict-Transport-Security: max-age=31536000; includeSubDomains; preload
X-Content-Type-Options: nosniff
Server: CW
Content-Encoding: gzip

{
  "id": "3ce17afc-bd0d-4ba8-b6b2-bc6aeb893439",
  "object": "chat.completion",
  "created": 1756226507,
  "model": "deepseek-chat",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "我来帮您查询北京的天气情况。",
        "tool_calls": [
          {
            "index": 0,
            "id": "call_0_6d23fa67-1011-44c6-9c49-71ada62b2342",
            "type": "function",
            "function": {
              "name": "get_weather",
              "arguments": "{\"location\": \"北京\"}"
            }
          }
        ]
      },
      "logprobs": null,
      "finish_reason": "tool_calls"
    }
  ],
  "usage": {
    "prompt_tokens": 191,
    "completion_tokens": 22,
    "total_tokens": 213,
    "prompt_tokens_details": {
      "cached_tokens": 0
    },
    "prompt_cache_hit_tokens": 0,
    "prompt_cache_miss_tokens": 191
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
      "content": "你是一个智能客服 Alice，你的主要作用就是帮用户解答疑问"
    },
    {
      "role": "user",
      "content": "你好，查一下北京的天气"
    },
    {
      "role": "assistant",
      "content": "我来帮您查询北京的天气情况。",
      "tool_calls": [
        {
          "index": 0,
          "id": "call_0_7261dfb9-46cb-4843-9069-b45662c4fe41",
          "type": "function",
          "function": {
            "name": "get_weather",
            "arguments": "{\"location\": \"北京\"}"
          }
        }
      ]
    },
    {
      "role": "tool",
      "tool_call_id": "call_0_7261dfb9-46cb-4843-9069-b45662c4fe41",
      "content": "晴天，29°C"
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

response

```http
HTTP/1.1 200 OK
Date: Tue, 26 Aug 2025 16:51:41 GMT
Content-Type: application/json
Transfer-Encoding: chunked
Connection: close
vary: origin, access-control-request-method, access-control-request-headers
access-control-allow-credentials: true
x-ds-trace-id: 614cf41c1a9e574593f47bd1a52981e4
Strict-Transport-Security: max-age=31536000; includeSubDomains; preload
X-Content-Type-Options: nosniff
Server: CW
Content-Encoding: gzip

{
  "id": "22448b25-46d7-4e24-8dce-42de932bdf93",
  "object": "chat.completion",
  "created": 1756227101,
  "model": "deepseek-chat",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "根据查询结果，北京目前的天气情况是：\n- 天气状况：晴天\n- 温度：29°C\n\n今天北京的天气很不错呢，是个晴朗的好天气！"
      },
      "logprobs": null,
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 221,
    "completion_tokens": 36,
    "total_tokens": 257,
    "prompt_tokens_details": {
      "cached_tokens": 192
    },
    "prompt_cache_hit_tokens": 192,
    "prompt_cache_miss_tokens": 29
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