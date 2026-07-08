# ============================================================
# mcp/server.py — MCP 服务器
# 使用 FastMCP 将 Math-Agent-System 暴露为 MCP 服务
#
# 启动方式:
#   python -m mcp.server          # 独立进程
#   python run.py --mode mcp      # CLI 模式
# ============================================================

import sys
import os

# 确保项目根目录在 sys.path 中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loguru import logger

# 尝试导入 FastMCP
try:
    from mcp.server import FastMCP
    HAS_FASTMCP = True
except ImportError:
    HAS_FASTMCP = False
    logger.warning("[MCP] FastMCP 未安装，使用回退模式。安装: pip install mcp")


# ============================================================
# 创建 MCP 服务器
# ============================================================

if HAS_FASTMCP:
    mcp_server = FastMCP(
        "Math-Agent-System",
        description="基于 LangGraph + Intern-S1 的多领域数学自动求解智能体系统",
        version="1.0.0",
    )

    # 注册所有工具
    from mcp.tools import register_all_tools
    register_all_tools(mcp_server)
else:
    mcp_server = None


# ============================================================
# 回退模式：CLI 交互式 MCP 模拟
# ============================================================

class FallbackMCPServer:
    """回退 MCP 服务器（当 FastMCP 不可用时）"""

    def __init__(self):
        from mcp.tools import TOOL_REGISTRY
        self.tools = TOOL_REGISTRY

    def run_interactive(self):
        """交互式运行（用于测试和演示）"""
        print("\n" + "=" * 60)
        print("[Math-Agent-System MCP Server] 交互模式")
        print("=" * 60)
        print("可用工具:")
        for i, name in enumerate(self.tools.keys(), 1):
            print(f"  {i}. {name}")
        print("\n输入工具名称调用，输入 'quit' 退出")
        print("=" * 60)

        while True:
            try:
                cmd = input("\n> ").strip()
                if not cmd:
                    continue
                if cmd.lower() in ["quit", "exit", "q"]:
                    break
                if cmd.lower() == "list":
                    for i, name in enumerate(self.tools.keys(), 1):
                        print(f"  {i}. {name}")
                    continue

                # 查找工具
                func = self.tools.get(cmd)
                if func is None:
                    print(f"未知工具: {cmd}")
                    continue

                # 获取参数
                import inspect
                sig = inspect.signature(func)
                params = {}
                for param_name, param in sig.parameters.items():
                    if param.default is inspect.Parameter.empty:
                        val = input(f"  {param_name}: ").strip()
                        if param.annotation == int:
                            val = int(val) if val else param.default
                        elif param.annotation == float:
                            val = float(val) if val else param.default
                        elif param.annotation == bool:
                            val = val.lower() in ["true", "1", "yes"]
                        params[param_name] = val
                    else:
                        # 有默认值的参数
                        prompt = f"  {param_name} (默认: {param.default}): "
                        val = input(prompt).strip()
                        if val:
                            if param.annotation == int:
                                val = int(val)
                            elif param.annotation == float:
                                val = float(val)
                            elif param.annotation == bool:
                                val = val.lower() in ["true", "1", "yes"]
                            params[param_name] = val

                print(f"\n调用 {cmd}...")
                result = func(**params)
                print(f"\n结果:\n{_format_result(result)}")

            except KeyboardInterrupt:
                print("\n退出")
                break
            except Exception as e:
                print(f"错误: {e}")


def _format_result(result, indent: int = 0) -> str:
    """格式化结果输出"""
    import json
    prefix = "  " * indent
    if isinstance(result, dict):
        return json.dumps(result, ensure_ascii=False, indent=2)
    elif isinstance(result, list):
        if not result:
            return "[]"
        items = []
        for item in result[:5]:  # 最多显示5项
            if isinstance(item, (dict, list)):
                items.append(_format_result(item, indent + 1))
            else:
                items.append(f"{prefix}  - {str(item)[:120]}")
        if len(result) > 5:
            items.append(f"{prefix}  ... (共{len(result)}项)")
        return "\n".join(items)
    else:
        return str(result)[:500]


# ============================================================
# 启动入口
# ============================================================

def run_mcp_server(mode: str = "stdio"):
    """
    启动 MCP 服务器

    参数:
        mode: 运行模式
            - "stdio": 标准输入输出模式（默认，供 MCP 客户端连接）
            - "interactive": 交互式模式（用于测试和演示）
    """
    if HAS_FASTMCP and mode == "stdio":
        logger.info("[MCP] 启动 FastMCP 服务器 (stdio 模式)...")
        mcp_server.run()
    else:
        logger.info("[MCP] 使用回退交互模式...")
        fallback = FallbackMCPServer()
        fallback.run_interactive()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Math-Agent-System MCP Server")
    parser.add_argument("--mode", choices=["stdio", "interactive"], default="interactive",
                        help="运行模式 (default: interactive)")
    args = parser.parse_args()
    run_mcp_server(args.mode)
