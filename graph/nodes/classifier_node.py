# ============================================================
# graph/nodes/classifier_node.py — 数学领域分类节点
# 委托给 ClassifierAgent 执行分类
# ============================================================

import time
from typing import Dict, Any
from loguru import logger

from schemas.math_domains import MathDomain, DOMAIN_CN_NAME, get_solver_for_domain


def classifier_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    数学领域分类节点 — 委托给 ClassifierAgent

    使用 ClassifierAgent 对问题进行领域分类，输出18类之一。
    """
    logger.info(f"[Classifier] 开始领域分类: {state['question_id']}")
    start_time = time.time()

    question_text = state["question_text"]
    parsed = state.get("parsed_problem", {})

    # --- 使用 ClassifierAgent 进行分类 ---
    from agents.classifier_agent import get_classifier

    agent = get_classifier()
    result = agent.classify(question_text, parsed)

    domain = result.domain
    confidence = result.confidence
    reason = result.reason
    solver_name = result.solver_name

    # --- 验证 domain 有效性 ---
    valid_domains = [d.value for d in MathDomain]
    if domain not in valid_domains:
        logger.warning(f"[Classifier] 无效领域 '{domain}', 回退到 algebra")
        domain = "algebra"
        confidence = 0.3
        reason = "无效领域自动纠正"
        solver_name = get_solver_for_domain(domain)

    node_trace = state.get("node_trace", []) + [f"classifier -> {domain} ({time.time() - start_time:.2f}s)"]

    domain_obj = MathDomain(domain) if domain in valid_domains else MathDomain.ALGEBRA
    logger.info(f"[Classifier] 分类完成: domain={domain} ({DOMAIN_CN_NAME.get(domain_obj, '未知')}), "
                f"confidence={confidence:.2f}, solver={solver_name}")

    return {
        "classified_domain": domain,
        "classification_confidence": confidence,
        "classification_reason": reason,
        "solver_name": solver_name,
        "node_trace": node_trace,
    }
