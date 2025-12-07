package io.github.young1lin.client;

import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.TimeoutException;
import java.util.logging.Logger;

import io.github.young1lin.dto.*;
import io.github.young1lin.host.McpServerConfig;
import io.github.young1lin.util.JsonUtil;

/**
 * MCP 客户端，用于连接 MCP 服务器并获取工具列表
 */
public class MCPClient {

    private static final Logger logger = Logger.getLogger(MCPClient.class.getName());

    private final String serverName;

    private final String command;

    private final List<String> args;

    private final Map<String, String> env;

    private Process process;

    private BufferedReader reader;

    private BufferedWriter writer;

    private Thread errorReaderThread;

    private final List<ToolDefinition> tools = new ArrayList<>();

    public MCPClient(String serverName, McpServerConfig mcpServerConfig) {
        this.serverName = serverName;
        this.command = mcpServerConfig.getCommand();
        this.args = mcpServerConfig.getArgs() != null ? new ArrayList<>(mcpServerConfig.getArgs()) : new ArrayList<>();
        this.env = mcpServerConfig.getEnv() != null ? new HashMap<>(mcpServerConfig.getEnv()) : new HashMap<>();
    }

    public void connect() throws IOException, InterruptedException {
        // 准备环境变量
        Map<String, String> processEnv = new HashMap<>(System.getenv());
        processEnv.putAll(this.env);

        // 在 Windows 上强制使用 UTF-8 编码
        boolean isWindows = System.getProperty("os.name").toLowerCase().contains("win");
        if (isWindows) {
            processEnv.put("PYTHONIOENCODING", "utf-8");
        }

        // 构建命令
        List<String> commandList = new ArrayList<>();

        // 在 Windows 上，对于需要通过 shell 执行的命令（如 npx, npm, node），使用 cmd.exe /c
        // 这些命令通常是 .cmd 或 .bat 脚本，需要通过 cmd.exe 来执行
        if (isWindows && (command.endsWith(".cmd") || command.endsWith(".bat") ||
            command.equals("npx") || command.equals("npm") || command.equals("node"))) {
            commandList.add("cmd.exe");
            commandList.add("/c");
        }

        commandList.add(command);
        commandList.addAll(args);

        logger.info("Starting process with command: " + String.join(" ", commandList));

        // 创建进程构建器
        ProcessBuilder processBuilder = new ProcessBuilder(commandList);
        processBuilder.environment().putAll(processEnv);
        processBuilder.redirectErrorStream(false);

        // 启动进程
        process = processBuilder.start();

        // 创建输入输出流
        reader = new BufferedReader(new InputStreamReader(
                process.getInputStream(), StandardCharsets.UTF_8));
        writer = new BufferedWriter(new OutputStreamWriter(
                process.getOutputStream(), StandardCharsets.UTF_8));

        // 启动虚拟线程读取错误流，防止进程阻塞
        errorReaderThread = Thread.ofVirtual().start(() -> {
            try (BufferedReader errorReader = new BufferedReader(new InputStreamReader(
                    process.getErrorStream(), StandardCharsets.UTF_8))) {
                String line;
                while ((line = errorReader.readLine()) != null) {
                    // 将错误输出记录到日志，方便调试
                    logger.warning("[" + serverName + " stderr] " + line);
                }
            } catch (IOException e) {
                // 忽略错误流关闭时的异常
                if (process.isAlive()) {
                    logger.warning("Error reading stderr: " + e.getMessage());
                }
            }
        });

        // 给子进程一个短暂的启动时间，避免还未就绪就发送初始化请求
        if (process.isAlive()) {
            try {
                Thread.sleep(500);
            } catch (InterruptedException ignored) {
                Thread.currentThread().interrupt();
            }
        }

        // 发送 initialize 请求
        InitializeJSONRPCRequest initRequest = new InitializeJSONRPCRequest();
        String requestJson = JsonUtil.toJson(initRequest) + "\n";
        writer.write(requestJson);
        writer.flush();

        // 读取 initialize 响应
        String responseLine = readLineWithTimeout(reader, 30, TimeUnit.SECONDS);
        if (responseLine == null) {
            throw new IOException("Initialize failed: no response from server within timeout");
        }
        responseLine = responseLine.trim();
        InitializeJSONRPCResult initResponse = JsonUtil.parseJson(responseLine, InitializeJSONRPCResult.class);
        if (initResponse.isError()) {
            throw new IOException("Initialize failed: " + initResponse.getError());
        }

        // 发送 initialized 通知
        Map<String, Object> notification = new HashMap<>();
        notification.put("jsonrpc", "2.0");
        notification.put("method", "notifications/initialized");
        String notificationJson = JsonUtil.toJson(notification) + "\n";
        writer.write(notificationJson);
        writer.flush();

        // 获取工具列表
        listTools();
    }

    public void listTools() throws IOException {
        ListToolsJSONRPCRequest listRequest = new ListToolsJSONRPCRequest("list_tools", null);
        String requestJson = JsonUtil.toJson(listRequest) + "\n";
        writer.write(requestJson);
        writer.flush();

        // 读取响应
        String responseLine = reader.readLine();
        if (responseLine != null) {
            responseLine = responseLine.trim();
            ListToolsJSONRPCResult listResponse = JsonUtil.parseJson(responseLine, ListToolsJSONRPCResult.class);
            if (listResponse.isError()) {
                throw new IOException("List tools failed: " + listResponse.getError());
            }
            if (listResponse.getResult() != null) {
                @SuppressWarnings("unchecked")
                Map<String, Object> resultMap = (Map<String, Object>) listResponse.getResult();
                @SuppressWarnings("unchecked")
                List<Map<String, Object>> toolsData = (List<Map<String, Object>>) resultMap.get("tools");
                if (toolsData != null) {
                    tools.clear();
                    for (Map<String, Object> toolData : toolsData) {
                        ToolDefinition tool = JsonUtil.parseJson(JsonUtil.toJson(toolData), ToolDefinition.class);
                        tools.add(tool);
                    }
                }
            }
        }
    }

    public String callTool(String toolName, Map<String, Object> arguments) throws IOException {
        CallToolJSONRPCRequest callRequest = new CallToolJSONRPCRequest(toolName, null, arguments);
        String requestJson = JsonUtil.toJson(callRequest) + "\n";
        writer.write(requestJson);
        writer.flush();

        // 读取响应
        String responseLine = reader.readLine();
        if (responseLine != null) {
            responseLine = responseLine.trim();
            CallToolJSONRPCResult callResponse = JsonUtil.parseJson(responseLine, CallToolJSONRPCResult.class);
            if (callResponse.isError()) {
                throw new IOException("Call tool failed: " + callResponse.getError());
            }
            if (callResponse.getResult() != null) {
                @SuppressWarnings("unchecked")
                Map<String, Object> resultMap = (Map<String, Object>) callResponse.getResult();
                @SuppressWarnings("unchecked")
                List<Map<String, Object>> contentList = (List<Map<String, Object>>) resultMap.get("content");
                if (contentList != null) {
                    // 提取文本内容
                    List<String> texts = new ArrayList<>();
                    for (Map<String, Object> item : contentList) {
                        if ("text".equals(item.get("type"))) {
                            texts.add(String.valueOf(item.get("text")));
                        }
                    }
                    return String.join("\n", texts);
                }
            }
        }
        return "";
    }

    public void close() throws IOException, InterruptedException {
        if (writer != null) {
            writer.close();
        }
        if (reader != null) {
            reader.close();
        }
        if (errorReaderThread != null && errorReaderThread.isAlive()) {
            // 等待错误流读取线程结束（最多等待1秒）
            errorReaderThread.join(1000);
        }
        if (process != null) {
            process.destroy();
            process.waitFor();
        }
    }

    private String readLineWithTimeout(BufferedReader bufferedReader, long timeout, TimeUnit unit)
            throws IOException, InterruptedException {
        CompletableFuture<String> future = CompletableFuture.supplyAsync(() -> {
            try {
                return bufferedReader.readLine();
            } catch (IOException e) {
                throw new RuntimeException(e);
            }
        });
        try {
            return future.get(timeout, unit);
        } catch (TimeoutException e) {
            future.cancel(true);
            return null;
        } catch (ExecutionException e) {
            Throwable cause = e.getCause();
            if (cause instanceof IOException ioEx) {
                throw ioEx;
            }
            throw new IOException("Failed to read line", cause);
        }
    }

    public String getServerName() {
        return serverName;
    }

    public List<ToolDefinition> getTools() {
        return new ArrayList<>(tools);
    }
}
