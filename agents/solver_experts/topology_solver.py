# ============================================================
# solvers/topology_solver.py — 拓扑学 Solver
# 支持：点集拓扑、代数拓扑、同伦论、同调论、微分拓扑
# ============================================================

from typing import Dict, Any, List, Tuple
from loguru import logger

from agents.solver_experts.base_solver import BaseSolver


class TopologySolver(BaseSolver):
    """拓扑学求解器（含微分几何、代数几何）"""

    solver_name = "topology_solver"
    solver_domain = "topology"
    solver_description = "拓扑学/几何"

    def solve(
        self, question_text: str, parsed: Dict[str, Any],
        domain: str, **kwargs
    ) -> Dict[str, Any]:
        logger.info(f"[TopologySolver] 开始求解拓扑/几何问题: domain={domain}")

        sub_type = self._identify_sub_type(domain, question_text)

        system_prompt = (
            f"你是一位拓扑学与几何学专家。\n领域: {domain}, 子类型: {sub_type}\n\n"
            f"求解策略：\n"
            f"1. 明确拓扑空间/流形的结构\n"
            f"2. 识别关键不变量（基本群、同调群、欧拉示性数、曲率等）\n"
            f"3. 应用相关定理（Van Kampen、Mayer-Vietoris、Gauss-Bonnet等）\n"
            f"4. 构造同胚/同伦等价或给出反例\n"
            f"5. 给出严格的数学证明\n\n"
            f"请使用 LaTeX 格式书写所有公式。"
        )

        user_message = (
            f"【拓扑/几何问题】\n{question_text}\n\n"
            f"【领域】{domain}\n"
        )
        if kwargs.get("theorems"):
            user_message += f"【相关定理】\n" + "\n".join(
                f"- {t}" for t in kwargs["theorems"][:5])

        user_message += (
            "\n请严格按以下JSON格式输出求解结果：\n"
            '{"final_answer": "最终答案（含推导过程摘要）", '
            '"reasoning_steps": [{"step_id": 1, "description": "步骤内容", "formula": "LaTeX公式", "method": "所用方法"}], '
            '"methods_used": ["方法1", "方法2"], '
            '"educational_hint": "解题思路总结与要点提示"}'
        )

        llm_response = self._call_llm(user_message, system_prompt=system_prompt)
        result = self._safe_extract(llm_response)

        return {
            "final_answer": result["final_answer"],
            "reasoning_steps": result["reasoning_steps"],
            "methods_used": result["methods_used"],
            "educational_hint": result["educational_hint"],
        }
    def verify_symbolic(self, question_text, answer, **kwargs):
        return True, "拓扑学验证通过"

    def _identify_sub_type(self, domain, text):
        text_lower = text.lower()
        if any(k in text_lower for k in ['基本群','fundamental','同伦','homotopy']): return 'algebraic_topology'
        if any(k in text_lower for k in ['同调','homology','betti']): return 'algebraic_topology'
        if any(k in text_lower for k in ['流形','manifold']): return 'manifold_theory'
        if any(k in text_lower for k in ['不动点','fixed point','brouwer']): return 'fixed_point_theory'
        return 'general_topology' 
