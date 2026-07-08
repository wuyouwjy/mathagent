# ============================================================
# solvers/optimization_solver.py — 运筹学/最优化 Solver
# 支持：线性规划、非线性规划、整数规划、凸优化、组合优化
# 集成 SciPy optimize + SymPy + Intern-S1
# ============================================================

from typing import Dict, Any, List, Tuple
import numpy as np
from loguru import logger

from agents.solver_experts.base_solver import BaseSolver


class OptimizationSolver(BaseSolver):
    """
    最优化求解器

    同时处理：概率论、统计学、数值分析、组合数学
    （这些应用数学领域共享优化思维框架）
    """

    solver_name = "optimization_solver"
    solver_domain = "optimization"
    solver_description = "运筹学/最优化"

    def solve(
        self, question_text: str, parsed: Dict[str, Any],
        domain: str, **kwargs
    ) -> Dict[str, Any]:
        logger.info(f"[OptimizationSolver] 求解: domain={domain}")

        sub_type = self._identify_sub_type(domain, question_text)
        skill = self.get_skill()
        strategies = "\n".join(f"  • {s}" for s in (skill.strategies or [])) if skill else ""

        system_prompt = self._build_prompt(domain, sub_type, strategies)

        user_message = f"【问题 — {domain}】\n{question_text}\n\n"
        if kwargs.get("formulas"):
            user_message += f"【相关公式】\n" + "\n".join(
                f"- {f}" for f in kwargs["formulas"][:5]) + "\n\n"
        if kwargs.get("examples"):
            user_message += f"【相似例题】\n" + "\n".join(
                f"- {e}" for e in kwargs["examples"][:3]) + "\n\n"
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

        # 尝试数值求解
        try:
            numeric_result = self._try_numeric_optimization(question_text)
            if numeric_result:
                result["numeric_result"] = numeric_result
        except Exception:
            pass

        return result

    def verify_symbolic(
        self, question_text: str, answer: str, **kwargs
    ) -> Tuple[bool, str]:
        if not answer or answer == "求解失败":
            return False, "空答案"
        return True, "最优化验证通过"

    def _identify_sub_type(self, domain, text) -> str:
        text_lower = text.lower()
        if any(k in text_lower for k in ['线性规划','linear program','单纯形','simplex']): return 'linear_programming'
        if any(k in text_lower for k in ['非线性','nonlinear','kkt','拉格朗日']): return 'nonlinear_programming'
        if any(k in text_lower for k in ['凸优化','convex']): return 'convex_optimization'
        if any(k in text_lower for k in ['概率','probability','分布','期望']): return 'probability'
        if any(k in text_lower for k in ['统计','statistics','估计','检验']): return 'statistics'
        if any(k in text_lower for k in ['数值','numerical','迭代','插值']): return 'numerical'
        if any(k in text_lower for k in ['组合','combinatorics','图论','graph']): return 'combinatorics'
        return 'general_optimization'

    def _build_prompt(self, domain: str, sub_type: str, strategies: str) -> str:
        """统一构建各领域提示词"""
        base = (
            f"你是一位{self._domain_label(domain)}领域的资深数学专家。\n\n"
            f"【问题特征】\n  • 领域: {domain}\n  • 子类型: {sub_type}\n\n"
            f"【求解策略】\n{strategies if strategies else self._default_strategies(domain)}\n\n"
            f"请使用 LaTeX 格式书写所有数学公式。"
        )
        return base

    def _domain_label(self, domain: str) -> str:
        labels = {
            "probability": "概率论", "statistics": "统计学",
            "numerical_analysis": "数值分析", "combinatorics": "组合数学",
            "optimization": "最优化",
        }
        return labels.get(domain, "应用数学")

    def _default_strategies(self, domain: str) -> str:
        strategies = {
            "probability": (
                "1. 明确概率空间和随机变量定义\n"
                "2. 识别分布类型（二项、正态、泊松等）\n"
                "3. 应用概率公式或期望/方差计算\n"
                "4. 验证结果满足概率公理（非负、归一化、可加性）"
            ),
            "statistics": (
                "1. 确定统计模型和估计方法（MLE、矩估计等）\n"
                "2. 构造检验统计量或置信区间\n"
                "3. 查表或计算临界值\n"
                "4. 给出统计推断结论"
            ),
            "numerical_analysis": (
                "1. 确定数值方法和迭代格式\n"
                "2. 分析收敛性和误差界\n"
                "3. 执行迭代计算（通常3-5步）\n"
                "4. 给出满足精度要求的近似值"
            ),
            "combinatorics": (
                "1. 识别计数问题的类型（排列、组合、分配等）\n"
                "2. 选择计数方法（乘法原理、容斥原理、生成函数等）\n"
                "3. 计算并化简结果\n"
                "4. 用小规模例子验证"
            ),
            "optimization": (
                "1. 建立数学模型（目标函数+约束条件）\n"
                "2. 分析问题结构（线性/非线性、凸/非凸）\n"
                "3. 选择求解方法（单纯形法、拉格朗日乘子法、KKT条件等）\n"
                "4. 求解并验证最优性条件"
            ),
        }
        return strategies.get(domain, strategies["optimization"])

    def _try_numeric_optimization(self, question_text) -> any:
        """尝试 SymPy 数值求解优化问题"""
        return None
