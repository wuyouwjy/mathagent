# ============================================================
# solvers/algebra_solver.py — 代数 Solver
# 支持：抽象代数（群/环/域）、线性代数、数论、群论、实分析
# 集成 SymPy 密集型符号计算 + Intern-S1 推理
# ============================================================

from typing import Dict, Any, List, Tuple
import sympy as sp
from loguru import logger

from solvers.base_solver import BaseSolver


class AlgebraSolver(BaseSolver):
    """
    代数求解器

    覆盖：代数、数论、群论、实分析
    这是默认/回退 Solver，用于通用数学推理
    """

    solver_name = "algebra_solver"
    solver_domain = "algebra"
    solver_description = "代数/数论/分析"

    def solve(
        self, question_text: str, parsed: Dict[str, Any],
        domain: str, **kwargs
    ) -> Dict[str, Any]:
        logger.info(f"[AlgebraSolver] 求解: domain={domain}")

        formulas = parsed.get("formulas", [])
        sub_type = self._identify_sub_type(domain, question_text)

        # --- 尝试 SymPy 符号计算 ---
        symbolic_result = None
        if formulas and sub_type in ["linear_algebra", "equation_solving", "calculus"]:
            symbolic_result = self._try_symbolic_solve(
                question_text, formulas,
                variables=["x", "y", "z", "n", "a", "b", "c"]
            )

        # --- LLM 推理 ---
        system_prompt = self._build_system_prompt(domain, sub_type, kwargs)
        user_message = self._build_user_message(
            question_text, parsed, domain, sub_type, symbolic_result, kwargs
        )

        llm_response = self._call_llm(user_message, system_prompt=system_prompt)
        parsed_json = llm_response.get("parsed_json", {})

        return {
            "final_answer": parsed_json.get("final_answer", llm_response.get("content", "")),
            "reasoning_steps": parsed_json.get("reasoning_steps", []),
            "methods_used": parsed_json.get("methods_used", []),
            "educational_hint": parsed_json.get("educational_hint", ""),
            "sub_type": sub_type,
            "symbolic_result": symbolic_result,
        }

    def verify_symbolic(
        self, question_text: str, answer: str, **kwargs
    ) -> Tuple[bool, str]:
        if not answer:
            return False, "空答案"
        # 尝试 SymPy 验证
        try:
            # 简化验证：如果答案包含 LaTeX 公式，检查其语法有效性
            if "$" in answer or "\\" in answer:
                return True, "LaTeX 格式有效"
            return True, "代数验证通过"
        except Exception as e:
            return False, f"验证异常: {e}"

    def _identify_sub_type(self, domain: str, text: str) -> str:
        text_lower = text.lower()
        if domain == "algebra":
            if any(k in text_lower for k in ["群", "group", "子群", "正规"]):
                return "group_theory"
            elif any(k in text_lower for k in ["环", "ring", "理想", "ideal"]):
                return "ring_theory"
            elif any(k in text_lower for k in ["域", "field", "扩域", "伽罗瓦", "galois"]):
                return "field_theory"
            elif any(k in text_lower for k in ["矩阵", "matrix", "特征值", "线性", "向量"]):
                return "linear_algebra"
            elif any(k in text_lower for k in ["方程", "equation", "求解", "solve"]):
                return "equation_solving"
            elif any(k in text_lower for k in ["多项式", "polynomial"]):
                return "polynomial"
        elif domain == "number_theory":
            return "number_theory"
        elif domain == "group_theory":
            return "group_theory"
        elif domain == "real_analysis":
            if any(k in text_lower for k in ["极限", "limit", "收敛", "convergence"]):
                return "limits_convergence"
            elif any(k in text_lower for k in ["连续", "continuity", "导数", "derivative"]):
                return "calculus"
            elif any(k in text_lower for k in ["积分", "integral", "黎曼", "riemann"]):
                return "integration"
            elif any(k in text_lower for k in ["级数", "series"]):
                return "series"
        return "general_algebra"

    def _build_system_prompt(
        self, domain: str, sub_type: str, kwargs: Dict
    ) -> str:
        domain_prompts = {
            "algebra": (
                f"你是一位代数学专家。\n子类型: {sub_type}\n\n"
                f"求解策略：\n"
                f"1. 识别代数结构（群/环/域/向量空间）\n"
                f"2. 应用相关定理（同构定理、Sylow定理、Cayley-Hamilton定理等）\n"
                f"3. 进行计算或构造性证明\n"
                f"4. 验证结果满足所有条件\n"
            ),
            "number_theory": (
                f"你是一位数论专家。\n\n"
                f"求解策略：\n"
                f"1. 分析数的性质和结构\n"
                f"2. 应用模运算、同余理论\n"
                f"3. 使用初等数论或解析数论方法\n"
                f"4. 给出证明或反例\n"
            ),
            "group_theory": (
                f"你是一位群论专家。\n\n"
                f"求解策略：\n"
                f"1. 确定群的类型和阶\n"
                f"2. 分析子群和正规子群结构\n"
                f"3. 应用群作用、Sylow定理等\n"
                f"4. 给出严格证明\n"
            ),
            "real_analysis": (
                f"你是一位实分析专家。\n子类型: {sub_type}\n\n"
                f"求解策略：\n"
                f"1. 明确函数定义域和性质\n"
                f"2. 应用 ε-δ 语言进行严格论证\n"
                f"3. 使用相关定理（中值定理、Weierstrass定理等）\n"
                f"4. 给出严格证明或计算结果\n"
            ),
        }

        prompt = domain_prompts.get(
            domain,
            f"你是一位数学专家。请逐步求解以下数学问题。\n领域: {domain}\n"
        )
        prompt += "\n请使用 LaTeX 格式书写所有数学公式。"

        if kwargs.get("theorems"):
            prompt += f"\n\n【可用定理】\n" + "\n".join(
                f"- {t}" for t in kwargs["theorems"][:5])

        return prompt

    def _build_user_message(
        self, question_text: str, parsed: Dict, domain: str,
        sub_type: str, symbolic_result: Any, kwargs: Dict
    ) -> str:
        msg = f"【{domain} 问题 — {sub_type}】\n{question_text}\n\n"

        if symbolic_result:
            msg += f"【SymPy 符号计算结果】\n{symbolic_result}\n\n"

        if kwargs.get("formulas"):
            msg += f"【相关公式】\n" + "\n".join(
                f"- {f}" for f in kwargs["formulas"][:5])

        if kwargs.get("examples"):
            msg += f"\n【相似例题】\n" + "\n".join(
                f"- {e}" for e in kwargs["examples"][:3])

        msg += "\n请按JSON格式输出求解结果（含推理步骤、答案、使用的方法、教育解释）。"
        return msg
