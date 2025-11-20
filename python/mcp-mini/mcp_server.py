import sys
import json
import signal
import os
import argparse
from typing import Any
from dto import (
    JSONRPCResult,
    JSONRPCError,
    ToolInputSchema,
    ToolDefinition,
    ToolParameterProperty,
    ListToolsJSONRPCResult,
    CallToolJSONRPCResult,
    TextToolContent,
    InitializeJSONRPCResult,
)
import logging
import inspect

# from collections.abc import Callable
from typing import Callable

# 在 Windows 上强制使用 UTF-8 编码
if sys.platform == "win32":
    # 重新配置 stdout 和 stdin 为 UTF-8
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stdin, "reconfigure"):
        sys.stdin.reconfigure(encoding="utf-8", errors="replace")


api_key = os.getenv("FAKE_CLINE_WEATHER_API_KEY", "test-key-123")

# 获取脚本所在目录
script_dir = os.path.dirname(os.path.abspath(__file__))
log_file = os.path.join(script_dir, "mcp_server.log")

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(log_file, encoding="utf-8")],
)
logger = logging.getLogger(__name__)

logger.info(f"api_key: {api_key}")


class Tool:
    def __init__(
        self,
        name: str,
        arguments: dict[str, Any],
        description: str,
        required_arguments: list[str],
        func: Callable[..., Any],
    ):
        self.name: str = name
        self.arguments: dict[str, Any] = arguments
        self.description: str = description
        self.required_arguments: list[str] = required_arguments
        self.func: Callable[..., Any] = func


class SimpleTool:
    def __init__(
        self,
        name: str,
        arguments: dict[str, Any],
        description: str,
        required_arguments: list[str],
        func: callable,
    ):
        self.name: str = name
        self.arguments: dict[str, Any] = arguments
        self.description: str = description
        self.required_arguments: list[str] = required_arguments
        self.func: callable = func


def tool(
    description: str, required_arguments: list[str] | None = None
) -> Callable[[callable], SimpleTool]:
    if required_arguments is None:
        required_arguments = []

    def decorator(func):
        return SimpleTool(
            name=func.__name__,
            description=description,
            arguments=func.__annotations__,
            required_arguments=required_arguments,
            func=func,
        )

    return decorator


class JsonRPCServer:
    def __init__(self):
        self.methods: dict[str, callable] = {}
        self.running: bool = True
        # 处理终止信号
        if sys.platform != "win32":
            _ = signal.signal(signal.SIGTERM, self._handle_signal)
            _ = signal.signal(signal.SIGINT, self._handle_signal)

    def _handle_signal(self, signal_num: int, frame):
        self.running = False
        logger.info(f"Server received signal {signal_num}, shutting down")
        sys.exit(0)

    def register_method(self, name: str, method: callable):
        self.methods[name] = method

    def process_request(self, request: dict[str, Any]) -> str | None:
        """
        Process a json rpc request

        Args:
            request (dict): json rpc request

        Returns:
            str: json rpc response
        """
        if request.get("jsonrpc") != "2.0":
            return self._error_response(request.get("id"), -32600, "Invalid Request")

        method = request.get("method")
        params: dict[str, Any] = request.get("params", {})
        request_id = request.get("id")

        # 如果没有id，这是一个通知
        if request_id is None:
            logger.info(f"Received notification: {method}, do nothing")
            # For notifications, we still process but don't send response
            if method in self.methods:
                try:
                    # 获取方法签名并过滤参数
                    func = self.methods[method]
                    sig = inspect.signature(func)
                    filtered_params = {}

                    for key, value in params.items():
                        if key in sig.parameters:
                            filtered_params[key] = value
                        else:
                            logger.debug(
                                f"Filtering out parameter '{key}' for method '{method}'"
                            )

                    func(**filtered_params)
                except Exception as e:
                    logger.error(f"Error processing notification {method}: {str(e)}")
            return None

        # 处理请求
        logger.info(f"Processing request for method: {method}, id: {request_id}")
        if method not in self.methods:
            logger.error(f"Method not found: {method}")
            return self._error_response(request_id, -32601, "Method not found")

        try:
            func = self.methods[method]

            # 智能参数过滤：只传递函数实际接受的参数
            sig = inspect.signature(func)
            filtered_params = {}
            extra_params = {}

            for key, value in params.items():
                if key in sig.parameters:
                    filtered_params[key] = value
                elif "**" in str(sig):  # 如果函数有 **kwargs
                    filtered_params[key] = value
                else:
                    extra_params[key] = value
                    logger.debug(
                        f"Parameter '{key}' not accepted by method '{method}', filtering out"
                    )

            if extra_params:
                logger.info(
                    f"Filtered parameters for {method}: {list(extra_params.keys())}"
                )

            result = func(**filtered_params)

            # Check if result is already a JSONRPCResult object
            if isinstance(result, JSONRPCResult):
                result.id = request_id
                return result.to_json()
            else:
                return JSONRPCResult(id=request_id, result=result).to_json()

        except Exception as e:
            logger.error(
                f"Internal error processing method {method}: {str(e)}", exc_info=True
            )
            return self._error_response(request_id, -32603, f"Internal error: {str(e)}")

    def _error_response(
        self, request_id: str | int | None, code: int, message: str
    ) -> str:
        """生成错误响应"""
        return JSONRPCResult(
            id=request_id, error=JSONRPCError(code=code, message=message)
        ).to_json()

    def start(self):
        """
        Start the server
        """
        while self.running:
            try:
                # 从标准输入读取一行数据，如果没有，就一直等待
                line = sys.stdin.readline()
                if not line:
                    break

                line = line.strip()
                if not line:
                    continue

                logger.debug(f"Received line: {line}")
                request = json.loads(line)
                response: str = self.process_request(request)

                if response is not None:
                    response_line = response + "\n"
                    sys.stdout.write(response_line)
                    sys.stdout.flush()

            except json.JSONDecodeError:
                error = self._error_response(None, -32700, "Parse error")
                sys.stdout.write(error + "\n")
                sys.stdout.flush()
            except (EOFError, KeyboardInterrupt):
                logger.info("Server interrupted")
                break
            except Exception as e:
                logger.error(f"Unexpected error: {e}", exc_info=True)

        logger.info("Server shutting down")


class ServerSession:
    def __init__(self, other_api: Any):
        self.other_api = other_api
        self.records: list[str] = []

    @tool(description="Get the weather of a location", required_arguments=["location"])
    def get_weather(self, location: str) -> str:
        """
        Get the weather of a location
        Args:
            location (str, required): The location to get weather for, only support English Name of the location, like "Beijing" or "Shanghai" or "Hangzhou"
        Returns:
            The weather of the location
        """
        logger.info(f"get_weather called with location: {location}")
        self.records.append(location)

        if location is None or location.strip() == "":
            return "Location is required"

        location = location.strip()
        result = f"The weather of {location} is unspported, please try another location"

        if location.lower() == "beijing":
            result = "The weather of Beijing is sunny, 25°C"
        elif location.lower() == "shanghai":
            result = "The weather of Shanghai is cloudy, 22°C"
        elif location.lower() == "hangzhou":
            result = "The weather of Hangzhou is rainy, 29°C, 80% humidity, wind 10km/h"
        elif location.lower() == "nyc":
            result = """The weather of NYC is
                        67°F°C
                        Precipitation: 0%
                        Humidity: 68%
                        Wind: 6 mph
                        """

        logger.info(f"get_weather returning: {result}")
        return result

    @tool(description="List all get weather records")
    def list_get_weather_records(self) -> list[str]:
        logger.info(f"list_get_weather_records called, returning: {self.records}")
        return self.records.copy()


class McpServer:
    def __init__(self, tools: list[SimpleTool], session: ServerSession = None):
        # Convert SimpleTool to Tool objects
        tool_objects: list[Tool] = []
        for simple_tool in tools:
            tool_obj: Tool = Tool(
                name=simple_tool.name,
                arguments=simple_tool.arguments,
                description=simple_tool.description,
                required_arguments=simple_tool.required_arguments,
                func=simple_tool.func,
            )
            tool_objects.append(tool_obj)

        # Convert Tool objects to ToolDefinition objects
        tool_definitions: list[ToolDefinition] = []
        for tool_obj in tool_objects:
            # Parse docstring to get parameter descriptions
            param_descriptions = self._parse_docstring_params(tool_obj.func)

            # Convert function annotations to ToolParameterProperty objects
            properties = {}
            for param_name, param_type in tool_obj.arguments.items():
                if param_name != "return":  # Skip return annotation
                    # Use description from docstring if available, otherwise use default
                    description = param_descriptions.get(
                        param_name, f"Parameter {param_name}"
                    )
                    properties[param_name] = ToolParameterProperty(
                        type=self._get_type_string(param_type),
                        description=description,
                    )

            input_schema = ToolInputSchema(
                type="object",
                properties=properties,
                required=(
                    tool_obj.required_arguments if tool_obj.required_arguments else []
                ),
            )

            tool_def = ToolDefinition(
                name=tool_obj.name,
                description=tool_obj.description,
                inputSchema=input_schema,
            )
            tool_definitions.append(tool_def)

        self.tools = tool_definitions
        self.tool_funcs = {tool_obj.name: tool_obj.func for tool_obj in tool_objects}
        self.session = session

        logger.info(f"McpServer initialized with tools: {[t.name for t in self.tools]}")

    def _parse_docstring_params(self, func: callable) -> dict[str, str]:
        """
        Parse parameter descriptions from function docstring.
        Supports Google-style docstrings with Args section.

        Returns:
            dict mapping parameter names to their descriptions
        """
        docstring = inspect.getdoc(func)
        if not docstring:
            return {}

        param_descriptions = {}
        lines = docstring.split("\n")
        in_args_section = False

        for i, original_line in enumerate(lines):
            line = original_line.strip()

            # Check if we're entering Args section
            if line.lower().startswith("args:"):
                in_args_section = True
                continue

            # Check if we're leaving Args section (next section starts)
            if in_args_section:
                # Check if this is a new section (not indented and contains ':')
                if (
                    line
                    and not original_line.startswith(" ")
                    and not original_line.startswith("\t")
                ):
                    if ":" in line:
                        # This might be a new section (like Returns:)
                        if any(
                            keyword in line.lower()
                            for keyword in [
                                "returns:",
                                "yields:",
                                "raises:",
                                "note:",
                                "example:",
                                "see also:",
                            ]
                        ):
                            break

                # Parse parameter line
                # Format: param_name (type, optional/required): description
                # or: param_name: description
                # Parameter lines typically have ':' and start with a parameter name
                if ":" in line:
                    # Extract parameter name and description
                    parts = line.split(":", 1)
                    if len(parts) == 2:
                        param_part = parts[0].strip()
                        description = parts[1].strip()

                        # Extract parameter name (handle formats like "param_name (type, required)")
                        if "(" in param_part:
                            param_name = param_part.split("(")[0].strip()
                        else:
                            param_name = param_part.strip()

                        # Only add if it looks like a parameter (starts with letter or underscore)
                        if param_name and (
                            param_name[0].isalpha() or param_name[0] == "_"
                        ):
                            param_descriptions[param_name] = description

        return param_descriptions

    def _get_type_string(self, param_type) -> str:
        """Convert Python type annotation to JSON schema type string"""
        if param_type is None:
            return "string"

        if hasattr(param_type, "__name__"):
            type_name = param_type.__name__
            if type_name == "str":
                return "string"
            elif type_name == "int":
                return "integer"
            elif type_name == "float":
                return "number"
            elif type_name == "bool":
                return "boolean"
            elif type_name == "list":
                return "array"
            else:
                return "string"  # default fallback
        else:
            # Handle generic types like list[str]
            type_str = str(param_type)
            if "list" in type_str.lower():
                return "array"
            return "string"  # default fallback

    def initialize(
        self, protocolVersion: str, capabilities: dict = None, clientInfo: dict = None
    ) -> InitializeJSONRPCResult:
        """Initialize the server"""
        logger.info(
            f"initialize called with protocolVersion: {protocolVersion}, capabilities: {capabilities}, clientInfo: {clientInfo}"
        )
        return InitializeJSONRPCResult(id=None, is_error=False)

    def notify_initialize(self) -> None:
        logger.info("recevice [notifications/initialized], just ack mechanism")

    def list_tools(self, cursor: str | None = None) -> ListToolsJSONRPCResult:
        """List all available tools"""
        logger.info(f"list_tools called with cursor: {cursor}, tools: {self.tools}")
        # For now, we don't support pagination, so cursor is ignored
        return ListToolsJSONRPCResult(
            id=None,  # This will be set by the calling code
            tools=self.tools,
            nextCursor=None,  # No pagination for now
            is_error=False,
        )

    def call_tool(
        self, name: str, arguments: dict | None = None
    ) -> CallToolJSONRPCResult:
        """Call a tool with the given arguments"""
        try:
            if name not in self.tool_funcs:
                logger.error(f"Tool '{name}' not found")
                return CallToolJSONRPCResult(
                    id=None,  # This will be set by the calling code
                    content=None,
                    is_error=True,
                    error_message=f"Tool '{name}' not found",
                )

            # Get the tool function
            tool_func = self.tool_funcs[name]

            # Prepare arguments
            if arguments is None:
                arguments = {}

            # Call the tool function
            if self.session is not None:
                result = tool_func(self.session, **arguments)
            else:
                result = tool_func(**arguments)
            # Convert result to TextToolContent
            content = [TextToolContent(text=str(result))]

            return CallToolJSONRPCResult(
                id=None,  # This will be set by the calling code
                content=content,
                is_error=False,
            )

        except Exception as e:
            logger.error(f"Tool '{name}' execution failed: {str(e)}", exc_info=True)
            return CallToolJSONRPCResult(
                id=None,  # This will be set by the calling code
                content=None,
                is_error=True,
                error_message=f"Tool execution failed: {str(e)}",
            )

    def notify_tool_change(self):
        logger.info("Tool list changed notification received")

    # TODO to be supported
    def list_prompts(self, cursor: str | None = None):
        logger.info("list_prompts called (not implemented)")
        return {"prompts": []}

    # TODO to be supported
    def get_prompt(self, name: str):
        logger.info(f"get_prompt called for '{name}' (not implemented)")
        return None

    # TODO to be supported
    def notify_prompt_change(self):
        logger.info("notify_prompt_change called (not implemented)")

    # TODO to be supported
    def list_resources(self, cursor: str | None = None):
        logger.info("list_resources called (not implemented)")
        return {"resources": []}

    # TODO to be supported
    def list_capabilities(self):
        logger.info("list_capabilities called (not implemented)")
        return {}


if __name__ == "__main__":
    logger.info("=" * 50)
    logger.info("Starting MCP Server...")
    logger.info("=" * 50)

    # 使用 argparse 进行更优雅的参数处理
    parser = argparse.ArgumentParser(description="MCP Server 参数配置")
    parser.add_argument("--arg1", help="第一个参数")
    parser.add_argument("--arg2", help="第二个参数")

    args = parser.parse_args()

    # 打印参数信息
    if args.arg1 is not None:
        logger.info(f"参数1: {args.arg1}")
    else:
        logger.info("没有提供参数1")

    if args.arg2 is not None:
        logger.info(f"参数2: {args.arg2}")
    else:
        logger.info("没有提供参数2")

    session = ServerSession(None)

    mcp_server = McpServer(
        tools=[session.get_weather, session.list_get_weather_records], session=session
    )

    # 创建 JSON RPC Server
    server = JsonRPCServer()

    # 注册方法
    server.register_method("initialize", mcp_server.initialize)
    server.register_method("notifications/initialized", mcp_server.notify_initialize)
    server.register_method("tools/list", mcp_server.list_tools)
    server.register_method("tools/call", mcp_server.call_tool)

    # Notifications (these don't return responses)
    server.register_method(
        "notifications/tools/list_changed", mcp_server.notify_tool_change
    )
    server.register_method(
        "notifications/prompts/list_changed", mcp_server.notify_prompt_change
    )

    # Other methods that might be called
    server.register_method("prompts/list", mcp_server.list_prompts)
    server.register_method("prompts/get", mcp_server.get_prompt)
    server.register_method("resources/list", mcp_server.list_resources)

    logger.info("All methods registered, server starting...")
    logger.info(f"Registered methods: {list(server.methods.keys())}")

    try:
        server.start()
    except Exception as e:
        logger.error(f"Server error: {e}", exc_info=True)
    finally:
        logger.info("Server shutting down")
        sys.exit(0)
