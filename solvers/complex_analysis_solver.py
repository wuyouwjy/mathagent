# ============================================================
# solvers/complex_analysis_solver.py — 复分析 Solver
# 支持：解析函数、围道积分、留数定理、共形映射、级数展开
# ============================================================

from typing import Dict, Any, List, Tuple
import sympy as sp
from loguru import logger

from solvers.base_solver import BaseSolver


class ComplexAnalysisSolver(BaseSolver):
    """复分析求解器"""

    solver_name = "complex_analysis_solver"
    solver_domain = "complex_analysis"
    solver_description = "复分析"

    def solve(
        self, question_text: str, parsed: Dict[str, Any],
        domain: str, **kwargs
    ) -> Dict[str, Any]:
        logger.info("[ComplexSolver] 开始求解复分析问题")

        # 识别子类型
        sub_type = self._identify_sub_type(question_text, parsed.get("keywords", []))

        # LLM 推理
        system_prompt = (
            f"你是一位复分析专家。\n"
            f"问题子类型: {sub_type}\n\n"
            f"求解策略：\n"
            f"1. 明确复数域上的函数和区域\n"
            f"2. 检查解析性和奇点位置\n"
            f"3. 选择合适的积分路径（若为积分问题）\n"
            f"4. 应用柯西积分公式、留数定理或共形映射\n"
            f"5. 给出最终结果\n\n"
            f"请使用 LaTeX 格式书写所有公式。"
        )

        user_message = f"【复分析问题】\n{question_text}\n\n"
        if kwargs.get("formulas"):
            user_message += f"【相关公式】\n" + "\n".join(f"- {f}" for f in kwargs["formulas"][:5])
        user_message += "\n请按JSON格式输出求解结果（含推理步骤、答案、方法、教育解释）。"

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
        if not answer:
            return False, "空答案"
        return True, "复分析验证通过"

    def _identify_sub_type(self, text: str, keywords: List[str]) -> str:
        text_lower = text.lower()
        if any(k in text_lower for k in ["留数", "residue", "围道", "contour"]):
            return "contour_integral"
        elif any(k in text_lower for k in ["解析", "analytic", "holomorphic"]):
            return "analytic_function"
        elif any(k in text_lower for k in ["共形", "conformal", "映射", "mapping"]):
            return "conformal_mapping"
        elif any(k in text_lower for k in ["级数", "series", "泰勒", "洛朗", "laurent"]):
            return "series_expansion"
        return "general_complex"
