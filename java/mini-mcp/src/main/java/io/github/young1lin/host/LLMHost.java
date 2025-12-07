package io.github.young1lin.host;

import java.io.IOException;
import java.io.InputStream;
import java.util.Map;
import java.util.Properties;
import java.util.Scanner;
import java.util.logging.Logger;

import io.github.young1lin.client.ChatBot;
import io.github.young1lin.client.MCPClient;
import io.github.young1lin.util.MCPConfigUtil;

/**
 * LLM Host - MCP 客户端主程序入口
 */
public class LLMHost {

    private static final Logger logger = Logger.getLogger(LLMHost.class.getName());

    private static final String BASE_SYSTEM_PROMPT = """
            你是D-Cline，是一个优秀的Agent，你精通软件工程，精通各种编程语言、框架、设计模式以及代码的最佳实践。

            ===
            你有一系列的工具可以使用，你每个消息可以使用一个工具，并且会接收到用户响应调用工具的结果，在调用工具前，你必须 thinking step by step。

            # 输出格式要求

            你的回复必须严格遵循以下 XML 格式：

            **第一步：思考过程**
            首先，你必须使用 `<thinking></thinking>` 标签包裹你的思考过程，格式如下：

            <thinking>
            [在这里详细说明你的思考过程，包括：
            - 分析用户的需求
            - 确定需要使用的工具
            - 说明为什么选择这个工具
            - 准备工具调用所需的参数]
            </thinking>

            **第二步：工具调用或最终答案**
            在思考过程之后，你可以选择：
            1. 调用工具获取更多信息
            2. 使用 final_answer 工具返回最终答案

            **重要**：
            1. 思考过程必须使用 `<thinking></thinking>` 标签包裹
            2. 思考过程和工具调用必须分开展示，先思考后调用
            3. 所有 XML 标签必须正确闭合
            4. 当你已经收集到足够的信息可以回答用户问题时，必须使用 final_answer 工具

            # 工具使用格式

            工具调用使用 XML 格式，XML 格式必须和下面一致。

            <tool_name>
            <parameter1_name>value1</parameter1_name>
            <parameter2_name>value2</parameter2_name>
            ...
            </tool_name>

            样例1：
            <read_file>
            <path>src/main.js</path>
            <task_progress>Checklist here (optional)</task_progress>
            </read_file>

            样例2：
            <final_answer>
            <answer>这是我的最终答案，已经完成了用户的所有要求。</answer>
            </final_answer>

            # Tools
            你将有以下工具可以调用

            ## ls
            描述：列出目录内容
            参数：
            - path：目录路径
            使用：

            <ls>
            <path>目录路径</path>
            </ls>

            ## read_file
            描述：读取文件内容
            参数：
            - path：文件路径
            - task_progress：任务进度（可选）
            使用：

            <read_file>
            <path>文件路径</path>
            <task_progress>任务进度（可选）</task_progress>
            </read_file>

            ## final_answer
            描述：当你已经完成任务或收集到足够信息回答用户问题时，使用此工具返回最终答案
            参数：
            - answer：你的最终答案内容
            使用：

            <final_answer>
            <answer>你的最终答案</answer>
            </final_answer>

            **重要**: 当你完成了用户的任务或者已经有足够的信息回答用户问题时，你必须调用 final_answer 工具。不要重复调用其他工具。

            # 使用 MCP tool
            描述：请求使用由连接的 MCP 服务器提供的工具。每个 MCP 服务器可以提供多个具有不同功能的工具。工具具有定义的输入模式，用于指定必需和可选参数。
            参数：
            - server_name: (必需) 提供工具的 MCP 服务器名称
            - tool_name: (必需) 要执行的工具名称
            - arguments: (必需) 包含工具输入参数的 JSON 对象，遵循工具的输入模式
            用法：

            <use_mcp_tool>
            <server_name>server name here</server_name>
            <tool_name>tool name here</tool_name>
            <arguments>
            {
              "param1": "value1",
              "param2": "value2"
            }
            </arguments>
            </use_mcp_tool>

            ===
            # MCP Server
            {MCP_SERVERS_SECTION}
            """;

    public static void main(String[] args) throws IOException {
        // 获取 API Key
        String apiKey = System.getenv("DEEPSEEK_API_KEY");
        if (apiKey == null || apiKey.isEmpty()) {
            InputStream envInputStream = LLMHost.class.getClassLoader().getResourceAsStream("env.properties");
            if (envInputStream != null) {
                Properties properties = new Properties();
                properties.load(envInputStream);
                apiKey = properties.getProperty("DEEPSEEK_API_KEY");
            }
        }

        if (apiKey == null || apiKey.isEmpty()) {
            System.err.println("错误：未找到 DEEPSEEK_API_KEY 环境变量");
            System.exit(1);
        }

        // obtain mcp.json
        InputStream mcpJsonInputStream = LLMHost.class.getClassLoader().getResourceAsStream("mcp.json");

        try {
            // 初始化 MCP 服务器
            System.out.println("正在初始化 MCP 服务器...");
            Map<String, MCPClient> mcpClients = MCPConfigUtil.initializeMCPServers(mcpJsonInputStream);

            // 动态构建 system prompt
            String mcpServersSection = MCPConfigUtil.buildMCPServersSection(mcpClients);
            String systemPrompt = BASE_SYSTEM_PROMPT.replace("{MCP_SERVERS_SECTION}", mcpServersSection);
            System.out.println("注入的 MCP Server 及其工具：\n" + mcpServersSection);

            System.out.println("=".repeat(50));
            System.out.println("MCP 客户端已就绪，开始交互式对话");
            System.out.println("输入 'exit' 或 'quit' 退出程序\n");

            // 创建 ChatBot
            ChatBot chatbot = new ChatBot(apiKey, systemPrompt, mcpClients);

            Scanner scanner = new Scanner(System.in);
            try {
                while (true) {
                    // 获取用户输入
                    System.out.print("\n你: ");
                    String userInput = scanner.nextLine().trim();

                    // 检查退出命令
                    if (userInput.toLowerCase().matches("exit|quit|退出")) {
                        System.out.println("\n再见！");
                        break;
                    }

                    // 如果输入为空，跳过
                    if (userInput.isEmpty()) {
                        continue;
                    }

                    // 输出分隔符
                    System.out.print("\n助手: ");

                    // 流式输出回复
                    chatbot.chat(userInput, new ChatBot.ChatResponseHandler() {
                        @Override
                        public void onContent(String content) {
                            System.out.print(content);
                            System.out.flush();
                        }

                        @Override
                        public void onToolResult(String result) {
                            System.out.print("\n[tool_result]\n" + result + "\n\n");
                            System.out.flush();
                        }

                        @Override
                        public void onFinalAnswer(String answer) {
                            System.out.print("\n[final_answer]\n" + answer + "\n");
                            System.out.flush();
                        }
                    });

                    // 回复完成后换行
                    System.out.println();
                }
            } catch (Exception e) {
                System.err.println("\n程序被用户中断或发生错误: " + e.getMessage());
                e.printStackTrace();
            } finally {
                // 关闭所有 MCP 连接
                System.out.println("\n正在关闭 MCP 连接...");
                for (MCPClient client : mcpClients.values()) {
                    try {
                        client.close();
                    } catch (Exception e) {
                        logger.warning("关闭 MCP 客户端失败: " + e.getMessage());
                    }
                }
                System.out.println("已关闭所有连接");
                scanner.close();
            }
        } catch (IOException e) {
            System.err.println("初始化失败: " + e.getMessage());
            e.printStackTrace();
            System.exit(1);
        }
    }
}
