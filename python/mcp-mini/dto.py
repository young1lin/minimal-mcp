import uuid
from typing import Any
from pydantic import BaseModel, ConfigDict, model_validator
from typing_extensions import Self


class JSONRPCRequest(BaseModel):
    """JSON RPC Request Message"""

    model_config = ConfigDict(extra="ignore", use_enum_values=True)

    method: str
    params: dict[str, Any] | None = None
    id: str | int | None = None
    jsonrpc: str = "2.0"

    @model_validator(mode="after")
    def generate_id_if_none(self):
        if self.id is None:
            self.id = str(uuid.uuid4())
        return self

    def to_json(self) -> str:
        """Convert to JSON string"""
        return self.model_dump_json(exclude_none=True, by_alias=True)


class JSONRPCError(BaseModel):
    """JSON RPC Error object"""

    model_config = ConfigDict(extra="ignore")

    code: int
    message: str
    data: Any | None = None


class JSONRPCResult(BaseModel):
    """JSON RPC Response Message"""

    model_config = ConfigDict(extra="ignore")

    id: str | int | None = None
    result: dict[str, Any] | None = None
    error: JSONRPCError | None = None
    jsonrpc: str = "2.0"

    @property
    def is_error(self) -> bool:
        """Check if this is an error response"""
        return self.error is not None

    @classmethod
    def from_json(cls, json_response: str) -> Self:
        """Create from JSON string"""
        return cls.model_validate_json(json_response)

    def to_json(self) -> str:
        """Convert to JSON string"""
        return self.model_dump_json(exclude_none=True, by_alias=True)


class ClientInfo(BaseModel):
    """Client information"""

    model_config = ConfigDict(extra="ignore")

    name: str = "Fake-Cline"
    version: str = "0.0.1-SNAPSHOT"
    title: str | None = "Fake-Cline MCP Client"


class ServerInfo(BaseModel):
    """Server information"""

    model_config = ConfigDict(extra="ignore")

    name: str = "Fake-Weather-Server"
    version: str = "0.0.1-SNAPSHOT"
    title: str | None = "Fake-Weather-Server MCP Server"


class Capabilities(BaseModel):
    """MCP Capabilities"""

    model_config = ConfigDict(extra="ignore")

    roots: dict[str, bool] | None = None
    sampling: dict[str, Any] | None = None
    elicitation: dict[str, Any] | None = None
    logging: dict[str, bool] | None = None
    prompts: dict[str, bool] | None = None
    resources: dict[str, bool] | None = None
    tools: dict[str, bool] | None = None
    completions: dict[str, bool] | None = None
    experimental: dict[str, bool] | None = None


class InitializeJSONRPCRequest(JSONRPCRequest):
    """Initialize JSON RPC Request"""

    def __init__(self, id: str | int | None = None, **data):
        params = {
            "protocolVersion": "2024-11-05",
            "capabilities": Capabilities(roots={"listChanged": True}),
            "clientInfo": ClientInfo(),
        }
        super().__init__(method="initialize", params=params, id=id, **data)


class InitializeJSONRPCResult(JSONRPCResult):
    """Initialize JSON RPC Result"""

    def __init__(self, id: str | int | None = None, is_error: bool = False, **data):
        # 如果 result 已经在 data 中（从 JSON 解析），直接使用父类初始化
        if "result" in data or "error" in data:
            super().__init__(id=id, **data)
        else:
            # 否则使用自定义逻辑创建
            if is_error:
                result = None
                error = JSONRPCError(code=-1, message="Initialize error")
            else:
                capabilities = Capabilities(
                    tools={"listChanged": True},
                    logging={"listChanged": False},
                    prompts={"listChanged": False},
                    resources={"subscribe": False, "listChanged": False},
                    completions={"listChanged": False},
                    experimental={"listChanged": False},
                )
                result = {
                    "protocolVersion": "2024-11-05",
                    "capabilities": capabilities.model_dump(exclude_none=True),
                    "serverInfo": ServerInfo().model_dump(exclude_none=True),
                    "instructions": "Fake-Weather MCP Server",
                }
                error = None

            super().__init__(id=id, result=result, error=error, **data)


class ListToolsJSONRPCRequest(JSONRPCRequest):
    """list tools JSON RPC Request"""

    def __init__(self, id: str | int, cursor: str | None = None, **data):
        params = {}
        if cursor is not None:
            params["cursor"] = cursor
        super().__init__(
            method="tools/list", params=params if params else None, id=id, **data
        )


class ToolParameterProperty(BaseModel):
    """Tool parameter property definition"""

    model_config = ConfigDict(extra="allow")

    type: str | None = None
    description: str | None = None
    anyOf: list[dict[str, Any]] | None = None
    oneOf: list[dict[str, Any]] | None = None
    allOf: list[dict[str, Any]] | None = None


class ToolInputSchema(BaseModel):
    """Tool input schema definition"""

    model_config = ConfigDict(extra="ignore")

    type: str = "object"
    properties: dict[str, ToolParameterProperty]
    required: list[str] | None = None


class ToolOutputSchema(BaseModel):
    """Tool output schema definition"""

    model_config = ConfigDict(extra="ignore")

    type: str = "object"
    properties: dict[str, ToolParameterProperty]
    required: list[str] | None = None
    additionalProperties: bool = False


class ToolDefinition(BaseModel):
    """MCP Tool definition"""

    model_config = ConfigDict(extra="ignore")

    name: str
    description: str
    inputSchema: ToolInputSchema
    title: str | None = None
    outputSchema: ToolOutputSchema | None = None
    annotations: dict[str, Any] | None = None

    def to_json(self) -> str:
        """Convert to JSON string"""
        return self.model_dump_json(exclude_none=True, by_alias=True)


class ListToolsJSONRPCResult(JSONRPCResult):
    """list tools JSON RPC Response"""

    def __init__(
        self,
        id: str | int | None = None,
        tools: list[ToolDefinition] | None = None,
        nextCursor: str | None = None,
        is_error: bool = False,
        **data
    ):
        # 如果 result 已经在 data 中（从 JSON 解析），直接使用父类初始化
        if "result" in data or "error" in data:
            super().__init__(id=id, **data)
        else:
            # 否则使用自定义逻辑创建
            if is_error:
                error = JSONRPCError(code=-1, message="Failed to list tools")
                result = None
            else:
                error = None
                if tools is None:
                    tools = []
                result = {
                    "tools": [tool.model_dump(exclude_none=True) for tool in tools]
                }
                if nextCursor:
                    result["nextCursor"] = nextCursor

            super().__init__(id=id, result=result, error=error, **data)


class ToolContent(BaseModel):
    """Base tool content class"""

    model_config = ConfigDict(extra="ignore")

    type: str


class TextToolContent(ToolContent):
    """Text tool content"""

    model_config = ConfigDict(extra="ignore")

    text: str
    type: str = "text"

    def __init__(self, text: str, **data):
        super().__init__(text=text, type="text", **data)


class CallToolJSONRPCRequest(JSONRPCRequest):
    """Call tool JSON RPC Request"""

    def __init__(
        self,
        name: str,
        id: str | int = None,
        arguments: dict[str, Any] | None = None,
        **data
    ):
        params = {
            "name": name,
        }
        if arguments is not None:
            params["arguments"] = arguments

        super().__init__(method="tools/call", params=params, id=id, **data)


class CallToolJSONRPCResult(JSONRPCResult):
    """Call tool JSON RPC Response"""

    def __init__(
        self,
        id: str | int | None = None,
        content: list[ToolContent] | None = None,
        is_error: bool = False,
        error_message: str | None = None,
        **data
    ):
        # 如果 result 已经在 data 中（从 JSON 解析），直接使用父类初始化
        if "result" in data or "error" in data:
            super().__init__(id=id, **data)
        else:
            # 否则使用自定义逻辑创建
            if is_error:
                error = JSONRPCError(
                    code=-1, message=error_message or "Tool execution failed"
                )
                result = None
            else:
                error = None
                result = {
                    "content": [
                        item.model_dump(exclude_none=True) for item in (content or [])
                    ],
                    "isError": False,
                }

            super().__init__(id=id, result=result, error=error, **data)
