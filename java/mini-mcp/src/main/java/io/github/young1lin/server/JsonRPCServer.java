package io.github.young1lin.server;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.util.HashMap;
import java.util.Map;
import java.util.function.Function;
import java.util.logging.Logger;

import io.github.young1lin.dto.JSONRPCError;
import io.github.young1lin.dto.JSONRPCResponse;
import io.github.young1lin.util.JsonUtil;

/**
 * JSON RPC 服务器
 */
public class JsonRPCServer {

    private static final Logger logger = Logger.getLogger(JsonRPCServer.class.getName());

    private final Map<String, Function<Map<String, Object>, Object>> methods = new HashMap<>();
    private volatile boolean running = true;

    public void registerMethod(String name, Function<Map<String, Object>, Object> method) {
        methods.put(name, method);
    }

    public String processRequest(Map<String, Object> request) {
        if (!"2.0".equals(request.get("jsonrpc"))) {
            return errorResponse(request.get("id"), -32600, "Invalid Request");
        }

        String method = (String) request.get("method");
        @SuppressWarnings("unchecked")
        Map<String, Object> params = (Map<String, Object>) request.getOrDefault("params", new HashMap<>());
        Object requestId = request.get("id");

        // 如果没有 id，这是一个通知
        if (requestId == null) {
            logger.info("Received notification: " + method + ", do nothing");
            if (methods.containsKey(method)) {
                try {
                    methods.get(method).apply(params);
                } catch (Exception e) {
                    logger.severe("Error processing notification " + method + ": " + e.getMessage());
                }
            }
            return null;
        }

        // 处理请求
        logger.info("Processing request for method: " + method + ", id: " + requestId);
        if (!methods.containsKey(method)) {
            logger.severe("Method not found: " + method);
            return errorResponse(requestId, -32601, "Method not found");
        }

        try {
            Object result = methods.get(method).apply(params);

            // 如果结果已经是 JSONRPCResponse，直接返回 JSON
            if (result instanceof JSONRPCResponse) {
                JSONRPCResponse response = (JSONRPCResponse) result;
                response.setId(requestId != null ? requestId.toString() : null);
                return JsonUtil.toJson(response);
            } else {
                JSONRPCResponse response = JSONRPCResponse.builder()
                        .id(requestId != null ? requestId.toString() : null)
                        .result(result)
                        .build();
                return JsonUtil.toJson(response);
            }
        } catch (Exception e) {
            logger.severe("Internal error processing method " + method + ": " + e.getMessage());
            e.printStackTrace();
            return errorResponse(requestId, -32603, "Internal error: " + e.getMessage());
        }
    }

    private String errorResponse(Object requestId, int code, String message) {
        JSONRPCResponse response = JSONRPCResponse.builder()
                .id(requestId != null ? requestId.toString() : null)
                .error(JSONRPCError.builder()
                        .code(code)
                        .message(message)
                        .build())
                .build();
        return JsonUtil.toJson(response);
    }

    public void start() {
        try (BufferedReader reader = new BufferedReader(new InputStreamReader(System.in))) {
            while (running) {
                try {
                    String line = reader.readLine();
                    if (line == null) {
                        break;
                    }

                    line = line.trim();
                    if (line.isEmpty()) {
                        continue;
                    }

                    logger.fine("Received line: " + line);
                    Map<String, Object> request = JsonUtil.parseJson(line);
                    String response = processRequest(request);

                    if (response != null) {
                        System.out.println(response);
                        System.out.flush();
                    }
                } catch (RuntimeException e) {
                    // JsonUtil 会抛出 RuntimeException，如果原因是 JSON 解析错误，则返回 Parse error
                    if (e.getCause() instanceof com.fasterxml.jackson.core.JsonProcessingException) {
                        String error = errorResponse(null, -32700, "Parse error");
                        System.out.println(error);
                        System.out.flush();
                    } else {
                        throw e; // 重新抛出其他类型的 RuntimeException
                    }
                } catch (Exception e) {
                    logger.severe("Unexpected error: " + e.getMessage());
                    e.printStackTrace();
                }
            }
        } catch (Exception e) {
            logger.severe("Server error: " + e.getMessage());
            e.printStackTrace();
        }

        logger.info("Server shutting down");
    }

    public void stop() {
        running = false;
    }
}
