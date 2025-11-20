import openai
from dotenv import load_dotenv
import os

_ = load_dotenv()

openai.api_key = os.getenv("DEEPSEEK_API_KEY")


# 创建一个 LLM

## 构建 system prompt

## 将 ToolDefinition 转为 Function Calling 的参数

# 直接调用 OpenAI 的函数，让它自己处理 tool 的调用

# 流式返回结果

# def get_llm():
#     return openai.completions.create(
#         model="deepseek-chat",
#         base_url="https://api.deepseek.com/v1",
#         api_key=openai.api_key,
#         messages=[
#             {"role": "system", "content": "You are a helpful assistant."},
#             {"role": "user", "content": "Hello, how are you?"},
#         ],
#     )
