# ============================================================
# graph/nodes/solver_node.py — Solver 调度执行节点
# 🔥 核心改动：使用 SolverDispatcher 调用 Solver 专家 + Skill
# 替代原来硬编码的 _execute_solver 函数
# ============================================================

import time
from typing import Dict, Any
from loguru import logger


def solver_dispatcher_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Solver 调度执行节点

    使用 SolverDispatcher 根据分类结果调度对应的 Solver 专家 + Skill。
    """
    solver_name = state.get("solver_name", "algebra_solver")
    logger.info(f"[Solver] 调度 Solver: {solver_name} → 问题 {state['question_id']}")
    start_time = time.time()

    question_text = state["question_text"]
    parsed = state.get("parsed_problem", {})
    domain = state.get("classified_domain", "")
    theorems = state.get("retrieved_theorems", [])
    formulas = state.get("retrieved_formulas", [])
    examples = state.get("retrieved_examples", [])
    reflection_feedback = state.get("reflection_feedback", "")

    try:
        # 🔥 使用 SolverDispatcher 替代硬编码 prompt
        from agents.solver_dispatcher import get_dispatcher

        dispatcher = get_dispatcher()
        solver_output = dispatcher.dispatch(
            solver_name=solver_name,
            question_text=question_text,
            parsed=parsed,
            domain=domain,
            theorems=theorems,
            formulas=formulas,
            examples=examples,
            reflection_feedback=reflection_feedback,
        )
        solver_status = "success"
    except Exception as e:
        logger.error(f"[Solver] Solver 执行异常: {e}")
        solver_output = {
            "error": str(e),
            "final_answer": "求解失败",
            "reasoning_steps": [],
            "methods_used": [],
        }
        solver_status = "failed"

    elapsed = time.time() - start_time
    node_trace = state.get("node_trace", []) + [f"solver:{solver_name} ({elapsed:.2f}s)"]

    logger.info(f"[Solver] 求解完成: status={solver_status}, "
                f"answer={str(solver_output.get('final_answer', ''))[:50]}..., "
                f"耗时={elapsed:.2f}s")

    return {
        "solver_output": solver_output,
        "solver_status": solver_status,
        "node_trace": node_trace,
    }
