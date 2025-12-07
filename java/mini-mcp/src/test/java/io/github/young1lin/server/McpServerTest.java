package io.github.young1lin.server;

import java.util.ArrayList;
import java.util.List;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import io.github.young1lin.tool.Tool;

@DisplayName("McpServerTest")
@ExtendWith(MockitoExtension.class)
public class McpServerTest {

    private McpServer mcpServer;

    private List<Tool> tools;

    @Mock
    private ServerSession session;

    @BeforeEach
    void setUp() {
        // 创建一个实际的 ArrayList，而不是 mock 的 List
        // 因为 McpServer 构造函数会遍历这个列表
        tools = new ArrayList<>();
        // 如果需要，可以添加 mock 的 SimpleTool 对象
        // tools.add(mock(SimpleTool.class));

        // 手动创建 McpServer 实例
        mcpServer = new McpServer(tools, session);
    }

    @DisplayName("测试调用工具是否成功")
    @Test
    void test_call_tool_success() {
        // Arrange

        // Act

        // Assert
    }

}
