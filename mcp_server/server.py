# mcp_server/server.py
"""MCP 服务器主入口"""

from fastmcp import FastMCP

# 创建 MCP 服务器实例
mcp = FastMCP(
    name="dailylaid-tools",
    instructions="Dailylaid 日常事务管理工具集"
)

# 注册工具
from .tools import register_schedule_tools
register_schedule_tools(mcp)


if __name__ == "__main__":
    mcp.run()
