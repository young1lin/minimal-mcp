from enum import Enum
import subprocess
import json
import asyncio
import logging
from dataclasses import dataclass
from abc import ABC, abstractmethod
from typing import Any, final, override, Literal
from .common_type import *


STDIO = "stdio"
STREAMABLE_HTTP = "streamable-http"
WEBSOCKET = "websocket"


class Status(Enum):
    CONNECTED = "connected"
    CONNECTING = "connecting"
    DISCONNECTED = "disconnected"


class McpServerConfig(ABC):
    def __init__(self):
        pass


# only support stdio transport
@final
class StdioMcpServerConfig(McpServerConfig):
    command: str
    args: list[str]
    env: dict[str, str]

    def __init__(self, command: str, args: list[str], env: dict[str, str]):
        self.command = command
        self.args = args
        self.env = env


@dataclass
class McpServer:
    name: str
    config: McpServerConfig
    status: Status
    tools: list[ToolDefinition]
    disabled: bool = False

    # 这里为了简单，prompts，resources 就丢了
    def __init__(
        self,
        name: str,
        config: McpServerConfig,
        status: Status,
        tools: list[ToolDefinition],
        disabled: bool = False,
    ):
        """
        MCP Server

        Args:
            name (str): MCP Server name
            config (McpServerConfig): MCP Server config
            status (Status): MCP Server status
            tools (list[ToolDefinition]): MCP Server tools
            disabled (bool, optional): MCP Server disabled. Defaults to False.
        """
        self.name = name
        self.config = config
        self.status = status
        self.tools = tools
        self.disabled = disabled


@final
class StdioMcpServer(McpServer):
    def __init__(
        self,
        name: str,
        config: StdioMcpServerConfig,
        status: Status,
        tools: list[ToolDefinition],
        disabled: bool = False,
    ):
        super().__init__(name, config, status, tools, disabled)


class Transport(ABC):

    def __init__(self, transport_type: Literal[STDIO, STREAMABLE_HTTP, WEBSOCKET]):
        self.transport_type = transport_type

    @abstractmethod
    def start(self):
        pass

    @abstractmethod
    def close(self):
        pass

    @abstractmethod
    def send(self, message: JSONRPCRequest, timeout: int = 10000) -> JSONRPCResult:
        pass


@dataclass
class StdioTransport(Transport):
    command: str
    args: list[str]
    env: dict[str, str]
    is_started: bool

    def __init__(self, command: str, args: list[str], env: dict[str, str]):
        super().__init__(STDIO)
        self.command = command
        self.args = args
        self.env = env
        self.is_started = False

    @override
    def start(self):
        """
        Start the transport
        """
        if self.is_started:
            return
        self.is_started = True
        self.process: subprocess.Popen[Any] = subprocess.Popen(
            args=[self.command] + self.args,  # 明确指定args参数
            env=self.env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            universal_newlines=True,
        )

    @override
    def close(self):
        if not self.is_started:
            return
        self.is_started = False
        if self.process:
            if self.process.stdin:
                self.process.stdin.close()
                # 在Windows上需要显式等待stdin关闭
                try:
                    self.process.stdin.close()
                except:
                    pass
            if self.process.stdout:
                self.process.stdout.close()
            if self.process.stderr:
                self.process.stderr.close()
            self.process.terminate()
            _ = self.process.wait()

    # TODO implements timeout
    @override
    async def send(
        self, message: JSONRPCRequest, timeout: int = 10000
    ) -> JSONRPCResult | None:
        request_line = message.to_json() + "\n"
        self.process.stdin.write(request_line)
        self.process.stdin.flush()

        # 读取响应
        response_line = self.process.stdout.readline()
        if response_line:
            return JSONRPCResult.from_json(response_line.strip())
        return None


class MCPClient:
    """
    MCP Client
    """

    def __init__(self, transport: Transport, timeout: int = 10000):
        self.transport = transport
        self.timeout = timeout

    def list_tools(self) -> ListToolsJSONRPCResult:
        return self.transport.send(ListToolsJSONRPCRequest(id=None), self.timeout)

    def call_tool(self, tool_name: str, tool_arguments: dict) -> CallToolJSONRPCResult:
        return self.transport.send(
            CallToolJSONRPCRequest(None, tool_name, tool_arguments), self.timeout
        )


@dataclass
class Connection:
    server: McpServer
    client: MCPClient
    transport: Transport

    def __init__(self, server: McpServer, client: MCPClient, transport: Transport):
        self.server = server
        self.client = client
        self.transport = transport


class MCPHub:

    mcp_json_config: str
    connections: list[Connection]

    def __init__(self, mcp_json_config: str = "mcp.json"):
        self.mcp_json_config = mcp_json_config
        self.connections = []
        self._load_config()

    def _load_config(self):
        with open(self.mcp_json_config, "r") as f:
            config = json.load(f)

        # 遍历字典的键值对
        for name, server_config in config["mcpServers"].items():
            server_type = server_config["type"]  # 现在使用 server_config 而不是 server
            transport: Transport = None
            server: McpServer = None
            client: MCPClient = None

            if server_type == STDIO:
                server_config_obj = StdioMcpServerConfig(
                    server_config["command"],
                    server_config["args"],
                    server_config["env"],
                )
                transport: StdioTransport = StdioTransport(
                    server_config_obj.command,
                    server_config_obj.args,
                    server_config_obj.env,
                )
                transport.start()
                client = MCPClient(transport)
                server = McpServer(
                    name,
                    server_config_obj,
                    Status.CONNECTED,
                    [],
                    False,
                )
            else:
                raise ValueError(f"Unsupported server type: {server_type}")

            self.connections.append(Connection(server, client, transport))

    def get_connections(self) -> list[Connection]:
        """获取所有连接

        Returns:
            list[Connection]: _description_
        """
        return self.connections

    def get_servers(self) -> list[McpServer]:
        """获取所有服务器

        Returns:
            list[McpServer]: _description_
        """
        return [connection.server for connection in self.connections]

    async def delete_connection(self, name: str) -> None:
        """删除指定名称的连接

        Args:
            name (str): _description_

        Returns:
            None: _description_
        """
        connection = next(
            (conn for conn in self.connections if conn.server.name == name), None
        )

        if connection:
            try:
                # 关闭传输和客户端连接
                await connection.transport.close()
                await connection.client.close()
            except Exception as error:
                logging.error(f"Failed to close transport for {name}: {error}")

            # 从连接列表中移除该连接
            self.connections = [
                conn for conn in self.connections if conn.server.name != name
            ]

    async def dispose(self):
        # 创建所有删除连接的任务
        tasks = [
            self.delete_connection(connection.server.name)
            for connection in self.connections.copy()
        ]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
