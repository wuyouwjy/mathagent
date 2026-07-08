# ============================================================
# graph/nodes/formatter_node.py — JSON 格式化输出节点
# ============================================================

from typing import Dict, Any
from loguru import logger


def _normalize_list(val):
    """归一化为列表：LLM 可能返回逗号分隔的字符串"""
    if isinstance(val, str):
        return [m.strip() for m in val.replace("，", ",").split(",") if m.strip()]
    if isinstance(val, list):
        return val
    return []


def _normalize_steps(val):
    """归一化推理步骤"""
    if isinstance(val, str):
        return [{"step_id": 1, "description": val[:500]}]
    if isinstance(val, list):
        return val
    return []


def formatter_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """格式化节点 — 生成标准 JSON 输出"""
    logger.info(f"[Formatter] 开始格式化输出: {state['question_id']}")

    # 缓存命中直接透传
    existing_output = state.get("final_output", {})
    if existing_output and existing_output.get("from_cache"):
        logger.info("[Formatter] 使用缓存结果，跳过格式化")
        return {
            "final_output": existing_output,
            "node_trace": state.get("node_trace", []) + ["formatter(cached)"],
        }

    from schemas.output_schema import MathSolutionOutput, ReasoningStep, VerificationResult

    solver_output = state.get("solver_output", {})
    verification_result = state.get("verification_result", {})

    # 归一化（LLM 可能返回非标准格式）
    raw_steps = _normalize_steps(solver_output.get("reasoning_steps", []))
    methods_used = _normalize_list(solver_output.get("methods_used", []))

    # 构建推理步骤
    reasoning_steps = []
    for step in raw_steps:
        try:
            reasoning_steps.append(ReasoningStep(
                step_id=step.get("step_id", len(reasoning_steps) + 1),
                description=step.get("description", ""),
                formula=step.get("formula"),
                result=step.get("result"),
                method=step.get("method"),
            ))
        except Exception:
            reasoning_steps.append(ReasoningStep(
                step_id=len(reasoning_steps) + 1,
                description=str(step),
            ))

    # 构建验证结果
    verification = VerificationResult(
        is_correct=verification_result.get("is_correct", False),
        confidence=verification_result.get("confidence", 0.0),
        check_method=verification_result.get("check_method", ""),
        error_details=verification_result.get("error_details"),
    )

    # 构建完整输出
    output = MathSolutionOutput(
        question_id=state["question_id"],
        domain=state.get("classified_domain", "unknown"),
        final_answer=solver_output.get("final_answer", "无答案"),
        reasoning_steps=reasoning_steps,
        methods_used=methods_used,
        verification=verification,
        educational_hint=solver_output.get("educational_hint", ""),
        computation_time_ms=state.get("computation_time_ms", 0.0),
        retry_count=state.get("reflection_count", 0),
    )

    output_dict = output.model_dump()

    logger.info(f"[Formatter] 格式化完成: steps={len(reasoning_steps)}, "
                f"methods={len(output.methods_used)}, final_answer_len={len(output.final_answer)}")

    return {
        "final_output": output_dict,
        "node_trace": state.get("node_trace", []) + ["formatter"],
    }
