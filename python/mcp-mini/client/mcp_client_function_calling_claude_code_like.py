"""
Claude Code 风格的 MCP 客户端

功能特点：
- 支持 MCP 服务器连接和工具调用
- 在工具执行过程中按 ESC 键可以中断执行
- 中断后可以输入新的指令继续对话
- 类似 Claude Code 的交互体验

使用方法：
1. 配置 .env 文件中的 DEEPSEEK_API_KEY
2. 配置 mcp-claude-code.json 中的服务器信息
3. 运行程序并开始对话
4. 在工具执行时按 ESC 中断，按 Ctrl+C 退出

注意：键盘中断功能仅在 Windows 系统上可用
"""

import httpx
import os
import json
import asyncio
import subprocess
from pathlib import Path
from typing import Any
from dotenv import load_dotenv
import sys
import shutil
import threading
import time

# ANSI 颜色代码
GREEN = "\033[32m"
RED = "\033[31m"
WHITE = "\033[37m"
RESET = "\033[0m"
GREEN_CIRCLE = f"{GREEN}●{RESET}"
RED_CIRCLE = f"{RED}●{RESET}"
WHITE_CIRCLE = f"{WHITE}●{RESET}"
BLINK = "\033[5m"  # 闪烁

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

# 导入内置工具（这些是 SimpleTool 对象）
from tools import (
    fetch_to_markdown,
    read_file,
    write_file,
    edit_file,
    glob_files,
    run_shell,
    simple_tool_to_function_calling,
    mcp_tool_to_function_calling,
)

# Windows 键盘监听
if sys.platform == "win32":
    import msvcrt

load_dotenv()

api_key = os.getenv("DEEPSEEK_API_KEY")
if not api_key:
    raise ValueError("DEEPSEEK_API_KEY not found in .env file")

# 支持从环境变量配置 LLM 参数
LLM_URL = os.getenv("LLM_URL", "https://api.deepseek.com/chat/completions")
LLM_MODEL = os.getenv("LLM_MODEL", "deepseek-reasoner")
MAX_ROUNDS = int(os.getenv("MAX_ROUNDS", "200"))
TOOL_TIMEOUT = int(os.getenv("TOOL_TIMEOUT", "300"))  # 工具执行超时（秒），默认 5 分钟


def listen_for_escape(stop_event: threading.Event) -> None:
    """在单独线程中监听键盘输入，检测 Esc 键"""
    if sys.platform != "win32":
        return

    import msvcrt

    try:
        while not stop_event.is_set():
            if msvcrt.kbhit():
                key = msvcrt.getch()
                # ESC 键会返回 b'\x1b'，但功能键会先返回 b'\xe0'
                if key == b"\x1b":  # ESC 键
                    stop_event.set()
                    break
                elif key == b"\x03":  # Ctrl+C
                    stop_event.set()
                    break
                elif key == b"\xe0":
                    # 功能键的前缀，读取实际的键码后丢弃
                    msvcrt.getch()
            time.sleep(0.01)  # 小延迟避免 CPU 占用过高
    except Exception:
        pass  # 静默处理异常


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


def convert_arguments(arguments: dict, tool_definition: dict) -> dict:
    """
    根据工具定义转换参数类型

    Args:
        arguments: 原始参数字典（从 JSON 解析）
        tool_definition: 工具定义（包含参数类型信息）

    Returns:
        转换后的参数字典
    """
    if not tool_definition or "function" not in tool_definition:
        return arguments

    parameters = tool_definition.get("function", {}).get("parameters", {})
    properties = parameters.get("properties", {})

    converted = {}
    for key, value in arguments.items():
        if key not in properties:
            converted[key] = value
            continue

        param_type = properties[key].get("type", "string")

        # 类型转换
        try:
            if param_type == "integer" and isinstance(value, str):
                converted[key] = int(value)
            elif param_type == "number" and isinstance(value, str):
                converted[key] = float(value)
            elif param_type == "boolean" and isinstance(value, str):
                converted[key] = value.lower() in ("true", "1", "yes")
            else:
                converted[key] = value
        except (ValueError, TypeError):
            # 转换失败，保持原值
            converted[key] = value

    return converted


class FunctionCallingChatBot:
    """使用原生 Function Calling 的 ChatBot"""

    def __init__(
        self,
        api_key: str,
        mcp_clients: dict[str, MCPClient] | None = None,
        work_dir: str | None = None,
    ):
        self.api_key = api_key
        self.client = httpx.AsyncClient()
        self.mcp_clients = mcp_clients or {}
        self.work_dir = work_dir or str(Path(__file__).parent.parent)

        # 构建 Function Calling 工具列表
        self.tools = []
        self.tool_mapping = {}  # function_name -> (server_name, tool_name)
        self.builtin_tools = {}  # function_name -> callable
        self.tool_definitions = {}  # function_name -> tool_definition (for type conversion)

        # 添加内置工具 - 这些是 SimpleTool 对象，使用 simple_tool_to_function_calling
        builtin_tools = [
            fetch_to_markdown,
            read_file,
            write_file,
            edit_file,
            glob_files,
            run_shell,
        ]

        for tool_def in builtin_tools:
            # tool_def 是 SimpleTool 对象，name 从 @tool(name="xxx") 获取
            function_def = simple_tool_to_function_calling(tool_def)
            self.tools.append(function_def)
            self.builtin_tools[tool_def.name] = tool_def.func
            self.tool_definitions[tool_def.name] = function_def  # 保存工具定义

        # 添加 MCP 工具 - 使用 mcp_tool_to_function_calling（ToolDefinition 没有 func 属性）
        for server_name, mcp_client in self.mcp_clients.items():
            for tool in mcp_client.tools:
                function_def = mcp_tool_to_function_calling(tool, server_name)
                self.tools.append(function_def)

                # 建立映射关系
                function_name = function_def["function"]["name"]
                self.tool_mapping[function_name] = (server_name, tool.name)
                self.tool_definitions[function_name] = function_def  # 保存工具定义

        # 初始化消息历史
        self.messages = [
            {
                "role": "system",
                "content": "你是一个优秀的 AI 助手，可以使用多种工具来帮助用户完成任务。",
            }
        ]

        # 键盘中断相关
        self.interrupt_event = threading.Event()
        self.keyboard_thread = None

        # 获取 Memory.md 内容
        self.memory_content = self._load_memory()

    def _load_memory(self) -> str:
        """加载 Memory.md 文件内容"""
        memory_path = Path(self.work_dir) / "Memory.md"
        if memory_path.exists():
            try:
                return memory_path.read_text(encoding="utf-8")
            except Exception:
                return ""
        return ""

    def _get_git_branch(self) -> str:
        """获取当前 Git 分支"""
        try:
            result = subprocess.run(
                ["git", "branch", "--show-current"],
                cwd=self.work_dir,
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                return result.stdout.strip()
            return ""
        except Exception:
            return ""

    def _build_system_prompt(self) -> str:
        """构建动态 system prompt，包含工作目录、Git 分支和 Memory.md 内容"""
        # 添加工作目录信息
        work_dir_info = f"\n\n## 当前工作目录\n{self.work_dir}"

        # 添加 Git 分支信息
        git_branch = self._get_git_branch()
        if git_branch:
            git_info = f"\n\n## 当前 Git 分支\n{git_branch}"
        else:
            git_info = ""

        # 添加 Memory.md 内容
        if self.memory_content:
            memory_info = f"\n\n## 项目说明 (Memory.md)\n{self.memory_content}"
        else:
            memory_info = ""

        base_prompt = f"""你是一个优秀的 AI 助手，可以使用多种工具来帮助用户完成任务。{work_dir_info}{git_info}{memory_info}"""

        return base_prompt

    def _update_system_prompt(self):
        """更新 system prompt 为最新内容"""
        if self.messages and self.messages[0]["role"] == "system":
            self.messages[0]["content"] = self._build_system_prompt()

    def start_keyboard_listener(self):
        """启动键盘监听线程"""
        if sys.platform != "win32":
            return

        if self.keyboard_thread and self.keyboard_thread.is_alive():
            return  # 已经启动

        self.interrupt_event.clear()
        self.keyboard_thread = threading.Thread(
            target=listen_for_escape, args=(self.interrupt_event,)
        )
        self.keyboard_thread.daemon = True
        self.keyboard_thread.start()

    def stop_keyboard_listener(self):
        """停止键盘监听"""
        if self.keyboard_thread:
            self.interrupt_event.set()
            self.keyboard_thread.join(timeout=0.1)
            self.keyboard_thread = None

    def _limit_messages(self):
        """限制消息数量，确保不会单独保留 tool 消息而删除其对应的 assistant 消息"""
        # 保留第一个 system message 在正确的位置
        system_messages = [msg for msg in self.messages if msg["role"] == "system"]
        other_messages = [msg for msg in self.messages if msg["role"] != "system"]

        if len(other_messages) <= MAX_ROUNDS * 2:
            # 确保 system message 在开头
            if system_messages:
                self.messages = system_messages + other_messages
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

        # 确保 system message 在开头
        if system_messages:
            self.messages = system_messages + kept_messages
        else:
            self.messages = kept_messages

    async def _call_llm(self):
        """一次性调用 LLM，返回完整响应和 tool_calls，支持中断"""
        request_data = {
            "model": LLM_MODEL,
            "messages": self.messages,
            "tools": self.tools,
            "stream": False,  # 改为非流式
        }

        # 检查是否被中断
        if self.interrupt_event.is_set():
            raise asyncio.CancelledError("LLM请求被用户中断")

        try:
            response = await self.client.post(
                LLM_URL,
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=request_data,
                timeout=60.0,
            )
        except asyncio.CancelledError:
            raise
        except Exception as e:
            if self.interrupt_event.is_set():
                raise asyncio.CancelledError("LLM请求被用户中断")
            raise e

        if response.status_code != 200:
            error_text = response.text
            print(f"\n[错误] API 返回状态码: {response.status_code}")
            print(f"[错误] 响应内容: {error_text}")
            response.raise_for_status()

        data = response.json()
        choice = data.get("choices", [{}])[0]
        message = choice.get("message", {})

        # 提取内容
        full_content = message.get("content", "")
        full_reasoning_content = message.get("reasoning_content", "")
        tool_calls_data = message.get("tool_calls", [])

        # 构建完整的 message 对象
        message_obj = {"role": "assistant"}
        if full_reasoning_content:
            message_obj["reasoning_content"] = full_reasoning_content
        if full_content:
            message_obj["content"] = full_content
        elif tool_calls_data:
            # 如果没有 content 但有 tool_calls，必须添加空字符串 content
            message_obj["content"] = ""
        else:
            # 如果两者都没有，添加空字符串以避免 API 错误
            message_obj["content"] = ""
        if tool_calls_data:
            message_obj["tool_calls"] = tool_calls_data

        return message_obj, tool_calls_data

    async def _execute_tool_calls(
        self, tool_calls: list[dict], interrupt_event: threading.Event
    ) -> tuple[list[dict], bool]:
        """并行执行多个工具调用，返回 (results, was_interrupted)"""
        interrupted = False
        stop_event = interrupt_event  # 使用传入的中断事件

        async def execute_single_tool(tool_call: dict, index: int) -> tuple[int, dict]:
            """执行单个工具调用"""
            function_name = tool_call["function"]["name"]
            arguments_str = tool_call["function"]["arguments"]

            try:
                arguments = json.loads(arguments_str) if arguments_str else {}
            except json.JSONDecodeError:
                result = {
                    "tool_call_id": tool_call["id"],
                    "role": "tool",
                    "content": f"错误：参数不是有效的 JSON: {arguments_str}",
                }
                return index, result

            # 类型转换：根据工具定义转换参数类型
            if function_name in self.tool_definitions:
                arguments = convert_arguments(arguments, self.tool_definitions[function_name])

            # 确定显示的工具名称和格式（统一格式）
            if function_name in self.builtin_tools:
                # 内置工具
                display_name = function_name
                tool_prefix = ""
            else:
                # MCP 工具从 tool_mapping 获取原始 tool_name
                if function_name in self.tool_mapping:
                    server_name, tool_name = self.tool_mapping[function_name]
                    display_name = tool_name
                    tool_prefix = f"[{server_name}] "
                else:
                    display_name = function_name
                    tool_prefix = "[MCP] "

            # 统一显示格式：tool_name(args)
            if arguments:
                args_str = json.dumps(arguments, ensure_ascii=False)
                print(f"\n{GREEN_CIRCLE} {tool_prefix}{display_name}({args_str})\n")
            else:
                print(f"\n{GREEN_CIRCLE} {tool_prefix}{display_name}()\n")

            # 先检查是否是内置工具
            if function_name in self.builtin_tools:
                try:
                    if stop_event.is_set():
                        result = {
                            "tool_call_id": tool_call["id"],
                            "role": "tool",
                            "content": "工具执行被用户中断",
                        }
                        return index, result

                    builtin_func = self.builtin_tools[function_name]
                    # 添加超时控制
                    result_content = await asyncio.wait_for(
                        builtin_func(**arguments), timeout=TOOL_TIMEOUT
                    )
                    result = {
                        "tool_call_id": tool_call["id"],
                        "role": "tool",
                        "content": result_content,
                    }
                    return index, result
                except asyncio.TimeoutError:
                    result = {
                        "tool_call_id": tool_call["id"],
                        "role": "tool",
                        "content": f"错误：工具执行超时（超过 {TOOL_TIMEOUT} 秒）",
                    }
                    return index, result
                except Exception as e:
                    result = {
                        "tool_call_id": tool_call["id"],
                        "role": "tool",
                        "content": f"错误：内置工具执行失败 - {str(e)}",
                    }
                    return index, result

            # 检查是否是 MCP 工具
            if "__" not in function_name:
                result = {
                    "tool_call_id": tool_call["id"],
                    "role": "tool",
                    "content": f"错误：函数名格式错误 {function_name}",
                }
                return index, result

            # 查找对应的 MCP Server 和工具
            if function_name not in self.tool_mapping:
                result = {
                    "tool_call_id": tool_call["id"],
                    "role": "tool",
                    "content": f"错误：未找到工具 {function_name}",
                }
                return index, result

            server_name, tool_name = self.tool_mapping[function_name]
            mcp_client = self.mcp_clients.get(server_name)

            if not mcp_client:
                result = {
                    "tool_call_id": tool_call["id"],
                    "role": "tool",
                    "content": f"错误：MCP Server {server_name} 未连接",
                }
                return index, result

            try:
                # 调用 MCP 工具，支持中断
                if stop_event.is_set():
                    result = {
                        "tool_call_id": tool_call["id"],
                        "role": "tool",
                        "content": "工具执行被用户中断",
                    }
                    return index, result

                # 添加超时控制
                result_content = await asyncio.wait_for(
                    mcp_client.call_tool(tool_name, arguments), timeout=TOOL_TIMEOUT
                )
                result = {
                    "tool_call_id": tool_call["id"],
                    "role": "tool",
                    "content": result_content,
                }
                return index, result
            except asyncio.TimeoutError:
                result = {
                    "tool_call_id": tool_call["id"],
                    "role": "tool",
                    "content": f"错误：MCP 工具执行超时（超过 {TOOL_TIMEOUT} 秒）",
                }
                return index, result
            except Exception as e:
                result = {
                    "tool_call_id": tool_call["id"],
                    "role": "tool",
                    "content": f"错误：工具执行失败 - {str(e)}",
                }
                return index, result

        # 串行执行工具调用，避免复杂的异步问题
        indexed_results = []

        for i, tc in enumerate(tool_calls):
            # 检查是否被中断
            if stop_event.is_set():
                interrupted = True  # 设置中断标志
                # 被中断，为剩余任务创建中断结果
                for j in range(i, len(tool_calls)):
                    indexed_results.append(
                        (
                            j,
                            {
                                "tool_call_id": tool_calls[j]["id"],
                                "role": "tool",
                                "content": "工具执行被中断",
                            },
                        )
                    )
                break

            try:
                # 串行执行单个工具
                result = await execute_single_tool(tc, i)
                indexed_results.append(result)
            except Exception as e:
                # 单个工具执行失败（异常信息已包含在返回结果中）
                indexed_results.append(
                    (
                        i,
                        {
                            "tool_call_id": tc["id"],
                            "role": "tool",
                            "content": f"工具执行异常: {str(e)}",
                        },
                    )
                )

        # 停止键盘监听
        stop_event.set()

        # 按原始顺序排序结果
        results = [None] * len(tool_calls)
        for idx, result in indexed_results:
            results[idx] = result

        return results, interrupted

    async def chat(self, message: str):
        """一次性对话，返回完整响应"""
        # 启动键盘监听
        self.start_keyboard_listener()

        try:
            # 更新 system prompt 为最新内容（包含工作目录、Git 分支、Memory.md）
            self._update_system_prompt()

            # 添加用户消息
            self.messages.append({"role": "user", "content": message})
            self._limit_messages()

            max_iterations = 10
            iteration = 0

            while iteration < max_iterations:
                iteration += 1

                # 检查是否被中断
                if self.interrupt_event.is_set():
                    print(f"\n{RED_CIRCLE} 对话被用户中断！")
                    print(f"{GREEN_CIRCLE} 您可以输入新指令继续对话")
                    break

                # 调用 LLM 获取完整响应
                message_obj, tool_calls_data = await self._call_llm()

                # 添加到消息历史
                self.messages.append(message_obj)

                # 输出推理过程（如果有）
                if "reasoning_content" in message_obj:
                    print(f"\033[90m{message_obj['reasoning_content']}\033[0m")

                # 初始化变量
                was_interrupted = False
                tool_results = []

                # 如果有工具调用，先执行工具，然后继续下一轮
                if tool_calls_data:
                    # 清除中断事件，准备执行工具
                    # 注意：必须在调用工具前清除，否则工具执行完成后设置的事件会导致下一轮误判为中断
                    self.interrupt_event.clear()

                    # 并行执行所有工具，支持中断
                    tool_results, was_interrupted = await self._execute_tool_calls(
                        tool_calls_data, self.interrupt_event
                    )

                    # 工具执行完成后，keyboard listener 已经被停止（interrupt_event 被设置）
                    # 清除中断事件，准备下一轮对话
                    # 注意：这里只清除事件，keyboard listener 会在下一轮对话开始时重新启动
                    self.interrupt_event.clear()

                # 检查是否被中断
                if was_interrupted:
                    print(f"\n{RED_CIRCLE} 工具执行被中断！")
                    print(f"{GREEN_CIRCLE} 您可以输入新指令继续对话")
                    self.messages.append(
                        {
                            "role": "system",
                            "content": "工具执行被用户中断，对话暂停等待新的指令。",
                        }
                    )
                    break

                # 如果有工具调用，输出工具结果并继续循环
                if tool_calls_data:
                    # 输出工具结果
                    for result in tool_results:
                        content = result["content"]
                        if len(content) > 2000:  # 截断过长的结果
                            content = content[:2000] + "..."
                        print(f"{content}")

                    # 添加工具结果到消息历史
                    self.messages.extend(tool_results)
                    self._limit_messages()
                    continue  # 继续下一轮对话
                else:
                    # 没有工具调用，输出 content 并结束对话
                    if "content" in message_obj:
                        print(f"\n{WHITE_CIRCLE} {message_obj['content']}")
                    break

        except asyncio.CancelledError:
            print(f"\n{RED_CIRCLE} LLM请求被中断！")
            print(f"{GREEN_CIRCLE} 您可以输入新指令继续对话")
        finally:
            # 停止键盘监听
            self.stop_keyboard_listener()


def parse_mcp_config(config_path: str) -> dict[str, Any]:
    """解析 mcp-claude-code.json 配置文件"""
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
    config_path = Path(__file__).parent / "mcp-claude-code.json"

    # 初始化 MCP 服务器
    print("正在初始化 MCP 服务器...\n")
    mcp_clients = await initialize_mcp_servers(str(config_path))

    if not mcp_clients:
        print("没有可用的 MCP 服务器，退出。")
        return

    # 创建 ChatBot
    work_dir = str(Path(config_path).parent.parent)
    chatbot = FunctionCallingChatBot(api_key, mcp_clients, work_dir)

    print(f"\n{'='*60}")
    print(f"已加载 {len(chatbot.tools)} 个工具:")
    for tool in chatbot.tools:
        print(f"  - {tool['function']['name']}: {tool['function']['description']}")
    print(f"{'='*60}")
    print(f"💡 提示：在工具执行过程中按 ESC 键可以中断执行，然后输入新指令继续")
    print(f"💡 按 Ctrl+C 可以退出程序")
    print()

    try:
        # 交互式对话
        while True:
            user_input = input("> ").strip()

            if user_input.lower() in ["exit", "quit", "退出"]:
                print("\n再见！")
                break

            if not user_input:
                continue

            await chatbot.chat(user_input)

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
