import unittest
import json
import uuid
from typing import Any, Dict, List

# 假设您的模型代码保存在 common_type.py 文件中
from .common_type import *


class TestJSONRPCRequest(unittest.TestCase):
    """测试 JSONRPCRequest 类"""

    def test_basic_request_creation(self):
        """测试基本请求创建"""
        request = JSONRPCRequest(method="test_method")

        self.assertEqual(request.method, "test_method")
        self.assertEqual(request.jsonrpc, "2.0")
        self.assertIsNotNone(request.id)  # 应该自动生成 ID
        self.assertIsNone(request.params)

    def test_request_with_params_and_id(self):
        """测试带参数和ID的请求"""
        params = {"arg1": "value1", "arg2": 42}
        request = JSONRPCRequest(method="test_method", params=params, id="test-123")

        self.assertEqual(request.method, "test_method")
        self.assertEqual(request.params, params)
        self.assertEqual(request.id, "test-123")

    def test_auto_id_generation(self):
        """测试自动 ID 生成"""
        request1 = JSONRPCRequest(method="test")
        request2 = JSONRPCRequest(method="test")

        self.assertIsNotNone(request1.id)
        self.assertIsNotNone(request2.id)
        self.assertNotEqual(request1.id, request2.id)

    def test_to_json_serialization(self):
        """测试 JSON 序列化"""
        request = JSONRPCRequest(
            method="test_method", params={"key": "value"}, id="123"
        )
        json_str = request.to_json()

        # 解析 JSON 验证结构
        data = json.loads(json_str)
        self.assertEqual(data["method"], "test_method")
        self.assertEqual(data["params"], {"key": "value"})
        self.assertEqual(data["id"], "123")
        self.assertEqual(data["jsonrpc"], "2.0")

    def test_exclude_none_in_serialization(self):
        """测试序列化时排除 None 值"""
        request = JSONRPCRequest(method="test_method", params=None)
        json_str = request.to_json()
        data = json.loads(json_str)

        self.assertNotIn("params", data)  # None 值应该被排除

    def test_extra_fields_ignored(self):
        """测试忽略额外字段"""
        # 这不会抛出异常，因为使用了 extra='ignore'
        request = JSONRPCRequest(method="test", extra_field="should_be_ignored")
        self.assertEqual(request.method, "test")


class TestJSONRPCError(unittest.TestCase):
    """测试 JSONRPCError 类"""

    def test_error_creation(self):
        """测试错误对象创建"""
        error = JSONRPCError(code=-32601, message="Method not found")

        self.assertEqual(error.code, -32601)
        self.assertEqual(error.message, "Method not found")
        self.assertIsNone(error.data)

    def test_error_with_data(self):
        """测试带数据的错误对象"""
        error_data = {"detail": "Invalid parameter"}
        error = JSONRPCError(code=-32602, message="Invalid params", data=error_data)

        self.assertEqual(error.data, error_data)


class TestJSONRPCResult(unittest.TestCase):
    """测试 JSONRPCResult 类"""

    def test_success_result(self):
        """测试成功响应"""
        result = JSONRPCResult(id="123", result={"status": "ok"})

        self.assertEqual(result.id, "123")
        self.assertEqual(result.result, {"status": "ok"})
        self.assertIsNone(result.error)
        self.assertFalse(result.is_error)

    def test_error_result(self):
        """测试错误响应"""
        error = JSONRPCError(code=-1, message="Test error")
        result = JSONRPCResult(id="123", error=error)

        self.assertEqual(result.id, "123")
        self.assertEqual(result.error, error)
        self.assertIsNone(result.result)
        self.assertTrue(result.is_error)

    def test_from_json_success(self):
        """测试从 JSON 创建成功响应"""
        json_data = {"jsonrpc": "2.0", "id": "123", "result": {"status": "success"}}
        json_str = json.dumps(json_data)

        result = JSONRPCResult.from_json(json_str)
        self.assertEqual(result.id, "123")
        self.assertEqual(result.result, {"status": "success"})
        self.assertFalse(result.is_error)

    def test_from_json_error(self):
        """测试从 JSON 创建错误响应"""
        json_data = {
            "jsonrpc": "2.0",
            "id": "123",
            "error": {"code": -1, "message": "Test error"},
        }
        json_str = json.dumps(json_data)

        result = JSONRPCResult.from_json(json_str)
        self.assertEqual(result.id, "123")
        self.assertTrue(result.is_error)
        self.assertEqual(result.error.code, -1)
        self.assertEqual(result.error.message, "Test error")

    def test_to_json_serialization(self):
        """测试 JSON 序列化"""
        result = JSONRPCResult(id="123", result={"data": "test"})
        json_str = result.to_json()
        data = json.loads(json_str)

        self.assertEqual(data["id"], "123")
        self.assertEqual(data["result"], {"data": "test"})
        self.assertEqual(data["jsonrpc"], "2.0")
        self.assertNotIn("error", data)


class TestClientServerInfo(unittest.TestCase):
    """测试 ClientInfo 和 ServerInfo 类"""

    def test_client_info_defaults(self):
        """测试 ClientInfo 默认值"""
        client = ClientInfo()

        self.assertEqual(client.name, "Fake-Cline")
        self.assertEqual(client.version, "0.0.1-SNAPSHOT")
        self.assertEqual(client.title, "Fake-Cline MCP Client")

    def test_server_info_defaults(self):
        """测试 ServerInfo 默认值"""
        server = ServerInfo()

        self.assertEqual(server.name, "Fake-Weather-Server")
        self.assertEqual(server.version, "0.0.1-SNAPSHOT")
        self.assertEqual(server.title, "Fake-Weather-Server MCP Server")

    def test_custom_values(self):
        """测试自定义值"""
        client = ClientInfo(name="Custom-Client", version="1.0.0", title="Custom Title")

        self.assertEqual(client.name, "Custom-Client")
        self.assertEqual(client.version, "1.0.0")
        self.assertEqual(client.title, "Custom Title")


class TestCapabilities(unittest.TestCase):
    """测试 Capabilities 类"""

    def test_empty_capabilities(self):
        """测试空的 capabilities"""
        capabilities = Capabilities()

        self.assertIsNone(capabilities.roots)
        self.assertIsNone(capabilities.tools)
        self.assertIsNone(capabilities.logging)

    def test_capabilities_with_values(self):
        """测试带值的 capabilities"""
        capabilities = Capabilities(
            tools={"listChanged": True}, logging={"listChanged": False}
        )

        self.assertEqual(capabilities.tools, {"listChanged": True})
        self.assertEqual(capabilities.logging, {"listChanged": False})

    def test_serialization_excludes_none(self):
        """测试序列化排除 None 值"""
        capabilities = Capabilities(tools={"listChanged": True})
        data = capabilities.model_dump(exclude_none=True)

        self.assertIn("tools", data)
        self.assertNotIn("logging", data)
        self.assertNotIn("roots", data)


class TestInitializeJSONRPC(unittest.TestCase):
    """测试 Initialize JSON-RPC 类"""

    def test_initialize_request(self):
        """测试初始化请求"""
        request = InitializeJSONRPCRequest(id="init-123")

        self.assertEqual(request.method, "initialize")
        self.assertEqual(request.id, "init-123")
        self.assertIsNotNone(request.params)

        params = request.params
        self.assertEqual(params["protocolVersion"], "2024-11-05")
        self.assertIsInstance(params["capabilities"], Capabilities)
        self.assertIsInstance(params["clientInfo"], ClientInfo)

    def test_initialize_result_success(self):
        """测试成功的初始化响应"""
        result = InitializeJSONRPCResult(id="init-123", is_error=False)

        self.assertEqual(result.id, "init-123")
        self.assertFalse(result.is_error)
        self.assertIsNotNone(result.result)

        result_data = result.result
        self.assertEqual(result_data["protocolVersion"], "2024-11-05")
        self.assertIn("capabilities", result_data)
        self.assertIn("serverInfo", result_data)
        self.assertEqual(result_data["instructions"], "Fake-Weather MCP Server")

    def test_initialize_result_error(self):
        """测试错误的初始化响应"""
        result = InitializeJSONRPCResult(id="init-123", is_error=True)

        self.assertEqual(result.id, "init-123")
        self.assertTrue(result.is_error)
        self.assertIsNone(result.result)
        self.assertEqual(result.error.code, -1)
        self.assertEqual(result.error.message, "Initialize error")


class TestListToolsJSONRPC(unittest.TestCase):
    """测试 ListTools JSON-RPC 类"""

    def test_list_tools_request_without_cursor(self):
        """测试无游标的工具列表请求"""
        request = ListToolsJSONRPCRequest(id="tools-123")

        self.assertEqual(request.method, "tools/list")
        self.assertEqual(request.id, "tools-123")
        self.assertIsNone(request.params)

    def test_list_tools_request_with_cursor(self):
        """测试带游标的工具列表请求"""
        request = ListToolsJSONRPCRequest(id="tools-123", cursor="next-page")

        self.assertEqual(request.method, "tools/list")
        self.assertEqual(request.id, "tools-123")
        self.assertIsNotNone(request.params)
        self.assertEqual(request.params["cursor"], "next-page")

    def test_list_tools_result_success(self):
        """测试成功的工具列表响应"""
        # 创建测试工具
        tool_property = ToolParameterProperty(type="string", description="Test param")
        input_schema = ToolInputSchema(
            type="object", properties={"param1": tool_property}, required=["param1"]
        )
        tool = ToolDefinition(
            name="test_tool", description="A test tool", inputSchema=input_schema
        )

        result = ListToolsJSONRPCResult(
            id="tools-123", tools=[tool], nextCursor="next-page"
        )

        self.assertEqual(result.id, "tools-123")
        self.assertFalse(result.is_error)
        self.assertIsNotNone(result.result)

        result_data = result.result
        self.assertIn("tools", result_data)
        self.assertEqual(result_data["nextCursor"], "next-page")
        self.assertEqual(len(result_data["tools"]), 1)

    def test_list_tools_result_error(self):
        """测试错误的工具列表响应"""
        result = ListToolsJSONRPCResult(id="tools-123", tools=[], is_error=True)

        self.assertTrue(result.is_error)
        self.assertEqual(result.error.message, "Failed to list tools")


class TestToolDefinition(unittest.TestCase):
    """测试工具定义相关类"""

    def test_tool_parameter_property(self):
        """测试工具参数属性"""
        prop = ToolParameterProperty(type="string", description="A string parameter")

        self.assertEqual(prop.type, "string")
        self.assertEqual(prop.description, "A string parameter")

    def test_tool_input_schema(self):
        """测试工具输入模式"""
        prop1 = ToolParameterProperty(type="string", description="Name parameter")
        prop2 = ToolParameterProperty(type="integer", description="Age parameter")

        schema = ToolInputSchema(
            type="object",
            properties={"name": prop1, "age": prop2},
            required=["name"],
            additionalProperties=False,
        )

        self.assertEqual(schema.type, "object")
        self.assertEqual(len(schema.properties), 2)
        self.assertEqual(schema.required, ["name"])
        self.assertFalse(schema.additionalProperties)

    def test_tool_definition_minimal(self):
        """测试最小工具定义"""
        prop = ToolParameterProperty(type="string", description="Input")
        input_schema = ToolInputSchema(type="object", properties={"input": prop})

        tool = ToolDefinition(
            name="test_tool", description="A test tool", inputSchema=input_schema
        )

        self.assertEqual(tool.name, "test_tool")
        self.assertEqual(tool.description, "A test tool")
        self.assertIsNone(tool.title)
        self.assertIsNone(tool.outputSchema)
        self.assertIsNone(tool.annotations)

    def test_tool_definition_complete(self):
        """测试完整工具定义"""
        prop = ToolParameterProperty(type="string", description="Input")
        input_schema = ToolInputSchema(type="object", properties={"input": prop})
        output_schema = ToolOutputSchema(type="object", properties={"result": prop})

        tool = ToolDefinition(
            name="test_tool",
            description="A test tool",
            inputSchema=input_schema,
            title="Test Tool",
            outputSchema=output_schema,
            annotations={"category": "test"},
        )

        self.assertEqual(tool.title, "Test Tool")
        self.assertIsNotNone(tool.outputSchema)
        self.assertEqual(tool.annotations["category"], "test")

    def test_tool_to_json(self):
        """测试工具定义 JSON 序列化"""
        prop = ToolParameterProperty(type="string", description="Input")
        input_schema = ToolInputSchema(type="object", properties={"input": prop})

        tool = ToolDefinition(
            name="test_tool", description="A test tool", inputSchema=input_schema
        )

        json_str = tool.to_json()
        data = json.loads(json_str)

        self.assertEqual(data["name"], "test_tool")
        self.assertEqual(data["description"], "A test tool")
        self.assertIn("inputSchema", data)
        self.assertNotIn("title", data)  # None 值被排除


class TestToolContent(unittest.TestCase):
    """测试工具内容相关类"""

    def test_tool_content_base(self):
        """测试基础工具内容"""
        content = ToolContent(type="base")
        self.assertEqual(content.type, "base")

    def test_text_tool_content(self):
        """测试文本工具内容"""
        content = TextToolContent(text="Hello, World!")

        self.assertEqual(content.type, "text")
        self.assertEqual(content.text, "Hello, World!")

    def test_text_tool_content_serialization(self):
        """测试文本工具内容序列化"""
        content = TextToolContent(text="Test message")
        data = content.model_dump()

        self.assertEqual(data["type"], "text")
        self.assertEqual(data["text"], "Test message")


class TestCallToolJSONRPC(unittest.TestCase):
    """测试 CallTool JSON-RPC 类"""

    def test_call_tool_request_without_arguments(self):
        """测试无参数的工具调用请求"""
        request = CallToolJSONRPCRequest(id="call-123", name="get_weather")

        self.assertEqual(request.method, "tools/call")
        self.assertEqual(request.id, "call-123")
        self.assertIsNotNone(request.params)
        self.assertEqual(request.params["name"], "get_weather")
        self.assertNotIn("arguments", request.params)

    def test_call_tool_request_with_arguments(self):
        """测试带参数的工具调用请求"""
        arguments = {"location": "Beijing", "unit": "celsius"}
        request = CallToolJSONRPCRequest(
            id="call-123", name="get_weather", arguments=arguments
        )

        self.assertEqual(request.method, "tools/call")
        self.assertEqual(request.id, "call-123")
        self.assertEqual(request.params["name"], "get_weather")
        self.assertEqual(request.params["arguments"], arguments)

    def test_call_tool_request_auto_id_generation(self):
        """测试工具调用请求自动生成 ID"""
        request = CallToolJSONRPCRequest(name="test_tool")

        self.assertIsNotNone(request.id)
        self.assertEqual(request.params["name"], "test_tool")

    def test_call_tool_request_serialization(self):
        """测试工具调用请求序列化"""
        arguments = {"param1": "value1", "param2": 42}
        request = CallToolJSONRPCRequest(
            id="call-456", name="test_tool", arguments=arguments
        )

        json_str = request.to_json()
        data = json.loads(json_str)

        self.assertEqual(data["method"], "tools/call")
        self.assertEqual(data["id"], "call-456")
        self.assertEqual(data["jsonrpc"], "2.0")
        self.assertEqual(data["params"]["name"], "test_tool")
        self.assertEqual(data["params"]["arguments"], arguments)

    def test_call_tool_result_success(self):
        """测试成功的工具调用响应"""
        content = [
            TextToolContent(text="Weather in Beijing: 25°C, sunny"),
            TextToolContent(text="Humidity: 60%"),
        ]

        result = CallToolJSONRPCResult(id="call-123", content=content, is_error=False)

        self.assertEqual(result.id, "call-123")
        self.assertFalse(result.is_error)
        self.assertIsNone(result.error)
        self.assertIsNotNone(result.result)

        result_data = result.result
        self.assertFalse(result_data["isError"])
        self.assertEqual(len(result_data["content"]), 2)
        self.assertEqual(result_data["content"][0]["type"], "text")
        self.assertEqual(
            result_data["content"][0]["text"], "Weather in Beijing: 25°C, sunny"
        )

    def test_call_tool_result_success_empty_content(self):
        """测试成功但无内容的工具调用响应"""
        result = CallToolJSONRPCResult(id="call-123", content=None, is_error=False)

        self.assertEqual(result.id, "call-123")
        self.assertFalse(result.is_error)
        self.assertIsNone(result.error)

        result_data = result.result
        self.assertFalse(result_data["isError"])
        self.assertEqual(result_data["content"], [])

    def test_call_tool_result_error_default_message(self):
        """测试错误的工具调用响应（默认错误消息）"""
        result = CallToolJSONRPCResult(id="call-123", is_error=True)

        self.assertEqual(result.id, "call-123")
        self.assertTrue(result.is_error)
        self.assertIsNone(result.result)
        self.assertIsNotNone(result.error)
        self.assertEqual(result.error.code, -1)
        self.assertEqual(result.error.message, "Tool execution failed")

    def test_call_tool_result_error_custom_message(self):
        """测试错误的工具调用响应（自定义错误消息）"""
        error_message = "Invalid location parameter"
        result = CallToolJSONRPCResult(
            id="call-123", is_error=True, error_message=error_message
        )

        self.assertEqual(result.id, "call-123")
        self.assertTrue(result.is_error)
        self.assertIsNone(result.result)
        self.assertEqual(result.error.message, error_message)

    def test_call_tool_result_serialization_success(self):
        """测试成功工具调用响应的序列化"""
        content = [TextToolContent(text="Success result")]
        result = CallToolJSONRPCResult(id="call-789", content=content, is_error=False)

        json_str = result.to_json()
        data = json.loads(json_str)

        self.assertEqual(data["id"], "call-789")
        self.assertEqual(data["jsonrpc"], "2.0")
        self.assertNotIn("error", data)
        self.assertIn("result", data)

        result_data = data["result"]
        self.assertFalse(result_data["isError"])
        self.assertEqual(len(result_data["content"]), 1)
        self.assertEqual(result_data["content"][0]["type"], "text")
        self.assertEqual(result_data["content"][0]["text"], "Success result")

    def test_call_tool_result_serialization_error(self):
        """测试错误工具调用响应的序列化"""
        result = CallToolJSONRPCResult(
            id="call-789", is_error=True, error_message="Test error"
        )

        json_str = result.to_json()
        data = json.loads(json_str)

        self.assertEqual(data["id"], "call-789")
        self.assertEqual(data["jsonrpc"], "2.0")
        self.assertNotIn("result", data)
        self.assertIn("error", data)

        error_data = data["error"]
        self.assertEqual(error_data["code"], -1)
        self.assertEqual(error_data["message"], "Test error")

    def test_call_tool_multiple_content_types(self):
        """测试多种类型内容的工具调用响应"""
        content = [
            TextToolContent(text="First result"),
            TextToolContent(text="Second result"),
            ToolContent(type="custom"),  # 测试基础内容类型
        ]

        result = CallToolJSONRPCResult(id="call-multi", content=content, is_error=False)

        result_data = result.result
        self.assertEqual(len(result_data["content"]), 3)
        self.assertEqual(result_data["content"][0]["type"], "text")
        self.assertEqual(result_data["content"][1]["type"], "text")
        self.assertEqual(result_data["content"][2]["type"], "custom")


class TestCompleteIntegration(unittest.TestCase):
    """完整集成测试，包括工具调用流程"""

    def test_complete_tool_workflow(self):
        """测试完整的工具工作流程"""
        # 1. 初始化
        init_request = InitializeJSONRPCRequest(id="integration-test")
        init_response = InitializeJSONRPCResult(id="integration-test")

        self.assertFalse(init_response.is_error)

        # 2. 列出工具
        tools_request = ListToolsJSONRPCRequest(id="list-tools")

        # 创建测试工具定义
        param_prop = ToolParameterProperty(
            type="string", description="Location for weather query"
        )
        input_schema = ToolInputSchema(
            type="object", properties={"location": param_prop}, required=["location"]
        )
        weather_tool = ToolDefinition(
            name="get_weather",
            description="Get current weather for a location",
            inputSchema=input_schema,
        )

        tools_response = ListToolsJSONRPCResult(id="list-tools", tools=[weather_tool])

        self.assertFalse(tools_response.is_error)
        self.assertEqual(len(tools_response.result["tools"]), 1)

        # 3. 调用工具
        call_request = CallToolJSONRPCRequest(
            id="call-weather", name="get_weather", arguments={"location": "Shanghai"}
        )

        # 模拟成功响应
        call_response = CallToolJSONRPCResult(
            id="call-weather",
            content=[TextToolContent(text="Shanghai weather: 22°C, cloudy")],
            is_error=False,
        )

        self.assertFalse(call_response.is_error)
        self.assertEqual(
            call_response.result["content"][0]["text"], "Shanghai weather: 22°C, cloudy"
        )

        # 4. 测试完整的 JSON 序列化/反序列化循环
        serialized_init = init_request.to_json()
        serialized_tools = tools_request.to_json()
        serialized_call = call_request.to_json()

        # 验证所有 JSON 都有效
        parsed_init = json.loads(serialized_init)
        parsed_tools = json.loads(serialized_tools)
        parsed_call = json.loads(serialized_call)

        self.assertEqual(parsed_init["method"], "initialize")
        self.assertEqual(parsed_tools["method"], "tools/list")
        self.assertEqual(parsed_call["method"], "tools/call")
        self.assertEqual(parsed_call["params"]["name"], "get_weather")

    def test_error_handling_workflow(self):
        """测试错误处理工作流程"""
        # 1. 初始化失败
        init_error_response = InitializeJSONRPCResult(id="init-error", is_error=True)
        self.assertTrue(init_error_response.is_error)

        # 2. 工具列表失败
        tools_error_response = ListToolsJSONRPCResult(
            id="tools-error", tools=[], is_error=True
        )
        self.assertTrue(tools_error_response.is_error)

        # 3. 工具调用失败
        call_error_response = CallToolJSONRPCResult(
            id="call-error",
            is_error=True,
            error_message="Tool not found: nonexistent_tool",
        )
        self.assertTrue(call_error_response.is_error)
        self.assertEqual(
            call_error_response.error.message, "Tool not found: nonexistent_tool"
        )

    def test_json_roundtrip_consistency(self):
        """测试 JSON 序列化/反序列化的一致性"""
        # 创建复杂的工具调用请求
        complex_arguments = {
            "location": "New York",
            "unit": "fahrenheit",
            "include_forecast": True,
            "days": 7,
            "options": {"include_humidity": True, "include_wind": False},
        }

        original_request = CallToolJSONRPCRequest(
            id="roundtrip-test", name="complex_weather", arguments=complex_arguments
        )

        # 序列化
        json_str = original_request.to_json()

        # 反序列化
        data = json.loads(json_str)
        reconstructed_request = JSONRPCRequest(
            method=data["method"],
            params=data["params"],
            id=data["id"],
            jsonrpc=data["jsonrpc"],
        )

        # 验证一致性
        self.assertEqual(original_request.method, reconstructed_request.method)
        self.assertEqual(original_request.id, reconstructed_request.id)
        self.assertEqual(original_request.params, reconstructed_request.params)
        self.assertEqual(original_request.jsonrpc, reconstructed_request.jsonrpc)

    def test_edge_cases(self):
        """测试边界情况"""
        # 1. 空参数的工具调用
        empty_call = CallToolJSONRPCRequest(
            id="empty-test", name="no_param_tool", arguments={}
        )
        self.assertEqual(empty_call.params["arguments"], {})

        # 2. None ID 的自动生成
        auto_id_call = CallToolJSONRPCRequest(name="auto_id_tool")
        self.assertIsNotNone(auto_id_call.id)

        # 3. 大量内容的响应
        large_content = [TextToolContent(text=f"Result {i}") for i in range(100)]
        large_response = CallToolJSONRPCResult(id="large-test", content=large_content)
        self.assertEqual(len(large_response.result["content"]), 100)

        # 4. 特殊字符处理
        special_args = {
            "text": "Hello, 世界! 🌍",
            "json": '{"nested": "value"}',
            "unicode": "\u2603",  # 雪人符号
        }
        special_call = CallToolJSONRPCRequest(
            id="special-test", name="special_tool", arguments=special_args
        )

        # 验证序列化不会出错
        json_str = special_call.to_json()
        self.assertIsInstance(json_str, str)

        # 验证可以正确解析
        parsed = json.loads(json_str)
        self.assertEqual(parsed["params"]["arguments"]["text"], "Hello, 世界! 🌍")


if __name__ == "__main__":
    # 运行所有测试
    unittest.main(verbosity=2)
