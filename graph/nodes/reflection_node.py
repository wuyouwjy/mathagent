# ============================================================
# graph/nodes/reflection_node.py — 反思节点
# 委托给 GraphManagerAgent 进行反思决策
# ============================================================

from typing import Dict, Any
from loguru import logger


def reflection_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    反思节点 — 委托给 GraphManagerAgent 分析验证失败原因

    逻辑：
    1. 如果验证通过 → 不需要反思
    2. 如果验证未通过 + 重试次数未达上限 → 生成反馈，触发反思重试
    3. 如果验证未通过 + 已达重试上限 → 接受当前结果
    """
    logger.info(f"[Reflection] 反思分析: {state['question_id']}")

    # 使用 GraphManagerAgent 进行评估
    from agents.graph_manager_agent import get_graph_manager

    agent = get_graph_manager()
    decision = agent.evaluate_reflection(state)

    logger.info(f"[Reflection] 决策: should_retry={decision.should_retry}, "
                f"count={decision.new_count}, "
                f"suggested_solver={decision.suggested_solver}")

    result = {
        "reflection_needed": decision.should_retry,
        "reflection_feedback": decision.feedback,
        "reflection_count": decision.new_count,
    }

    # 如果有备选 Solver 建议，更新 solver_name
    if decision.suggested_solver:
        logger.info(f"[Reflection] 建议切换 Solver: {state.get('solver_name')} → {decision.suggested_solver}")
        result["solver_name"] = decision.suggested_solver

    return result
