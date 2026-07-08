# ============================================================
# graph/nodes/verifier_node.py — 结果验证节点
# ============================================================

import time
from typing import Dict, Any, List
from loguru import logger


def verifier_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    验证节点 — 验证 Solver 输出结果

    使用 LLM 逻辑验证（推理链检查）。
    """
    logger.info(f"[Verifier] 开始验证: {state['question_id']}")
    start_time = time.time()

    solver_output = state.get("solver_output", {})
    question_text = state.get("question_text", "")
    domain = state.get("classified_domain", "")

    final_answer = solver_output.get("final_answer", "")
    reasoning_steps = solver_output.get("reasoning_steps", [])
    methods_used = solver_output.get("methods_used", [])

    # 如果 Solver 执行失败，直接标记验证不通过
    if state.get("solver_status") == "failed":
        logger.warning("[Verifier] Solver 执行失败，跳过验证")
        return {
            "verification_result": {
                "is_correct": False, "confidence": 0.0,
                "check_method": "solver_failed",
                "error_details": solver_output.get("error", "Solver 执行失败"),
            },
            "verification_passed": False,
        }

    # 快速模式：不调用 LLM 验证，信任 solver 输出（评测模式用）
    if state.get("max_reflection_count", 3) == 0:
        has_answer = bool(final_answer and final_answer != "无答案" and "求解失败" not in str(final_answer))
        return {
            "verification_result": {
                "is_correct": has_answer, "confidence": 0.85 if has_answer else 0.0,
                "check_method": "fast_mode_trust",
                "error_details": "" if has_answer else "无有效答案",
            },
            "verification_passed": has_answer,
        }

    try:
        verification = _llm_verify(
            question_text=question_text,
            final_answer=final_answer,
            reasoning_steps=reasoning_steps,
            methods_used=methods_used,
            domain=domain,
        )
    except Exception as e:
        logger.error(f"[Verifier] LLM 验证异常: {e}")
        verification = {
            "is_correct": False, "confidence": 0.3,
            "check_method": "verification_error", "error_details": str(e),
        }

    elapsed = time.time() - start_time
    node_trace = state.get("node_trace", []) + [
        f"verifier (correct={verification.get('is_correct')}, conf={verification.get('confidence', 0):.2f}, {elapsed:.2f}s)"
    ]

    verification_passed = verification.get("is_correct", False)

    logger.info(f"[Verifier] 验证完成: passed={verification_passed}, confidence={verification.get('confidence', 0):.2f}")

    return {
        "verification_result": verification,
        "verification_passed": verification_passed,
        "node_trace": node_trace,
    }


def _llm_verify(
    question_text: str, final_answer: str,
    reasoning_steps: List[Dict], methods_used: List[str], domain: str,
) -> Dict[str, Any]:
    """使用 LLM 验证求解结果"""
    from tools.intern_client import get_intern_client

    client = get_intern_client()

    system_prompt = (
        "你是一位数学验证专家。请严格验证以下数学问题的求解结果。\n\n"
        "检查要点：\n"
        "1. 推理逻辑是否严谨、无跳步？\n"
        "2. 每一步的数学推导是否正确？\n"
        "3. 最终答案是否满足原问题的所有条件？\n"
        "4. 使用的方法是否适用于该问题？\n\n"
        "请以 JSON 格式返回验证结果：\n"
        '{"is_correct": true/false, "confidence": 0.0到1.0, '
        '"check_method": "描述", "error_details": "错误详情", '
        '"correction_suggestion": "修改建议"}'
    )

    steps_summary = "\n".join([
        f"  Step {s.get('step_id', i+1)}: {s.get('description', '')[:100]}"
        for i, s in enumerate(reasoning_steps[:10])
    ])
    if len(reasoning_steps) > 10:
        steps_summary += f"\n  ... (共{len(reasoning_steps)}步)"

    user_message = (
        f"【原始问题】\n{question_text}\n\n"
        f"【数学领域】{domain}\n"
        f"【使用的方法】{', '.join(methods_used) if methods_used else '未指定'}\n\n"
        f"【推理步骤】\n{steps_summary}\n\n"
        f"【最终答案】\n{final_answer}\n\n"
        f"请验证以上求解过程。"
    )

    response = client.chat_with_json_output(
        messages=[{"role": "user", "content": user_message}],
        system_prompt=system_prompt,
        temperature=0.0,
    )

    parsed_json = response.get("parsed_json")
    if parsed_json:
        return {
            "is_correct": parsed_json.get("is_correct", False),
            "confidence": float(parsed_json.get("confidence", 0.5)),
            "check_method": parsed_json.get("check_method", "LLM验证"),
            "error_details": parsed_json.get("error_details", ""),
            "correction_suggestion": parsed_json.get("correction_suggestion", ""),
        }
    else:
        return {
            "is_correct": False, "confidence": 0.3,
            "check_method": "parse_error", "error_details": "LLM 返回无法解析",
        }
