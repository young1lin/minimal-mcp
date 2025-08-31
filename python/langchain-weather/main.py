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
