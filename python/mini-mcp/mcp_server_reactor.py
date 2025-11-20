"""
MCP Server - Optimized with Reactor Pattern
"""

import sys
import json
import signal
import os
import argparse
import asyncio
import logging
import inspect
from typing import Any, Dict, Optional, Callable, List, Union
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
from functools import wraps
from dataclasses import dataclass, field
from enum import Enum
import traceback

from .common_type import (
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


# ========================= Configuration =========================
@dataclass
class ServerConfig:
    """Server configuration"""

    api_key: str = field(
        default_factory=lambda: os.getenv("FAKE_CLINE_WEATHER_API_KEY", "test-key-123")
    )
    log_level: str = "DEBUG"
    log_file: Optional[str] = None
    max_workers: int = 4
    request_timeout: float = 30.0
    enable_metrics: bool = True

    def __post_init__(self):
        if self.log_file is None:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            self.log_file = os.path.join(script_dir, "mcp_server.log")


# ========================= Logging Setup =========================
class LoggerFactory:
    """Factory for creating configured loggers"""

    @staticmethod
    def create_logger(name: str, config: ServerConfig) -> logging.Logger:
        logger = logging.getLogger(name)
        logger.setLevel(getattr(logging, config.log_level))

        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s"
        )

        # File handler
        if config.log_file:
            file_handler = logging.FileHandler(config.log_file, encoding="utf-8")
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)

        # Console handler
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

        return logger


# ========================= Request Processing =========================
class RequestType(Enum):
    """Types of JSON-RPC requests"""

    METHOD = "method"
    NOTIFICATION = "notification"
    BATCH = "batch"


@dataclass
class Request:
    """Encapsulates a JSON-RPC request"""

    id: Optional[Union[str, int]]
    method: str
    params: Dict[str, Any]
    type: RequestType
    raw_data: Dict[str, Any]

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Request":
        """Create Request from dictionary"""
        request_id = data.get("id")
        method = data.get("method", "")
        params = data.get("params", {})

        # Determine request type
        if request_id is None:
            request_type = RequestType.NOTIFICATION
        else:
            request_type = RequestType.METHOD

        return cls(
            id=request_id,
            method=method,
            params=params,
            type=request_type,
            raw_data=data,
        )


@dataclass
class Response:
    """Encapsulates a JSON-RPC response"""

    id: Optional[Union[str, int]]
    result: Optional[Dict[str, Any]] = None
    error: Optional[JSONRPCError] = None

    def to_json(self) -> str:
        """Convert to JSON string"""
        return JSONRPCResult(id=self.id, result=self.result, error=self.error).to_json()


# ========================= Handler Interface =========================
class IRequestHandler(ABC):
    """Abstract interface for request handlers"""

    @abstractmethod
    async def can_handle(self, request: Request) -> bool:
        """Check if this handler can process the request"""
        pass

    @abstractmethod
    async def handle(self, request: Request) -> Optional[Response]:
        """Handle the request and return response"""
        pass


# ========================= Method Registry =========================
class MethodRegistry:
    """Registry for managing RPC methods"""

    def __init__(self, logger: logging.Logger):
        self._methods: Dict[str, Callable] = {}
        self._logger = logger

    def register(self, name: str, method: Callable) -> None:
        """Register a method"""
        self._logger.debug(f"Registering method: {name}")
        self._methods[name] = method

    def unregister(self, name: str) -> None:
        """Unregister a method"""
        if name in self._methods:
            self._logger.debug(f"Unregistering method: {name}")
            del self._methods[name]

    def get(self, name: str) -> Optional[Callable]:
        """Get a method by name"""
        return self._methods.get(name)

    def exists(self, name: str) -> bool:
        """Check if method exists"""
        return name in self._methods

    @property
    def methods(self) -> List[str]:
        """Get list of registered methods"""
        return list(self._methods.keys())


# ========================= Request Handlers =========================
class MethodHandler(IRequestHandler):
    """Handler for regular method calls"""

    def __init__(self, registry: MethodRegistry, logger: logging.Logger):
        self._registry = registry
        self._logger = logger

    async def can_handle(self, request: Request) -> bool:
        return request.type == RequestType.METHOD

    async def handle(self, request: Request) -> Optional[Response]:
        """Handle method request"""
        if not self._registry.exists(request.method):
            self._logger.error(f"Method not found: {request.method}")
            return Response(
                id=request.id,
                error=JSONRPCError(code=-32601, message="Method not found"),
            )

        method = self._registry.get(request.method)

        try:
            # Filter parameters based on method signature
            filtered_params = self._filter_params(method, request.params)

            # Execute method
            if asyncio.iscoroutinefunction(method):
                result = await method(**filtered_params)
            else:
                result = await asyncio.get_event_loop().run_in_executor(
                    None, method, **filtered_params
                )

            # Handle result
            if isinstance(result, JSONRPCResult):
                result.id = request.id
                return Response(id=result.id, result=result.result, error=result.error)
            else:
                return Response(id=request.id, result=result)

        except Exception as e:
            self._logger.error(
                f"Error executing method {request.method}: {str(e)}", exc_info=True
            )
            return Response(
                id=request.id,
                error=JSONRPCError(code=-32603, message=f"Internal error: {str(e)}"),
            )

    def _filter_params(
        self, method: Callable, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Filter parameters based on method signature"""
        sig = inspect.signature(method)
        filtered = {}

        for key, value in params.items():
            if key in sig.parameters:
                filtered[key] = value
            elif any(
                p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()
            ):
                # Method accepts **kwargs
                filtered[key] = value
            else:
                self._logger.debug(
                    f"Filtering out parameter '{key}' for method '{method.__name__}'"
                )

        return filtered


class NotificationHandler(IRequestHandler):
    """Handler for notifications (no response expected)"""

    def __init__(self, registry: MethodRegistry, logger: logging.Logger):
        self._registry = registry
        self._logger = logger

    async def can_handle(self, request: Request) -> bool:
        return request.type == RequestType.NOTIFICATION

    async def handle(self, request: Request) -> Optional[Response]:
        """Handle notification (returns None)"""
        self._logger.info(f"Received notification: {request.method}")

        if self._registry.exists(request.method):
            method = self._registry.get(request.method)

            try:
                # Filter parameters
                sig = inspect.signature(method)
                filtered_params = {
                    k: v for k, v in request.params.items() if k in sig.parameters
                }

                # Execute method without waiting for result
                if asyncio.iscoroutinefunction(method):
                    asyncio.create_task(method(**filtered_params))
                else:
                    asyncio.get_event_loop().run_in_executor(
                        None, method, **filtered_params
                    )

            except Exception as e:
                self._logger.error(
                    f"Error processing notification {request.method}: {str(e)}",
                    exc_info=True,
                )

        return None  # Notifications don't return responses


# ========================= Reactor Pattern Implementation =========================
class Reactor:
    """Event-driven reactor for handling requests"""

    def __init__(self, config: ServerConfig, logger: logging.Logger):
        self._config = config
        self._logger = logger
        self._handlers: List[IRequestHandler] = []
        self._executor = ThreadPoolExecutor(max_workers=config.max_workers)
        self._running = False
        self._request_queue = asyncio.Queue()

    def register_handler(self, handler: IRequestHandler) -> None:
        """Register a request handler"""
        self._handlers.append(handler)

    async def process_request(self, request: Request) -> Optional[Response]:
        """Process a request through the handler chain"""
        for handler in self._handlers:
            if await handler.can_handle(request):
                try:
                    return await asyncio.wait_for(
                        handler.handle(request), timeout=self._config.request_timeout
                    )
                except asyncio.TimeoutError:
                    self._logger.error(f"Request timeout for {request.method}")
                    if request.type == RequestType.METHOD:
                        return Response(
                            id=request.id,
                            error=JSONRPCError(code=-32000, message="Request timeout"),
                        )
                    return None
                except Exception as e:
                    self._logger.error(f"Handler error: {e}", exc_info=True)
                    if request.type == RequestType.METHOD:
                        return Response(
                            id=request.id,
                            error=JSONRPCError(
                                code=-32603, message=f"Internal error: {str(e)}"
                            ),
                        )
                    return None

        # No handler found
        if request.type == RequestType.METHOD:
            return Response(
                id=request.id,
                error=JSONRPCError(code=-32601, message="Method not found"),
            )

        return None

    async def dispatch(self, data: Dict[str, Any]) -> Optional[str]:
        """Dispatch a request for processing"""
        # Validate JSON-RPC format
        if data.get("jsonrpc") != "2.0":
            return Response(
                id=data.get("id"),
                error=JSONRPCError(code=-32600, message="Invalid Request"),
            ).to_json()

        request = Request.from_dict(data)
        response = await self.process_request(request)

        if response:
            return response.to_json()

        return None

    def shutdown(self):
        """Shutdown the reactor"""
        self._running = False
        self._executor.shutdown(wait=True)


# ========================= Main Server =========================
class JsonRPCServer:
    """Main JSON-RPC server with reactor pattern"""

    def __init__(self, config: ServerConfig):
        self._config = config
        self._logger = LoggerFactory.create_logger(__name__, config)
        self._registry = MethodRegistry(self._logger)
        self._reactor = Reactor(config, self._logger)
        self._running = True

        # Setup handlers
        self._setup_handlers()

        # Setup signal handlers
        self._setup_signals()

    def _setup_handlers(self):
        """Setup request handlers"""
        self._reactor.register_handler(MethodHandler(self._registry, self._logger))
        self._reactor.register_handler(
            NotificationHandler(self._registry, self._logger)
        )

    def _setup_signals(self):
        """Setup signal handlers"""
        if sys.platform != "win32":
            signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT, self._handle_signal)

    def _handle_signal(self, signum: int, frame):
        """Handle shutdown signals"""
        self._logger.info(f"Received signal {signum}, shutting down...")
        self._running = False

    def register_method(self, name: str, method: Callable):
        """Register a method"""
        self._registry.register(name, method)

    async def _read_input(self) -> Optional[str]:
        """Read input from stdin asynchronously"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, sys.stdin.readline)

    async def _write_output(self, data: str):
        """Write output to stdout asynchronously"""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._write_sync, data)

    def _write_sync(self, data: str):
        """Synchronous write to stdout"""
        sys.stdout.write(data + "\n")
        sys.stdout.flush()

    async def _handle_request(self, line: str):
        """Handle a single request line"""
        try:
            request_data = json.loads(line)
            response = await self._reactor.dispatch(request_data)

            if response:
                await self._write_output(response)

        except json.JSONDecodeError:
            error_response = Response(
                id=None, error=JSONRPCError(code=-32700, message="Parse error")
            )
            await self._write_output(error_response.to_json())

        except Exception as e:
            self._logger.error(f"Unexpected error: {e}", exc_info=True)

    async def run(self):
        """Run the server"""
        self._logger.info("Server started")
        self._logger.info(f"Registered methods: {self._registry.methods}")

        try:
            while self._running:
                line = await self._read_input()

                if not line:
                    break

                line = line.strip()
                if not line:
                    continue

                self._logger.debug(f"Received: {line}")
                await self._handle_request(line)

        except (EOFError, KeyboardInterrupt):
            self._logger.info("Server interrupted")
        except Exception as e:
            self._logger.error(f"Server error: {e}", exc_info=True)
        finally:
            self._reactor.shutdown()
            self._logger.info("Server shutdown complete")


# ========================= Tool Decorator =========================
def tool(description: str, required_arguments: List[str] = None):
    """Decorator for creating tools"""
    if required_arguments is None:
        required_arguments = []

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        wrapper.tool_metadata = {
            "name": func.__name__,
            "description": description,
            "arguments": func.__annotations__,
            "required_arguments": required_arguments,
            "func": func,
        }

        return wrapper

    return decorator


# ========================= Session Management =========================
class ServerSession:
    """Session management for the server"""

    def __init__(self, config: ServerConfig, logger: logging.Logger):
        self._config = config
        self._logger = logger
        self.records: List[str] = []

    @tool(description="Get the weather of a location", required_arguments=["location"])
    def get_weather(self, location: str) -> str:
        """
        Get the weather of a location
        Args:
            location (str, required): The location to get weather for
        Returns:
            The weather of the location
        """
        self._logger.info(f"get_weather called with location: {location}")
        self.records.append(location)

        if not location or not location.strip():
            return "Location is required"

        location = location.strip().lower()

        weather_data = {
            "beijing": "The weather of Beijing is sunny, 25°C",
            "shanghai": "The weather of Shanghai is cloudy, 22°C",
            "hangzhou": "The weather of Hangzhou is rainy, 29°C, 80% humidity, wind 10km/h",
        }

        result = weather_data.get(
            location, f"The weather of {location.title()} is unknown"
        )

        self._logger.info(f"get_weather returning: {result}")
        return result

    @tool(description="List all get weather records")
    def list_get_weather_records(self) -> List[str]:
        """List all weather query records"""
        self._logger.info(f"list_get_weather_records called, returning: {self.records}")
        return self.records.copy()


# ========================= MCP Server Implementation =========================
class McpServer:
    """MCP Server implementation"""

    def __init__(
        self, tools: List[Callable], session: ServerSession, logger: logging.Logger
    ):
        self._logger = logger
        self._session = session
        self._tool_definitions = []
        self._tool_funcs = {}

        self._initialize_tools(tools)

    def _initialize_tools(self, tools: List[Callable]):
        """Initialize tools from functions"""
        for tool_func in tools:
            if not hasattr(tool_func, "tool_metadata"):
                self._logger.warning(f"Function {tool_func.__name__} is not a tool")
                continue

            metadata = tool_func.tool_metadata

            # Build properties
            properties = {}
            for param_name, param_type in metadata["arguments"].items():
                if param_name != "return":
                    properties[param_name] = ToolParameterProperty(
                        type=self._get_type_string(param_type),
                        description=f"Parameter {param_name}",
                    )

            # Create tool definition
            input_schema = ToolInputSchema(
                type="object",
                properties=properties,
                required=metadata["required_arguments"] or [],
            )

            tool_def = ToolDefinition(
                name=metadata["name"],
                description=metadata["description"],
                inputSchema=input_schema,
            )

            self._tool_definitions.append(tool_def)
            self._tool_funcs[metadata["name"]] = metadata["func"]

        self._logger.info(
            f"Initialized tools: {[t.name for t in self._tool_definitions]}"
        )

    def _get_type_string(self, param_type) -> str:
        """Convert Python type to JSON schema type"""
        type_mapping = {
            "str": "string",
            "int": "integer",
            "float": "number",
            "bool": "boolean",
            "list": "array",
            "dict": "object",
        }

        if param_type is None:
            return "string"

        type_name = getattr(param_type, "__name__", str(param_type))

        for py_type, json_type in type_mapping.items():
            if py_type in type_name.lower():
                return json_type

        return "string"  # Default

    def initialize(
        self, protocolVersion: str, capabilities: dict = None, clientInfo: dict = None
    ) -> InitializeJSONRPCResult:
        """Initialize the server"""
        self._logger.info(f"Initializing with protocol version: {protocolVersion}")
        return InitializeJSONRPCResult(id=None, is_error=False)

    def list_tools(self, cursor: str = None) -> ListToolsJSONRPCResult:
        """List available tools"""
        self._logger.debug(f"Listing tools, cursor: {cursor}")
        return ListToolsJSONRPCResult(
            id=None, tools=self._tool_definitions, nextCursor=None
        )

    def call_tool(self, name: str, arguments: dict = None) -> CallToolJSONRPCResult:
        """Call a tool"""
        try:
            if name not in self._tool_funcs:
                self._logger.error(f"Tool '{name}' not found")
                return CallToolJSONRPCResult(
                    id=None,
                    content=None,
                    is_error=True,
                    error_message=f"Tool '{name}' not found",
                )

            tool_func = self._tool_funcs[name]
            arguments = arguments or {}

            # Call the tool
            if self._session:
                result = tool_func(self._session, **arguments)
            else:
                result = tool_func(**arguments)

            # Convert result
            content = [TextToolContent(text=str(result))]

            return CallToolJSONRPCResult(id=None, content=content, is_error=False)

        except Exception as e:
            self._logger.error(f"Tool execution failed: {str(e)}", exc_info=True)
            return CallToolJSONRPCResult(
                id=None,
                content=None,
                is_error=True,
                error_message=f"Tool execution failed: {str(e)}",
            )


# ========================= Main Entry Point =========================
async def main():
    """Main entry point"""
    # Parse arguments
    parser = argparse.ArgumentParser(description="MCP Server")
    parser.add_argument("--arg1", help="First argument")
    parser.add_argument("--arg2", help="Second argument")
    parser.add_argument("--log-level", default="DEBUG", help="Log level")

    args = parser.parse_args()

    # Create configuration
    config = ServerConfig(log_level=args.log_level)

    # Create logger
    logger = LoggerFactory.create_logger("main", config)

    logger.info("=" * 50)
    logger.info("Starting MCP Server...")
    logger.info("=" * 50)

    if args.arg1:
        logger.info(f"Arg1: {args.arg1}")
    if args.arg2:
        logger.info(f"Arg2: {args.arg2}")

    # Create session
    session = ServerSession(config, logger)

    # Create MCP server
    mcp_server = McpServer(
        tools=[session.get_weather, session.list_get_weather_records],
        session=session,
        logger=logger,
    )

    # Create JSON-RPC server
    server = JsonRPCServer(config)

    # Register methods
    server.register_method("initialize", mcp_server.initialize)
    server.register_method("tools/list", mcp_server.list_tools)
    server.register_method("tools/call", mcp_server.call_tool)

    # Run server
    await server.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nServer stopped by user")
    except Exception as e:
        print(f"Fatal error: {e}", file=sys.stderr)
        sys.exit(1)
