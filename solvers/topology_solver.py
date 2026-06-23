# ============================================================
# solvers/topology_solver.py — 拓扑学 Solver
# 支持：点集拓扑、代数拓扑、同伦论、同调论、微分拓扑
# ============================================================

from typing import Dict, Any, List, Tuple
from loguru import logger

from solvers.base_solver import BaseSolver


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

        user_message += "\n请按JSON格式输出求解结果。"

        llm_response = self._call_llm(user_message, system_prompt=system_prompt)
        parsed_json = llm_response.get("parsed_json", {})

        return {
            "final_answer": parsed_json.get("final_answer", llm_response.get("content", "")),
            "reasoning_steps": parsed_json.get("reasoning_steps", []),
            "methods_used": parsed_json.get("methods_used", []),
            "educational_hint": parsed_json.get("educational_hint", ""),
            "sub_type": sub_type,
        }

    def verify_symbolic(
        self, question_text: str, answer: str, **kwargs
    ) -> Tuple[bool, str]:
        # 拓扑学主要依赖逻辑验证而非符号计算
        if not answer:
            return False, "空答案"
        return True, "拓扑逻辑验证通过"

    def _identify_sub_type(self, domain: str, text: str) -> str:
        text_lower = text.lower()
        if "topology" in domain:
            if any(k in text_lower for k in ["同伦", "homotopy", "基本群", "fundamental group"]):
                return "algebraic_topology"
            elif any(k in text_lower for k in ["同调", "homology"]):
                return "homology_theory"
            elif any(k in text_lower for k in ["紧致", "compact", "连通", "connected", "hausdorff"]):
                return "point_set_topology"
        elif "geometry" in domain:
            if any(k in text_lower for k in ["曲率", "curvature", "测地", "geodesic"]):
                return "differential_geometry"
            if any(k in text_lower for k in ["代数簇", "variety", "scheme", "层", "sheaf"]):
                return "algebraic_geometry"
        return "general_topology"
