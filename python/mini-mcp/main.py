import logging
from .mcp_host import MCPHub, Connection

# 配置logging输出到main.log文件
logging.basicConfig(
    level=logging.INFO,
    filename="main.log",
    filemode="w",  # 'w' 表示覆盖写入，'a' 表示追加写入
    format="%(asctime)s - %(levelname)s - %(message)s",
)

if __name__ == "__main__":
    hub: MCPHub = MCPHub()
    connections: list[Connection] = hub.get_connections()
    for connection in connections:
        logging.info(connection.server.name)
        logging.info(connection.client.list_tools())
    hub.dispose()
