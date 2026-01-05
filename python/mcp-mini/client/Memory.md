# Memory.md - mcp-mini 项目说明

## 项目概述

mcp-mini 是一个轻量级的 MCP (Model Context Protocol) 实现项目，用于演示和学习 MCP 协议的工作原理。

## 项目结构

```
python/mcp-mini/
├── client/                  # MCP 客户端实现
│   ├── mcp_client_function_calling_claude_code_like.py  # Claude Code 风格客户端
│   ├── mcp_client_function_calling_reasoner.py          # Reasoner 客户端
│   ├── mcp_client_function_calling.py                   # Function Calling 客户端
│   └── tools.py                                        # 内置工具实现
├── mcp_server.py              # MCP 服务器实现
├── pyproject.toml             # 项目配置
└── uv.lock                    # 依赖锁定文件
```

## 运行方式

本项目使用 `uv` 作为包管理器。

### 安装依赖
```bash
cd python/mcp-mini
uv sync
```

### 运行代码
```bash
uv run python mcp_server.py          # 启动 MCP 服务器
uv run python client/mcp_client_function_calling_claude_code_like.py  # 启动客户端
```

## 配置说明

1. **环境变量**：在 `.env` 文件中配置 `DEEPSEEK_API_KEY`
2. **MCP 服务器配置**：在 `client/mcp-claude-code.json` 中配置服务器信息

## 核心功能

- 支持 MCP 服务器连接和工具调用
- Function Calling 风格的工具调用
- Claude Code 风格的交互体验
- 支持在工具执行过程中按 ESC 键中断执行
