package io.github.young1lin.client;

import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.logging.Logger;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import java.util.stream.Stream;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

import io.github.young1lin.util.JsonUtil;

/**
 * ChatBot 类，用于与 LLM 交互并处理工具调用
 * 使用 Java 21 内置的 java.net.http.HttpClient
 */
public class ChatBot {

    private static final Logger logger = Logger.getLogger(ChatBot.class.getName());
    private static final String LLM_URL = "https://api.deepseek.com/chat/completions";
    private static final String LLM_MODEL = "deepseek-chat";
    private static final int MAX_ROUNDS = 10;

    private final String apiKey;
    private final String systemPrompt;
    private final HttpClient client;
    private final Map<String, MCPClient> mcpClients;
    private final List<Map<String, String>> messages;
    private static final ObjectMapper objectMapper = new ObjectMapper();

    public ChatBot(String apiKey, String systemPrompt, Map<String, MCPClient> mcpClients) {
        this.apiKey = apiKey;
        this.systemPrompt = systemPrompt;
        this.mcpClients = mcpClients != null ? new HashMap<>(mcpClients) : new HashMap<>();
        this.client = HttpClient.newBuilder()
                .connectTimeout(Duration.ofSeconds(30))
                .build();
        this.messages = new ArrayList<>();
        this.messages.add(Map.of("role", "system", "content", systemPrompt));
    }

    private void limitMessages() {
        List<Map<String, String>> nonSystemMessages = new ArrayList<>();
        for (Map<String, String> msg : messages) {
            if (!"system".equals(msg.get("role"))) {
                nonSystemMessages.add(msg);
            }
        }
        int maxMessages = MAX_ROUNDS * 2;

        if (nonSystemMessages.size() > maxMessages) {
            List<Map<String, String>> systemMsg = new ArrayList<>();
            for (Map<String, String> msg : messages) {
                if ("system".equals(msg.get("role"))) {
                    systemMsg.add(msg);
                }
            }
            messages.clear();
            messages.addAll(systemMsg);
            messages.addAll(nonSystemMessages.subList(
                    nonSystemMessages.size() - maxMessages, nonSystemMessages.size()));
        }
    }

    private Map.Entry<String, Map<String, String>> parseXmlTool(String content) {
        // 匹配工具调用标签：<tool_name>...</tool_name>
        Pattern pattern = Pattern.compile("<(\\w+)>(.*?)</\\1>", Pattern.DOTALL);
        Matcher matcher = pattern.matcher(content);

        while (matcher.find()) {
            String toolName = matcher.group(1);
            String toolContent = matcher.group(2);

            if ("read_file".equals(toolName) || "ls".equals(toolName) ||
                    "final_answer".equals(toolName) || "use_mcp_tool".equals(toolName)) {
                // 解析参数
                Map<String, String> params = new HashMap<>();
                Pattern paramPattern = Pattern.compile("<(\\w+)>(.*?)</\\1>", Pattern.DOTALL);
                Matcher paramMatcher = paramPattern.matcher(toolContent);
                while (paramMatcher.find()) {
                    String paramName = paramMatcher.group(1);
                    String paramValue = paramMatcher.group(2).trim();
                    params.put(paramName, paramValue);
                }
                return Map.entry(toolName, params);
            }
        }
        return null;
    }

    private ToolExecutionResult executeTool(String toolName, Map<String, String> params) throws IOException {
        if ("final_answer".equals(toolName)) {
            String answer = params.getOrDefault("answer", "");
            return new ToolExecutionResult(answer, true);
        }

        if ("read_file".equals(toolName)) {
            String path = params.getOrDefault("path", "");
            if (!path.isEmpty()) {
                try {
                    String result = readFile(path);
                    return new ToolExecutionResult("文件内容：\n" + result, false);
                } catch (Exception e) {
                    return new ToolExecutionResult("读取文件失败：" + e.getMessage(), false);
                }
            }
        } else if ("ls".equals(toolName)) {
            String path = params.getOrDefault("path", ".");
            try {
                java.io.File dir = new java.io.File(path);
                String[] items = dir.list();
                if (items != null) {
                    String result = String.join("\n", items);
                    return new ToolExecutionResult("\n" + result, false);
                }
            } catch (Exception e) {
                return new ToolExecutionResult("列出目录失败：" + e.getMessage(), false);
            }
        } else if ("use_mcp_tool".equals(toolName)) {
            String serverName = params.getOrDefault("server_name", "").trim();
            String toolNameMcp = params.getOrDefault("tool_name", "").trim();
            String argumentsStr = params.getOrDefault("arguments", "{}").trim();

            if (serverName.isEmpty()) {
                return new ToolExecutionResult("错误：缺少 server_name 参数", false);
            }
            if (toolNameMcp.isEmpty()) {
                return new ToolExecutionResult("错误：缺少 tool_name 参数", false);
            }

            if (!mcpClients.containsKey(serverName)) {
                return new ToolExecutionResult("错误：找不到 MCP 服务器 '" + serverName + "'", false);
            }

            try {
                @SuppressWarnings("unchecked")
                Map<String, Object> arguments = JsonUtil.parseJson(argumentsStr, Map.class);
                MCPClient mcpClient = mcpClients.get(serverName);
                String result = mcpClient.callTool(toolNameMcp, arguments);
                return new ToolExecutionResult(result, false);
            } catch (Exception e) {
                return new ToolExecutionResult("调用 MCP 工具失败：" + e.getMessage(), false);
            }
        }

        return new ToolExecutionResult(null, false);
    }

    private String readFile(String path) throws IOException {
        return new String(java.nio.file.Files.readAllBytes(
                java.nio.file.Paths.get(path)), StandardCharsets.UTF_8);
    }

    public void chat(String message, ChatResponseHandler handler) throws IOException, InterruptedException {
        messages.add(Map.of("role", "user", "content", message));
        limitMessages();

        int maxIterations = 20;
        int iteration = 0;

        while (iteration < maxIterations) {
            iteration++;

            // 构建请求体
            Map<String, Object> requestBody = new HashMap<>();
            requestBody.put("model", LLM_MODEL);
            requestBody.put("messages", messages);
            requestBody.put("stream", true);

            String requestBodyJson = JsonUtil.toJson(requestBody);

            // 创建 HTTP 请求
            HttpRequest request = HttpRequest.newBuilder()
                    .uri(URI.create(LLM_URL))
                    .header("Authorization", "Bearer " + apiKey)
                    .header("Content-Type", "application/json")
                    .POST(HttpRequest.BodyPublishers.ofString(requestBodyJson, StandardCharsets.UTF_8))
                    .timeout(Duration.ofSeconds(60))
                    .build();

            StringBuilder fullContent = new StringBuilder();
            StringBuilder buffer = new StringBuilder();
            boolean toolExecuted = false;
            boolean shouldOutput = true;

            // 使用流式响应处理 SSE
            HttpResponse<Stream<String>> response = client.send(
                    request,
                    HttpResponse.BodyHandlers.ofLines());

            if (response.statusCode() != 200) {
                throw new IOException("Unexpected status code: " + response.statusCode());
            }

            // 处理 SSE 格式的响应流
            try (Stream<String> lines = response.body()) {
                for (String line : (Iterable<String>) lines::iterator) {
                    line = line.trim();
                    if (line.isEmpty() || !line.startsWith("data: ")) {
                        continue;
                    }

                    String dataStr = line.substring(6);
                    if ("[DONE]".equals(dataStr)) {
                        break;
                    }

                    try {
                        JsonNode data = objectMapper.readTree(dataStr);
                        if (data.has("choices")) {
                            var choices = data.get("choices");
                            if (choices.isArray() && choices.size() > 0) {
                                var delta = choices.get(0).get("delta");
                                if (delta != null && delta.has("content")) {
                                    String content = delta.get("content").asText();
                                    fullContent.append(content);
                                    buffer.append(content);

                                    // 流式检测完整的工具调用
                                    if (!toolExecuted) {
                                        Map.Entry<String, Map<String, String>> toolCall = parseXmlTool(
                                                buffer.toString());
                                        if (toolCall != null && toolCall.getValue() != null) {
                                            toolExecuted = true;
                                            shouldOutput = false;

                                            // 将 assistant 的回复添加到消息历史
                                            if (fullContent.length() > 0) {
                                                messages.add(
                                                        Map.of("role", "assistant", "content", fullContent.toString()));
                                                limitMessages();
                                            }

                                            // 处理工具调用
                                            ToolExecutionResult result = executeTool(toolCall.getKey(),
                                                    toolCall.getValue());

                                            if (result.isFinal) {
                                                handler.onFinalAnswer(result.result);
                                                return;
                                            } else if (result.result != null) {
                                                handler.onToolResult(result.result);
                                                messages.add(Map.of("role", "user",
                                                        "content",
                                                        "工具 " + toolCall.getKey() + " 的执行结果：" + result.result));
                                                limitMessages();
                                            }

                                            // 检测到工具调用但不是 final_answer，继续循环
                                            break;
                                        }
                                    }

                                    // 只有在没有检测到工具调用时才输出内容
                                    if (shouldOutput) {
                                        handler.onContent(content);
                                    }
                                }
                            }
                        }
                    } catch (Exception e) {
                        logger.warning("Failed to parse SSE data: " + e.getMessage());
                    }
                }
            }

            // 将完整的回复添加到消息历史中（如果还没有添加）
            if (fullContent.length() > 0 && !toolExecuted) {
                messages.add(Map.of("role", "assistant", "content", fullContent.toString()));
                limitMessages();

                // 最后再检查一次是否有工具调用
                Map.Entry<String, Map<String, String>> toolCall = parseXmlTool(fullContent.toString());
                if (toolCall != null && toolCall.getValue() != null) {
                    ToolExecutionResult result = executeTool(toolCall.getKey(), toolCall.getValue());

                    if (result.isFinal) {
                        handler.onFinalAnswer(result.result);
                        return;
                    } else if (result.result != null) {
                        handler.onToolResult(result.result);
                        messages.add(Map.of("role", "user",
                                "content", "工具 " + toolCall.getKey() + " 的执行结果：" + result.result));
                        limitMessages();
                        continue;
                    }
                }
            }

            // 检查是否有新的工具调用需要处理
            if (messages.size() > 0 && "assistant".equals(messages.get(messages.size() - 1).get("role"))) {
                break;
            }
        }
    }

    private static class ToolExecutionResult {
        final String result;
        final boolean isFinal;

        ToolExecutionResult(String result, boolean isFinal) {
            this.result = result;
            this.isFinal = isFinal;
        }
    }

    public interface ChatResponseHandler {
        void onContent(String content);

        void onToolResult(String result);

        void onFinalAnswer(String answer);
    }
}
