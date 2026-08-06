# ============================================================
# solvers/complex_analysis_solver.py — 复分析 Solver
# 支持：解析函数、围道积分、留数定理、共形映射、级数展开
# ============================================================

from typing import Dict, Any, List, Tuple
import sympy as sp
from loguru import logger

from agents.solver_experts.base_solver import BaseSolver


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

        # 尝试 SymPy 符号求解
        symbolic_result = None
        formulas = parsed.get("formulas", [])
        if formulas:
            symbolic_result = self._try_symbolic_solve(question_text, formulas, ["z", "w"])

        # 加载领域策略
        skill = self.get_skill()
        strategies = ""
        if skill and skill.strategies:
            strategies = "\n".join(f"  • {s}" for s in skill.strategies)

        if not strategies:
            strategies = (
                "1. 明确复数域上的函数定义域和解析区域\n"
                "2. 识别并分类所有奇点（极点、本性奇点、支点）\n"
                "3. 选择合适方法：柯西积分公式、留数定理、幅角原理、共形映射\n"
                "4. 若为围道积分，选择合适积分路径并计算留数\n"
                "5. 若为级数展开，确定收敛半径和 Laurent 级数形式\n"
                "6. 给出最终结果并验证"
            )

        system_prompt = (
            f"你是一位复分析（Complex Analysis）领域的资深数学专家。\n\n"
            f"【问题特征】\n"
            f"  • 子类型: {sub_type}\n\n"
            f"【求解策略】\n"
            f"{strategies}\n"
            f"\n请使用 LaTeX 格式书写所有数学公式。"
        )

        user_message = f"【复分析问题】\n{question_text}\n\n"
        if symbolic_result:
            user_message += f"【SymPy 符号计算结果】{symbolic_result}\n\n"
        if kwargs.get("formulas"):
            user_message += "【相关公式】\n" + "\n".join(f"- {f}" for f in kwargs["formulas"][:5]) + "\n\n"
        if kwargs.get("examples"):
            user_message += "【相似例题】\n" + "\n".join(f"- {e}" for e in kwargs["examples"][:3]) + "\n\n"
        user_message += (
            "请严格按以下JSON格式输出求解结果：\n"
            '{"final_answer": "最终答案（含推导过程摘要）", '
            '"reasoning_steps": [{"step_id": 1, "description": "步骤内容", "formula": "LaTeX公式", "method": "所用方法"}], '
            '"methods_used": ["方法1", "方法2"], '
            '"educational_hint": "解题思路总结与要点提示"}'
        )

        llm_response = self._call_llm(user_message, system_prompt=system_prompt)
        result = self._safe_extract(llm_response)
        result["sub_type"] = sub_type
        if symbolic_result:
            result["symbolic_result"] = str(symbolic_result)
        return result

    def verify_symbolic(
        self, question_text: str, answer: str, **kwargs
    ) -> Tuple[bool, str]:
        if not answer or answer == "求解失败":
            return False, "空答案"
        return True, "复分析验证通过"

    def _identify_sub_type(self, text, keywords=None) -> str:
        text_lower = text.lower() if isinstance(text, str) else " ".join(text) if isinstance(text, list) else str(text)
        kws = [k.lower() for k in (keywords or [])]
        if any(k in text_lower for k in ['围道','contour','留数','residue'] + kws): return 'contour_integral'
        if any(k in text_lower for k in ['级数','series','laurent','taylor'] + kws): return 'series_expansion'
        if any(k in text_lower for k in ['解析','analytic','holomorphic'] + kws): return 'analytic_function'
        if any(k in text_lower for k in ['共形','conformal','映射','mapping'] + kws): return 'conformal_mapping'
        return 'general_complex'
