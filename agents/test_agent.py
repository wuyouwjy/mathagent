# ============================================================
# agents/test_agent.py — 自动测试智能体
# 每次代码改动后自动运行 pytest 验证系统可用性
#
# 用法:
#   from agents.test_agent import TestAgent
#   agent = TestAgent()
#   result = agent.run_tests()       # 快速测试（跳过 LLM 相关）
#   result = agent.run_full_tests()  # 全量测试
# ============================================================

import subprocess
import sys
import os
from typing import Dict, Any, List
from loguru import logger


class TestAgent:
    """自动测试智能体 — 验证系统完整性"""

    def __init__(self):
        self.project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.last_result = None

    def run_tests(self, verbose: bool = False) -> Dict[str, Any]:
        """
        运行快速测试（跳过需要 LLM 调用的测试）

        返回:
            Dict: {"passed": int, "failed": int, "skipped": int, "status": str, "errors": List[str]}
        """
        logger.info("[TestAgent] 开始快速测试...")
        return self._run_pytest(["-q", "--tb=line"])

    def run_full_tests(self, verbose: bool = False) -> Dict[str, Any]:
        """
        运行全量测试

        返回:
            Dict: 同上
        """
        logger.info("[TestAgent] 开始全量测试...")
        return self._run_pytest(["-v", "--tb=short"])

    def _run_pytest(self, args: List[str]) -> Dict[str, Any]:
        """执行 pytest"""
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pytest", "tests/"] + args,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=120,
            )
            output = result.stdout + result.stderr

            # 解析结果
            passed = 0
            failed = 0
            skipped = 0
            for line in output.split("\n"):
                if "passed" in line and "=" in line:
                    import re
                    m = re.search(r'(\d+)\s+passed', line)
                    if m:
                        passed = int(m.group(1))
                    m = re.search(r'(\d+)\s+failed', line)
                    if m:
                        failed = int(m.group(1))
                    m = re.search(r'(\d+)\s+skipped', line)
                    if m:
                        skipped = int(m.group(1))

            status = "ok" if failed == 0 else "fail"
            self.last_result = {"passed": passed, "failed": failed, "skipped": skipped, "status": status}

            logger.info(f"[TestAgent] 测试完成: {passed} passed, {failed} failed, {skipped} skipped")
            return self.last_result

        except subprocess.TimeoutExpired:
            logger.error("[TestAgent] 测试超时")
            return {"passed": 0, "failed": 1, "skipped": 0, "status": "timeout"}
        except Exception as e:
            logger.error(f"[TestAgent] 测试异常: {e}")
            return {"passed": 0, "failed": 1, "skipped": 0, "status": "error", "error": str(e)}

    def check_imports(self) -> Dict[str, Any]:
        """检查所有关键模块是否可导入"""
        modules = [
            "user_agent", "llm_client", "run_competition",
            "agents", "agents.classifier_agent", "agents.graph_manager_agent",
            "agents.evaluation_agent", "agents.solver_dispatcher", "agents.test_agent",
            "agents.solver_experts.base_solver", "agents.solver_experts.solver_registry",
            "graph", "graph.nodes", "graph.graph_builder", "graph.workflow",
            "rag.retriever", "rag.cache.problem_cache",
            "mcp.tools", "mcp.server",
            "configs.settings", "schemas",
            "tools.intern_client", "tools.platform_adapter",
        ]
        ok, failed = [], []
        for m in modules:
            try:
                __import__(m)
                ok.append(m)
            except Exception as e:
                failed.append((m, str(e)))
        logger.info(f"[TestAgent] 导入检查: {len(ok)}/{len(modules)} 成功")
        return {"ok": ok, "failed": failed, "status": "ok" if not failed else "fail"}


def get_test_agent() -> TestAgent:
    """获取全局 TestAgent 单例"""
    if not hasattr(get_test_agent, "_instance"):
        get_test_agent._instance = TestAgent()
    return get_test_agent._instance
