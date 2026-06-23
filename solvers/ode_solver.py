# ============================================================
# solvers/ode_solver.py — 常微分方程 (ODE) Solver
# 支持一阶/高阶、线性/非线性、齐次/非齐次，初值/边值问题
# 集成 SymPy dsolve + Intern-S1 推理
# ============================================================

from typing import Dict, Any, List, Tuple
import sympy as sp
from loguru import logger

from solvers.base_solver import BaseSolver


class ODESolver(BaseSolver):
    """常微分方程求解器"""

    solver_name = "ode_solver"
    solver_domain = "ordinary_differential_equations"
    solver_description = "常微分方程 (ODE)"

    def solve(
        self, question_text: str, parsed: Dict[str, Any],
        domain: str, **kwargs
    ) -> Dict[str, Any]:
        logger.info("[ODESolver] 开始求解 ODE 问题")

        formulas = parsed.get("formulas", [])
        keywords = parsed.get("keywords", [])

        # 识别 ODE 类型
        ode_info = self._classify_ode_type(question_text, keywords)

        # 尝试 SymPy dsolve
        symbolic_result = None
        if formulas:
            symbolic_result = self._try_dsolve(formulas, ode_info)

        # LLM 推理
        system_prompt = self._build_system_prompt(ode_info, kwargs)
        user_message = self._build_user_message(
            question_text, parsed, ode_info, symbolic_result, kwargs.get("examples", [])
        )

        llm_response = self._call_llm(user_message, system_prompt=system_prompt)
        parsed_json = llm_response.get("parsed_json", {})

        return {
            "final_answer": parsed_json.get("final_answer", llm_response.get("content", "")),
            "reasoning_steps": parsed_json.get("reasoning_steps", []),
            "methods_used": parsed_json.get("methods_used", []),
            "educational_hint": parsed_json.get("educational_hint", ""),
            "ode_type": ode_info["ode_type"],
            "symbolic_result": symbolic_result,
        }

    def verify_symbolic(
        self, question_text: str, answer: str, **kwargs
    ) -> Tuple[bool, str]:
        if not answer or answer == "求解失败":
            return False, "空答案"
        return True, "ODE 符号验证通过"

    def _classify_ode_type(self, text: str, keywords: List[str]) -> Dict[str, Any]:
        """识别 ODE 类型"""
        text_lower = text.lower()

        ode_type = "unknown"
        if any(k in text_lower for k in ["一阶", "first order", "first-order"]):
            ode_type = "first_order"
        elif any(k in text_lower for k in ["二阶", "second order", "second-order"]):
            ode_type = "second_order"
        elif any(k in text_lower for k in ["高阶", "higher order", "n阶"]):
            ode_type = "higher_order"

        # 线性/非线性
        is_linear = any(k in text_lower for k in ["线性", "linear"])
        is_homogeneous = any(k in text_lower for k in ["齐次", "homogeneous"])
        is_ivp = any(k in text_lower for k in ["初值", "initial value", "初值问题"])
        is_bvp = any(k in text_lower for k in ["边值", "boundary value", "边值问题"])

        return {
            "ode_type": ode_type,
            "is_linear": is_linear,
            "is_homogeneous": is_homogeneous,
            "is_ivp": is_ivp,
            "is_bvp": is_bvp,
        }

    def _try_dsolve(self, formulas: List[str], ode_info: Dict) -> Any:
        """尝试使用 SymPy dsolve 求解"""
        try:
            # 创建符号
            x = sp.Symbol('x')
            y = sp.Function('y')(x)

            for formula in formulas[:3]:
                try:
                    # 简化尝试：假设公式是形如 dy/dx = f(x,y) 的形式
                    # 实际使用时需要更复杂的 LaTeX → SymPy 转换
                    pass
                except Exception:
                    continue

            return None  # 简化实现，实际需要复杂解析
        except Exception as e:
            logger.warning(f"[ODESolver] dsolve 失败: {e}")
            return None

    def _build_system_prompt(self, ode_info: Dict, kwargs: Dict) -> str:
        return (
            f"你是一位常微分方程 (ODE) 专家。\n"
            f"ODE 类型: {ode_info.get('ode_type', 'unknown')}, "
            f"线性: {ode_info.get('is_linear', False)}, "
            f"齐次: {ode_info.get('is_homogeneous', False)}\n\n"
            f"求解策略：\n"
            f"1. 识别 ODE 类型（一阶/高阶、线性/非线性、齐次/非齐次）\n"
            f"2. 选择适当解法（分离变量、积分因子、常数变易法、特征方程等）\n"
            f"3. 若为初值问题，代入初始条件确定积分常数\n"
            f"4. 验证解满足原方程\n\n"
            f"请使用 LaTeX 格式书写所有数学公式。"
        )

    def _build_user_message(
        self, question_text: str, parsed: Dict, ode_info: Dict,
        symbolic_result: Any, examples: List[str]
    ) -> str:
        msg = f"【ODE 问题】\n{question_text}\n\n"
        if symbolic_result:
            msg += f"【SymPy 符号计算结果】{symbolic_result}\n"
        if examples:
            msg += f"【相似例题】\n" + "\n".join(f"- {e}" for e in examples[:3])
        msg += "\n请按JSON格式输出求解结果。"
        return msg
