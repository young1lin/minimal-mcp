package io.github.young1lin.host;

import java.io.InputStream;
import java.util.ArrayList;
import java.util.List;
import java.util.logging.*;

import io.github.young1lin.server.JsonRPCServer;
import io.github.young1lin.server.McpServer;
import io.github.young1lin.server.ServerSession;
import io.github.young1lin.tool.Tool;
import io.github.young1lin.util.ThreadAwareFormatter;

/**
 * MCP 服务器主入口
 */
public class McpServerHost {

    private static final Logger logger = Logger.getLogger(McpServerHost.class.getName());

    /**
     * 初始化日志配置，将日志输出到文件而不是控制台
     */
    private static void initLogging() {
        try {
            // 尝试从 resources 加载 logging.properties
            InputStream configStream = McpServerHost.class.getClassLoader()
                    .getResourceAsStream("logging.properties");
            if (configStream != null) {
                LogManager.getLogManager().readConfiguration(configStream);
                configStream.close();
            }

            // 无论是否加载了配置文件，都确保移除控制台处理器
            Logger rootLogger = Logger.getLogger("");
            Handler[] handlers = rootLogger.getHandlers();
            for (Handler handler : handlers) {
                // 移除控制台处理器（ConsoleHandler）
                if (handler.getClass().getName().equals("java.util.logging.ConsoleHandler")) {
                    rootLogger.removeHandler(handler);
                }
            }

            // 如果配置文件不存在或没有配置 FileHandler，手动添加
            boolean hasFileHandler = false;
            for (Handler handler : rootLogger.getHandlers()) {
                if (handler instanceof FileHandler) {
                    hasFileHandler = true;
                    break;
                }
            }

            if (!hasFileHandler) {
                FileHandler fileHandler = new FileHandler("mcp_server_%u.log", 10485760, 5, true);
                fileHandler.setLevel(Level.INFO);
                fileHandler.setFormatter(new ThreadAwareFormatter());
                rootLogger.addHandler(fileHandler);
                rootLogger.setLevel(Level.INFO);
            }
        } catch (Exception e) {
            // 如果配置失败，使用默认的文件日志配置
            try {
                Logger rootLogger = Logger.getLogger("");
                Handler[] handlers = rootLogger.getHandlers();
                for (Handler handler : handlers) {
                    rootLogger.removeHandler(handler);
                }
                FileHandler fileHandler = new FileHandler("mcp_server_%u.log", 10485760, 5, true);
                fileHandler.setLevel(Level.INFO);
                fileHandler.setFormatter(new ThreadAwareFormatter());
                rootLogger.addHandler(fileHandler);
                rootLogger.setLevel(Level.INFO);
            } catch (Exception ex) {
                // 如果还是失败，至少记录错误（使用 System.err，因为日志系统可能未初始化）
                System.err.println("Failed to configure logging: " + ex.getMessage());
            }
        }
    }

    public static void main(String[] args) {
        // 首先初始化日志配置
        initLogging();

        logger.info("=".repeat(50));
        logger.info("Starting MCP Server...");
        logger.info("=".repeat(50));

        // 解析命令行参数
        String arg1 = null;
        String arg2 = null;
        for (int i = 0; i < args.length; i++) {
            if ("--arg1".equals(args[i]) && i + 1 < args.length) {
                arg1 = args[i + 1];
                i++;
            } else if ("--arg2".equals(args[i]) && i + 1 < args.length) {
                arg2 = args[i + 1];
                i++;
            }
        }

        // 打印参数信息
        if (arg1 != null) {
            logger.info("参数1: " + arg1);
        } else {
            logger.info("没有提供参数1");
        }

        if (arg2 != null) {
            logger.info("参数2: " + arg2);
        } else {
            logger.info("没有提供参数2");
        }

        // 创建会话
        ServerSession session = new ServerSession();

        // 创建工具列表
        List<Tool> tools = new ArrayList<>();
        tools.add(session.getWeatherTool());
        tools.add(session.listGetWeatherRecordsTool());

        // 创建 MCP 服务器
        McpServer mcpServer = new McpServer(tools, session);

        // 创建 JSON RPC Server
        JsonRPCServer server = new JsonRPCServer();

        // 注册方法
        server.registerMethod("initialize", mcpServer.initializeMethod());
        server.registerMethod("notifications/initialized", mcpServer.notifyInitializeMethod());
        server.registerMethod("tools/list", mcpServer.listToolsMethod());
        server.registerMethod("tools/call", mcpServer.callToolMethod());

        // Notifications (these don't return responses)
        server.registerMethod("notifications/tools/list_changed", mcpServer.notifyToolChangeMethod());
        server.registerMethod("notifications/prompts/list_changed", mcpServer.notifyPromptChangeMethod());

        // Other methods that might be called
        server.registerMethod("prompts/list", mcpServer.listPromptsMethod());
        server.registerMethod("prompts/get", mcpServer.getPromptMethod());
        server.registerMethod("resources/list", mcpServer.listResourcesMethod());

        logger.info("All methods registered, server starting...");

        try {
            server.start();
        } catch (Exception e) {
            logger.severe("Server error: " + e.getMessage());
            e.printStackTrace();
        } finally {
            logger.info("Server shutting down");
            System.exit(0);
        }
    }

}

