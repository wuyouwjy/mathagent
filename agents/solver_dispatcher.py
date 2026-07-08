# ============================================================
# agents/solver_dispatcher.py — Solver 调度器
# 职责：根据分类结果，从注册表获取 Solver 实例 + Skill，调用求解
#
# 这是连接 ClassifierAgent 和 Solver 专家的关键桥梁。
# 替代了原来 graph/nodes.py 中硬编码的 _execute_solver 函数。
# ============================================================

import time
from typing import Dict, Any, Optional, List
from loguru import logger


class SolverDispatcher:
    """
    Solver 调度器

    根据分类结果从 Solver 注册表中获取对应的 Solver 实例，
    加载领域 Skill，调用 Solver 的 solve() 方法。

    用法:
        dispatcher = SolverDispatcher()
        result = dispatcher.dispatch(
            solver_name="pde_solver",
            question_text="求解 ∂u/∂t = ∂²u/∂x²",
            parsed={...},
            domain="partial_differential_equations",
        )
    """

    def dispatch(
        self,
        solver_name: str,
        question_text: str,
        parsed: Dict[str, Any],
        domain: str,
        theorems: Optional[List[str]] = None,
        formulas: Optional[List[str]] = None,
        examples: Optional[List[str]] = None,
        reflection_feedback: str = "",
        **kwargs
    ) -> Dict[str, Any]:
        """
        调度 Solver 执行求解

        参数:
            solver_name: Solver 名称（如 "pde_solver"）
            question_text: 问题文本
            parsed: 解析后的结构化问题
            domain: 数学领域
            theorems: RAG 检索到的相关定理
            formulas: RAG 检索到的相关公式
            examples: RAG 检索到的相似例题
            reflection_feedback: 反思反馈信息（重试时使用）

        返回:
            Dict: Solver 输出（含 final_answer, reasoning_steps, methods_used 等）
        """
        start_time = time.time()

        if theorems is None:
            theorems = []
        if formulas is None:
            formulas = []
        if examples is None:
            examples = []

        logger.info(f"[SolverDispatcher] 调度 Solver: {solver_name} (domain={domain})")

        # --- 从注册表创建 Solver 实例 ---
        try:
            from agents.solver_experts.solver_registry import create_solver
            solver = create_solver(solver_name)
        except Exception as e:
            logger.error(f"[SolverDispatcher] 创建 Solver 失败: {e}")
            return self._fallback_result(f"Solver 创建失败: {e}")

        # --- 加载领域 Skill ---
        skill = solver.get_skill()
        if skill:
            logger.debug(f"[SolverDispatcher] 加载 Skill: {skill.skill_name} "
                         f"(strategies={len(skill.strategies)}, examples={len(skill.few_shot_examples)})")

        # --- 构建增强的求解上下文 ---
        knowledge_context = self._build_knowledge_context(
            theorems=theorems, formulas=formulas, examples=examples,
            skill=skill, reflection_feedback=reflection_feedback
        )

        # --- 调用 Solver.solve() ---
        try:
            solver_output = solver.solve(
                question_text=question_text,
                parsed=parsed,
                domain=domain,
                theorems=theorems,
                formulas=formulas,
                examples=examples,
                knowledge_context=knowledge_context,
                skill=skill,
            )
        except Exception as e:
            logger.error(f"[SolverDispatcher] Solver 执行异常: {e}")
            return self._fallback_result(f"Solver 执行异常: {e}")

        elapsed = time.time() - start_time
        logger.info(f"[SolverDispatcher] 求解完成: answer={str(solver_output.get('final_answer', ''))[:50]}..., "
                     f"耗时={elapsed:.2f}s")

        return solver_output

    def _build_knowledge_context(
        self,
        theorems: List[str],
        formulas: List[str],
        examples: List[str],
        skill: Optional[Any],
        reflection_feedback: str,
    ) -> str:
        """构建知识增强上下文"""
        parts = []

        if theorems:
            parts.append("【相关定理】\n" + "\n".join(f"- {t}" for t in theorems[:5]))

        if formulas:
            parts.append("【相关公式】\n" + "\n".join(f"- {f}" for f in formulas[:5]))

        if examples:
            parts.append("【相似例题】\n" + "\n".join(f"- {e}" for e in examples[:3]))

        if skill and skill.strategies:
            parts.append("【推荐策略】\n" + "\n".join(f"- {s}" for s in skill.strategies[:5]))

        if reflection_feedback:
            parts.append(f"\n{reflection_feedback}")

        return "\n\n".join(parts) if parts else ""

    def _fallback_result(self, error_msg: str) -> Dict[str, Any]:
        """构建回退结果"""
        return {
            "final_answer": f"求解失败: {error_msg}",
            "reasoning_steps": [],
            "methods_used": [],
            "educational_hint": "求解过程中发生错误，请检查问题描述和系统配置。",
            "error": error_msg,
        }


# ============================================================
# 全局单例
# ============================================================

_global_dispatcher: Optional[SolverDispatcher] = None


def get_dispatcher() -> SolverDispatcher:
    """获取全局 SolverDispatcher 单例"""
    global _global_dispatcher
    if _global_dispatcher is None:
        _global_dispatcher = SolverDispatcher()
    return _global_dispatcher
