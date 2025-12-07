package io.github.young1lin.util;

import java.io.IOException;
import java.io.InputStream;
import java.util.*;

import com.fasterxml.jackson.core.type.TypeReference;

import io.github.young1lin.client.MCPClient;
import io.github.young1lin.host.McpServerConfig;

/**
 * MCP 配置工具类
 */
public class MCPConfigUtil {

    /**
     * 解析 mcp.json 配置文件
     */
    public static Map<String, McpServerConfig> parseMCPConfig(InputStream in) throws IOException {
        // 解析整个 mcp.json 为 Map
        Map<String, Object> config = JsonUtil.parseJson(in, new TypeReference<Map<String, Object>>() {
        }).orElse(Collections.emptyMap());
        Object mcpServersObj = config.get("mcpServers");
        if (mcpServersObj instanceof Map<?, ?> mcpServersMap) {
            Map<String, McpServerConfig> result = new HashMap<>();
            for (Map.Entry<?, ?> entry : mcpServersMap.entrySet()) {
                Object key = entry.getKey();
                Object value = entry.getValue();
                if (key instanceof String && value instanceof Map) {
                    // 将 Map 转为 McpServer
                    McpServerConfig server = JsonUtil.convertValue(value, McpServerConfig.class);
                    result.put((String) key, server);
                }
            }
            return result;
        }
        return Collections.emptyMap();
    }

    /**
     * 构建 MCP 服务器部分的 system prompt
     */
    public static String buildMCPServersSection(Map<String, MCPClient> mcpClients) {
        if (mcpClients == null || mcpClients.isEmpty()) {
            return "当前没有可用的 MCP Server。";
        }

        StringBuilder sections = new StringBuilder();
        sections.append("现在你有这些 MCP Server 可以调用：\n\n");

        for (Map.Entry<String, MCPClient> entry : mcpClients.entrySet()) {
            String serverName = entry.getKey();
            MCPClient client = entry.getValue();

            sections.append("## ").append(serverName).append("\n");
            List<io.github.young1lin.dto.ToolDefinition> tools = client.getTools();
            if (tools == null || tools.isEmpty()) {
                sections.append("### 可用工具：无\n");
            } else {
                sections.append("### 可用工具如下\n");
                for (io.github.young1lin.dto.ToolDefinition tool : tools) {
                    sections.append("- ").append(tool.getName()).append("：").append(tool.getDescription()).append("\n");
                    if (tool.getInputSchema() != null && tool.getInputSchema().getProperties() != null) {
                        sections.append("  输入参数：\n");
                        List<String> required = tool.getInputSchema().getRequired() != null
                                ? tool.getInputSchema().getRequired()
                                : new ArrayList<>();
                        for (Map.Entry<String, io.github.young1lin.dto.ToolParameterProperty> paramEntry : tool
                                .getInputSchema().getProperties().entrySet()) {
                            String paramName = paramEntry.getKey();
                            io.github.young1lin.dto.ToolParameterProperty paramProp = paramEntry.getValue();
                            String requiredMark = required.contains(paramName) ? "(必需)" : "(可选)";
                            sections.append("    - ").append(paramName).append("：")
                                    .append(paramProp.getDescription()).append(" ").append(requiredMark).append("\n");
                        }
                    } else {
                        sections.append("  输入参数：无\n");
                    }
                    sections.append("\n"); // 空行分隔
                }
            }
        }

        return sections.toString();
    }

    /**
     * 初始化所有 MCP 服务器
     */
    public static Map<String, MCPClient> initializeMCPServers(InputStream in) throws IOException {
        Map<String, McpServerConfig> config = parseMCPConfig(in);
        Map<String, MCPClient> mcpClients = new HashMap<>();

        for (Map.Entry<String, McpServerConfig> entry : config.entrySet()) {
            String serverName = entry.getKey();
            McpServerConfig serverConfig = entry.getValue();

            String type = serverConfig.getType();
            // 默认走 stdio 类型
            if (type != null && !"stdio".equals(type)) {
                System.out.println("跳过服务器 " + serverName + "：仅支持 stdio 类型");
                continue;
            }

            String command = serverConfig.getCommand();

            if (command == null || command.isEmpty()) {
                System.out.println("跳过服务器 " + serverName + "：缺少 command 配置");
                continue;
            }

            try {
                MCPClient client = new MCPClient(serverName, serverConfig);
                client.connect();
                mcpClients.put(serverName, client);
                System.out.println("成功连接 MCP 服务器: " + serverName + ", 工具数量: " + client.getTools().size());
            } catch (Exception e) {
                System.out.println("连接 MCP 服务器 " + serverName + " 失败: " + e.getMessage());
                e.printStackTrace();
            }
        }

        return mcpClients;
    }

}
