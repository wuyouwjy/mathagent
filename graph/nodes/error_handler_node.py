# ============================================================
# graph/nodes/error_handler_node.py — 错误处理节点
# ============================================================

from typing import Dict, Any
from loguru import logger


def error_handler_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    错误处理节点 — 全局异常兜底

    确保：
    1. 错误信息被记录
    2. 输出仍为有效的 JSON 结构
    3. 工作流可以正常终止
    """
    logger.error(f"[ErrorHandler] 处理异常: {state['question_id']}")
    errors = state.get("error_info", [])

    fallback_output = {
        "question_id": state["question_id"],
        "domain": state.get("classified_domain", "unknown"),
        "final_answer": "求解失败",
        "reasoning_steps": [],
        "methods_used": [],
        "verification": {
            "is_correct": False, "confidence": 0.0,
            "check_method": "error_handler",
            "error_details": "; ".join(errors) if errors else "未知错误",
        },
        "educational_hint": "求解过程中发生错误，请检查问题描述和系统配置。",
        "computation_time_ms": state.get("computation_time_ms", 0.0),
        "retry_count": state.get("reflection_count", 0),
    }

    return {
        "final_output": fallback_output,
        "verification_passed": False,
        "node_trace": state.get("node_trace", []) + ["error_handler"],
    }
