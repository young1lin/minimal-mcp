import os
import threading
import time
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain.prompts import ChatPromptTemplate
from langchain.tools import tool
from langchain.callbacks import StreamingStdOutCallbackHandler
from langchain.callbacks.base import BaseCallbackHandler

load_dotenv()

api_key = os.getenv("DEEPSEEK_API_KEY")
if not api_key:
    raise ValueError("DEEPSEEK_API_KEY not found in .env file")

# 自定义流式回调处理器
class CustomStreamingHandler(BaseCallbackHandler):
    def __init__(self):
        self.is_streaming = False
        
    def on_llm_start(self, serialized, prompts, **kwargs):
        """LLM 开始时的回调"""
        self.is_streaming = True
        
    def on_llm_new_token(self, token: str, **kwargs):
        """每个新 token 的回调 - 实现逐字符输出"""
        if self.is_streaming:
            print(token, end="", flush=True)
    
    def on_llm_end(self, response, **kwargs):
        """LLM 结束时的回调"""
        self.is_streaming = False
        
    def on_tool_start(self, serialized, input_str: str, **kwargs):
        """工具开始时的回调"""
        tool_name = serialized.get("name", "unknown_tool")
        print(f"\n🔧 正在使用工具: {tool_name}")
        print(f"📝 输入参数: {input_str}")
        
    def on_tool_end(self, output: str, **kwargs):
        """工具结束时的回调"""
        print(f"✅ 工具执行完成")
        print(f"🤖 生成回复: ", end="", flush=True)

# 创建流式回调处理器
streaming_handler = CustomStreamingHandler()

llm = ChatOpenAI(
    model="deepseek-chat",
    base_url="https://api.deepseek.com/v1",
    api_key=api_key,
    streaming=True,
    temperature=0.1,
    callbacks=[streaming_handler]  # 添加流式回调
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
    location_clean = location.lower().strip()
    
    print(f"receive location: {location_clean}")
    # 支持更多的北京变体
    beijing_variants = ["beijing", "北京", "bj"]
    
    if location_clean in beijing_variants:
        print("📍 正在查询北京天气............")
        return "北京今日天气：晴天，气温 25°C，湿度 45%，微风"
    elif location_clean == "shanghai":
        return "上海今日天气：多云，气温 28°C，湿度 55%，微风"
    elif location_clean == "hangzhou":
        print("📍 正在查询杭州天气............")
        return "杭州今日天气：小雨，气温 25°C，湿度 60%，大风"
    elif location_clean == "newyork":
        print("📍 正在查询纽约天气............")
        return "纽约今日天气：小雨，气温 15°C，湿度 40%，微风"
    else:
        return f"抱歉，暂时无法查询到 '{location}' 的天气信息。目前仅支持查询北京的天气。"

# 全局状态管理
class ChatState:
    def __init__(self):
        self.is_processing = False
        self.lock = threading.Lock()
        self.should_exit = False
    
    def set_processing(self, status: bool):
        with self.lock:
            self.is_processing = status
    
    def is_busy(self) -> bool:
        with self.lock:
            return self.is_processing
    
    def exit(self):
        with self.lock:
            self.should_exit = True

# 工具列表
tools = [get_weather]

# 改进的提示模板
prompt = ChatPromptTemplate.from_messages([
    ("system", """你是一个专业的天气查询助手。你可以帮用户查询天气信息。"""),
    ("human", "{input}"),
    ("placeholder", "{agent_scratchpad}"),
])

chat_state = ChatState()

# 创建 agent - 注意这里也要传入回调
agent = create_tool_calling_agent(llm, tools, prompt)
agent_executor = AgentExecutor(
    agent=agent, 
    tools=tools, 
    verbose=False,  # 关闭默认的详细输出，使用自定义回调
    handle_parsing_errors=True,
    callbacks=[streaming_handler]  # 为 agent_executor 也添加回调
)

def process_user_input(user_input: str, agent_executor: AgentExecutor):
    """处理用户输入的函数，在单独线程中运行"""
    chat_state.set_processing(True)
    
    try:        
        # 使用 invoke 而不是 stream，让回调处理器处理流式输出
        response = agent_executor.invoke({"input": user_input})
        
        print("\n" + "-" * 50)
        
    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
        print("🔄 请重试或输入 'exit' 退出")
    finally:
        chat_state.set_processing(False)

def get_user_input() -> str:
    """获取用户输入，带有状态检查"""
    while True:
        if chat_state.should_exit:
            return ""
            
        # 检查是否正在处理
        if chat_state.is_busy():
            print("\r🔄 AI 正在思考中，请稍候...", end="", flush=True)
            time.sleep(0.1)
            continue
        
        # 清除提示行
        print("\r" + " " * 40, end="")
        print("\r🗣️ 请输入您的问题: ", end="", flush=True)
        
        try:
            user_input = input().strip()
            return user_input
        except EOFError:
            return "exit"
        except KeyboardInterrupt:
            print("\n")
            return "exit"

def main():
    print("🌤️ 天气查询助手启动！")
    print("💡 提示：目前支持查询北京的天气信息")
    print("📝 输入 'exit' 或 'quit' 退出程序")
    print("⚠️ 流式输出已启用，AI 将逐字输出回复\n")
    
    while not chat_state.should_exit:
        try:
            user_input = get_user_input()
            
            if not user_input or user_input.lower() in ['exit', 'quit', '退出', 'q']:
                chat_state.exit()
                print("👋 再见！感谢使用天气查询助手！")
                break
            
            if not user_input.strip():
                print("❌ 请输入有效的问题")
                continue
            
            print()  # 换行，准备输出回复
            
            # 在单独线程中处理用户输入
            processing_thread = threading.Thread(
                target=process_user_input, 
                args=(user_input, agent_executor),
                daemon=True
            )
            processing_thread.start()
            
            # 等待处理完成
            processing_thread.join()
            
        except KeyboardInterrupt:
            print("\n\n👋 程序被用户中断，再见！")
            chat_state.exit()
            break
        except Exception as e:
            print(f"\n❌ 主程序发生错误: {e}")
            chat_state.set_processing(False)

if __name__ == "__main__":
    main()