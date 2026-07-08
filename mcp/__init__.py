# ============================================================
# mcp/__init__.py — MCP 模块入口
# 将 Math-Agent-System 的能力暴露为 MCP (Model Context Protocol) 工具
# ============================================================

from mcp.server import mcp_server, run_mcp_server
from mcp.tools import register_all_tools
