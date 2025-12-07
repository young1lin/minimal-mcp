package io.github.young1lin.server;

import java.lang.reflect.Method;
import java.lang.reflect.Parameter;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.function.Function;
import java.util.logging.Logger;
import java.util.stream.Collectors;

import io.github.young1lin.dto.*;
import io.github.young1lin.tool.Tool;

/**
 * MCP 服务器主类
 */
public class McpServer {

    private static final Logger logger = Logger.getLogger(McpServer.class.getName());

    private final List<ToolDefinition> tools;

    private final Map<String, Tool> toolFuncs;

    private final ServerSession session;

    public McpServer(List<Tool> tools, ServerSession session) {
        this.session = session;

        if (tools == null || tools.isEmpty()) {
            logger.warning("tools is null or empty");
            this.tools = new ArrayList<>();
            this.toolFuncs = new HashMap<>();
            return;
        }

        // Convert Tool objects to ToolDefinition objects using stream
        this.tools = tools.stream()
                .map(toolObj -> {
                    // Parse docstring to get parameter descriptions
                    Map<String, String> paramDescriptions = parseDocstringParams(toolObj.getFunc());

                    // Convert function annotations to ToolParameterProperty objects using stream
                    Map<String, ToolParameterProperty> properties = toolObj.getArguments()
                            .entrySet()
                            .stream()
                            .collect(Collectors.toMap(
                                    Map.Entry::getKey,
                                    entry -> {
                                        String paramName = entry.getKey();
                                        Class<?> paramType = entry.getValue();
                                        String description = paramDescriptions.getOrDefault(
                                                paramName, "Parameter " + paramName);
                                        return ToolParameterProperty.builder()
                                                .type(getTypeString(paramType))
                                                .description(description)
                                                .build();
                                    }));

                    ToolInputSchema inputSchema = ToolInputSchema.builder()
                            .type("object")
                            .properties(properties)
                            .required(
                                    toolObj.getRequiredArguments() != null && !toolObj.getRequiredArguments().isEmpty()
                                            ? toolObj.getRequiredArguments()
                                            : null)
                            .build();

                    return ToolDefinition.builder()
                            .name(toolObj.getName())
                            .description(toolObj.getDescription())
                            .inputSchema(inputSchema)
                            .build();
                })
                .collect(Collectors.toList());
        this.toolFuncs = tools.stream()
                .collect(Collectors.toMap(Tool::getName, Function.identity()));

        logger.info("McpServer initialized with tools: " +
                tools.stream().map(Tool::getName).collect(Collectors.toList()));
    }

    private Map<String, String> parseDocstringParams(Method func) {
        // Java 没有 docstring，我们使用 JavaDoc 注释
        // 这里简化处理，返回空 Map
        // 实际可以通过反射获取注解信息
        return new HashMap<>();
    }

    private String getTypeString(Class<?> paramType) {
        if (paramType == null) {
            return "string";
        }

        String typeName = paramType.getSimpleName();
        if ("String".equals(typeName)) {
            return "string";
        } else if ("Integer".equals(typeName) || "int".equals(typeName)) {
            return "integer";
        } else if ("Double".equals(typeName) || "Float".equals(typeName) ||
                "double".equals(typeName) || "float".equals(typeName)) {
            return "number";
        } else if ("Boolean".equals(typeName) || "boolean".equals(typeName)) {
            return "boolean";
        } else if (List.class.isAssignableFrom(paramType)) {
            return "array";
        } else {
            return "string"; // default fallback
        }
    }

    public InitializeJSONRPCResult initialize(String protocolVersion, Map<String, Object> capabilities,
            Map<String, Object> clientInfo) {
        logger.info("initialize called with protocolVersion: " + protocolVersion +
                ", capabilities: " + capabilities + ", clientInfo: " + clientInfo);
        return new InitializeJSONRPCResult(null, false);
    }

    public Function<Map<String, Object>, Object> initializeMethod() {
        return params -> {
            String protocolVersion = (String) params.getOrDefault("protocolVersion", "2024-11-05");
            @SuppressWarnings("unchecked")
            Map<String, Object> capabilities = (Map<String, Object>) params.get("capabilities");
            @SuppressWarnings("unchecked")
            Map<String, Object> clientInfo = (Map<String, Object>) params.get("clientInfo");
            return initialize(protocolVersion, capabilities, clientInfo);
        };
    }

    public void notifyInitialize() {
        logger.info("receive [notifications/initialized], just ack mechanism");
    }

    public Function<Map<String, Object>, Object> notifyInitializeMethod() {
        return params -> {
            notifyInitialize();
            return null;
        };
    }

    public ListToolsJSONRPCResult listTools(String cursor) {
        logger.info("list_tools called with cursor: " + cursor + ", tools: " + tools);
        return new ListToolsJSONRPCResult(null, tools, null, false);
    }

    public Function<Map<String, Object>, Object> listToolsMethod() {
        return params -> {
            String cursor = (String) params.get("cursor");
            return listTools(cursor);
        };
    }

    public CallToolJSONRPCResult callTool(String name, Map<String, Object> arguments) {
        try {
            if (!toolFuncs.containsKey(name)) {
                logger.severe("Tool '" + name + "' not found");
                return new CallToolJSONRPCResult(null, null, true, "Tool '" + name + "' not found");
            }

            // Get the tool function
            Tool tool = toolFuncs.get(name);
            Method method = tool.getFunc();
            Object instance = tool.getInstance();

            // Prepare arguments
            if (arguments == null) {
                arguments = new HashMap<>();
            }

            // Call the tool function using reflection
            Object result;
            try {
                Parameter[] parameters = method.getParameters();
                Object[] args = new Object[parameters.length];

                for (int i = 0; i < parameters.length; i++) {
                    Parameter param = parameters[i];
                    String paramName = param.getName();
                    if (arguments.containsKey(paramName)) {
                        args[i] = arguments.get(paramName);
                    } else {
                        args[i] = null;
                    }
                }

                if (instance != null) {
                    result = method.invoke(instance, args);
                } else {
                    result = method.invoke(null, args);
                }
            } catch (Exception e) {
                throw new RuntimeException("Failed to invoke tool method", e);
            }

            // Convert result to TextToolContent
            List<ToolContent> content = new ArrayList<>();
            content.add(new TextToolContent(String.valueOf(result)));

            return new CallToolJSONRPCResult(null, content, false, null);
        } catch (Exception e) {
            logger.severe("Tool '" + name + "' execution failed: " + e.getMessage());
            e.printStackTrace();
            return new CallToolJSONRPCResult(null, null, true, "Tool execution failed: " + e.getMessage());
        }
    }

    public Function<Map<String, Object>, Object> callToolMethod() {
        return params -> {
            String name = (String) params.get("name");
            @SuppressWarnings("unchecked")
            Map<String, Object> arguments = (Map<String, Object>) params.get("arguments");
            return callTool(name, arguments);
        };
    }

    public void notifyToolChange() {
        logger.info("Tool list changed notification received");
    }

    public Function<Map<String, Object>, Object> notifyToolChangeMethod() {
        return params -> {
            notifyToolChange();
            return null;
        };
    }

    public Map<String, Object> listPrompts(String cursor) {
        logger.info("list_prompts called (not implemented)");
        Map<String, Object> result = new HashMap<>();
        result.put("prompts", new ArrayList<>());
        return result;
    }

    public Function<Map<String, Object>, Object> listPromptsMethod() {
        return params -> {
            String cursor = (String) params.get("cursor");
            return listPrompts(cursor);
        };
    }

    public Object getPrompt(String name) {
        logger.info("get_prompt called for '" + name + "' (not implemented)");
        return null;
    }

    public Function<Map<String, Object>, Object> getPromptMethod() {
        return params -> {
            String name = (String) params.get("name");
            return getPrompt(name);
        };
    }

    public void notifyPromptChange() {
        logger.info("notify_prompt_change called (not implemented)");
    }

    public Function<Map<String, Object>, Object> notifyPromptChangeMethod() {
        return params -> {
            notifyPromptChange();
            return null;
        };
    }

    public Map<String, Object> listResources(String cursor) {
        logger.info("list_resources called (not implemented)");
        Map<String, Object> result = new HashMap<>();
        result.put("resources", new ArrayList<>());
        return result;
    }

    public Function<Map<String, Object>, Object> listResourcesMethod() {
        return params -> {
            String cursor = (String) params.get("cursor");
            return listResources(cursor);
        };
    }

    public Map<String, Object> listCapabilities() {
        logger.info("list_capabilities called (not implemented)");
        return new HashMap<>();
    }

    public Function<Map<String, Object>, Object> listCapabilitiesMethod() {
        return params -> listCapabilities();
    }
}
