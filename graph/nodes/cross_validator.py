"""Cross-Validator: compare Reasoning vs Python results, route accordingly. §3.5.5.

M4 hardening: for computation problems, prefer the sympy-computed Python answer
when it succeeded (deterministic > LLM prose, which may echo placeholders or
compute wrong values). For proof problems or python-failed cases, use reasoning.
"""
from utils.answer.matcher import AnswerMatcher
from utils.answer.contract import answer_part_count, missing_components
from utils.answer.extractor import is_multi_part_problem, looks_incomplete_answer
from utils.answer.cot_stripper import is_placeholder_answer
from utils.verify.reconciliation_policy import reconciliation_retry_available
from utils.verify.evidence import parse_verification_evidence
from config import CONFIG
from utils.problem.profile import (
    classify_question_mode,
    fill_answer_matches_blanks,
    is_objective_mode,
    normalize_objective_answer,
    objective_answer_is_usable,
)


def _clean_answer(answer: str) -> str:
    return "" if is_placeholder_answer(answer) else (answer or "")


def _same_scalar_or_text(a: str, b: str) -> bool:
    """两个候选是否本质相同（去空白/标点后一致）。"""
    import re as _re
    ka = _re.sub(r"[\s。．.,，;；]+", "", str(a or ""))
    kb = _re.sub(r"[\s。．.,，;；]+", "", str(b or ""))
    return bool(ka) and ka == kb


def _preferred_answer(state: dict, match_result: dict) -> str:
    """Pick the answer to surface as validated_answer.

    证据优先序（2026-08-09 评委建议 1，最高优先级）：
    ``有枚举支撑且反驳对手的 Python 答案 > evidence=support 的分支 > 推理答案 >
    结构化部分结论``。idx 20 事故——Python 枚举出 C(2k,k)² 且 evidence=contradict
    明确反驳了推理的 "4"，仲裁超时后系统仍输出被自家验证器反驳的 "4"——由第一
    条规则在架构上杜绝：证据指向谁，兜底就选谁。

    Computation + python_success + 答案完整 → Python answer (sympy, deterministic).
    Python 答案为空/碎片（评委报告问题 2：'(Matrix([' 等截断片段曾污染
    final_response）→ 回退 reasoning answer；两者都不完整时取非空者兜底。

    uncertain 时保持推理优先（去锚定），但 2026-07-07 评委报告显示：推理侧漏
    结论/漏问项/漏分配而 Python 侧完整时（265/271/283/93/113/275），残缺答案
    仍然胜出。故当推理答案缺契约字段或漏问项、且 Python 答案更完整时改选 Python。
    """
    rr = state.get("reasoning_result") or {}
    po = state.get("python_output") or {}
    problem = state.get("problem", "")
    ptype = match_result.get("problem_type", "computation")
    python_answer = _clean_answer(po.get("answer", ""))
    reasoning_answer = _clean_answer(rr.get("answer", ""))
    python_ok = bool(po.get("success")) and bool(python_answer)
    reasoning_ok = bool(reasoning_answer) and not looks_incomplete_answer(reasoning_answer)
    question_mode = state.get("question_mode") or ""
    if is_objective_mode(question_mode):
        # Keep every degradation path canonical.  In particular, an invalid or
        # unavailable objective candidate may still reach the semantic arbiter's
        # deterministic fallback; returning the raw rationale there would undo the
        # short-path formatting guarantee in coordinator_node.
        for candidate in (reasoning_answer, python_answer):
            normalized = normalize_objective_answer(candidate, question_mode)
            if objective_answer_is_usable(normalized, question_mode):
                return normalized
        return ""
    # 证据优先的最后防线：Python 证据明确反驳推理候选、且 Python 自己持有一个
    # 不同的、可用的、非伪造的答案时，兜底必须选 Python——被自家验证器反驳的
    # 答案不得再被输出。仅在此条件下打破"推理优先"，避免污染无争议路径。
    evidence_status = po.get("evidence_status", "")
    fabricated = bool((po.get("authenticity") or {}).get("fabricated"))
    if evidence_status == "contradict" and python_answer and not fabricated \
            and not looks_incomplete_answer(python_answer) \
            and not _same_scalar_or_text(python_answer, reasoning_answer):
        return python_answer
    if match_result.get("status") == "match" and reasoning_ok:
        # Python/SymPy supplies correctness evidence; retain the already validated
        # human-readable reasoning form for the public answer.
        return reasoning_answer
    if match_result.get("status") == "uncertain" and reasoning_ok:
        if python_ok and not looks_incomplete_answer(python_answer):
            r_missing = missing_components(problem, reasoning_answer)
            p_missing = missing_components(problem, python_answer)
            if len(p_missing) < len(r_missing):
                return python_answer
            if is_multi_part_problem(problem) \
                    and answer_part_count(python_answer) > answer_part_count(reasoning_answer):
                return python_answer
        return reasoning_answer
    if ptype == "computation" and python_ok and not looks_incomplete_answer(python_answer):
        # 反伪造：无实质计算的代码答案不得凭"执行成功"压过一个可用的推理答案。
        if not (fabricated and reasoning_ok):
            return python_answer
    if reasoning_ok:
        return reasoning_answer
    return reasoning_answer or python_answer


def cross_validator_node(state, config):
    reasoning_result = state.get("reasoning_result") or {}
    raw_python_output = state.get("python_output") or {}
    python_output = parse_verification_evidence(
        raw_python_output,
        candidate_answer=reasoning_result.get("answer", ""),
        code=state.get("python_code", ""),
    )
    question_mode = state.get("question_mode") or classify_question_mode(state.get("problem", ""))
    if is_objective_mode(question_mode):
        # Objective questions deliberately have no Python candidate.  A valid,
        # normalized answer from the concise reasoning path is the only candidate
        # worth emitting; sending it through the computation matcher would mark it
        # uncertain solely because Python was skipped and trigger an unnecessary
        # arbitration/reconciliation round.
        candidate = normalize_objective_answer(reasoning_result.get("answer", ""), question_mode)
        if not objective_answer_is_usable(candidate, question_mode):
            candidate = normalize_objective_answer(python_output.get("answer", ""), question_mode)
        if objective_answer_is_usable(candidate, question_mode):
            blank_gap = question_mode == "fill" and not fill_answer_matches_blanks(
                candidate, state.get("problem", ""))
            # 填空分项数不足题面空位数时降低置信（评委报告 idx 86：残缺答案
            # 曾以 0.78 置信直接放行，无任何完整性检查）。
            confidence = 0.45 if blank_gap else 0.78
            reason = (f"客观题快速路径已提取{question_mode}答案"
                      + ("；但分项数少于题面空位数，答案可能不完整" if blank_gap else ""))
            # VeritasMath 移植（启元实证 P0）：判断题双向确认。Intern-S2 对
            # "是否"题存在系统性"否"偏向（启元实测 90% 判断错题同根因），单轮
            # 方向不可靠。确认轮一致才采纳；反向则温度0重解取第三票。
            # 仅 true_false 题型、答案为判断词、预算充足时触发，其余零成本。
            if question_mode == "true_false" and CONFIG.get("enable_judge_confirm", True):
                from utils.verify.judge_confirm import run_judge_confirmation, should_confirm
                if should_confirm(state.get("problem", ""), candidate):
                    from utils.deps import get_deps
                    deps = get_deps(config)

                    def _resolve_prompt():
                        return (f"【题目】{state.get('problem', '')}\n"
                                "请独立判断该命题是否成立：逐步推导后，最后一行"
                                "单独输出 答案:是 或 答案:否（只输出这一行判断）。")

                    jc = run_judge_confirmation(
                        state.get("problem", ""), candidate, deps,
                        main_prompt_builder=_resolve_prompt)
                    if jc.get("action") == "confirm":
                        confidence = min(confidence + 0.12, 0.95)
                        reason += f"；双向确认一致（{jc.get('note', '')}）"
                    elif jc.get("action") == "reverse":
                        candidate = jc.get("final_word") or candidate
                        confidence = max(confidence, 0.6)
                        reason += f"；双向确认反向，改判 {candidate}"
            match_result = {
                "status": "match",
                "verdict": True,
                "comparison_verdict": True,
                "confidence": confidence,
                "reason": reason,
                "method": "objective_direct",
                "problem_type": question_mode,
                "text_similarity": 1.0,
                "matched_fields": [],
                "mismatched_fields": [],
                "field_coverage": 0.5 if blank_gap else 1.0,
            }
        else:
            match_result = {
                "status": "uncertain",
                "verdict": None,
                "comparison_verdict": None,
                "confidence": 0.0,
                "reason": "客观题未提取到可提交的答案",
                "method": "objective_unparsed",
                "problem_type": question_mode,
                "text_similarity": 0.0,
                "matched_fields": [],
                "mismatched_fields": [],
                "field_coverage": 0.0,
            }
    else:
        match_result = dict(AnswerMatcher.match_answers(
            problem=state["problem"],
            reasoning_result=reasoning_result,
            python_result=python_output,
        ))
    evidence_status = python_output.get("evidence_status", "inconclusive")
    evidence_summary = python_output.get("evidence_summary", "")
    contradictions = list(python_output.get("contradictions") or [])
    match_result.update({
        "python_evidence_status": evidence_status,
        "python_evidence_summary": evidence_summary,
        "python_contradictions": contradictions,
    })
    status = match_result["status"]
    validated_answer = ""
    next_node = "coordinator"
    problem_type = match_result.get("problem_type", "computation")

    history_entry = {
        "round": state.get("reconciliation_round", 0),
        "status": status,
        "evidence_status": evidence_status,
        "evidence_summary": evidence_summary[:1000],
        "contradictions": contradictions[:10],
    }

    # Explicit evidence of a counterexample outranks textual/symbolic agreement.
    # A program can run successfully while proving that the candidate is false.
    if evidence_status == "contradict":
        match_result["routing_reason"] = "python_evidence_contradiction"
        # Playoff 确定性复算裁决：计算题 + 双候选 + 未 play 过时，先代回复算
        # 戳破 Python 的"假证据"（Python 自身算错却自报反驳了正确推理）。
        already_played = bool(state.get("playoff_trace"))
        if problem_type == "computation" and CONFIG.get("enable_playoff", True) \
                and not already_played:
            from graph.nodes.playoff import playoff_candidates
            cand_a, cand_b = playoff_candidates(state)
            if cand_a and cand_b:
                match_result["routing_reason"] = \
                    "python_evidence_contradiction_deterministic_playoff"
                history_entry["status"] = "contradict_playoff"
                return {
                    "validation_status": "contradict_playoff",
                    "validation_details": match_result,
                    "validated_answer": validated_answer,
                    "next_node": "playoff",
                    "python_output": python_output,
                    "python_evidence_status": evidence_status,
                    "python_evidence_summary": evidence_summary,
                    "python_contradictions": contradictions,
                    "validation_history": [history_entry],
                }
        if reconciliation_retry_available(state, config):
            status = "mismatch_reconciling"
            next_node = "reconciliation"
        else:
            status = "mismatch_arbitrating"
            next_node = "semantic_arbiter"
            match_result["unresolved_contradiction"] = True
        history_entry["status"] = status
        return {
            "validation_status": status,
            "validation_details": match_result,
            "validated_answer": validated_answer,
            "next_node": next_node,
            "python_output": python_output,
            "python_evidence_status": evidence_status,
            "python_evidence_summary": evidence_summary,
            "python_contradictions": contradictions,
            "validation_history": [history_entry],
        }

    if status == "match":
        if problem_type == "computation" and python_output.get("success") \
                and match_result.get("method") in {"symbolic", "structured_symbolic"}:
            match_result["bypass_reason"] = "python_success_and_symbolic_equivalence"
        match_result["routing_reason"] = "validated_match"
        if match_result.get("method") == "objective_direct":
            validated_answer = normalize_objective_answer(
                reasoning_result.get("answer", ""), question_mode
            )
            if not validated_answer:
                validated_answer = normalize_objective_answer(
                    python_output.get("answer", ""), question_mode
                )
        else:
            validated_answer = _preferred_answer(state, match_result)
        next_node = "coordinator"
    elif status == "mismatch":
        # Playoff 确定性复算裁决：计算题冲突先代回复算，季后赛已跑过/不适用时
        # 回落到既有的重算-仲裁通道。
        already_played = bool(state.get("playoff_trace"))
        if problem_type == "computation" and CONFIG.get("enable_playoff", True) \
                and not already_played:
            from graph.nodes.playoff import playoff_candidates
            cand_a, cand_b = playoff_candidates(state)
            if cand_a and cand_b:
                status = "mismatch_playoff"
                match_result["routing_reason"] = "computation_mismatch_deterministic_playoff"
                history_entry["status"] = status
                return {
                    "validation_status": status,
                    "validation_details": match_result,
                    "validated_answer": validated_answer,
                    "next_node": "playoff",
                    "python_output": python_output,
                    "python_evidence_status": evidence_status,
                    "python_evidence_summary": evidence_summary,
                    "python_contradictions": contradictions,
                    "validation_history": [history_entry],
                }
        # subgraph-level retry gated by reconciliation_round (NOT per-node attempts —
        # per-node attempts gate the agent's internal format/code retries; the plan
        # §4.2 keeps these separate).
        if reconciliation_retry_available(state, config):
            status = "mismatch_reconciling"
            next_node = "reconciliation"
        else:
            status = "mismatch_arbitrating"
            match_result["routing_reason"] = "mismatch_retry_exhausted_semantic_arbitration"
            next_node = "semantic_arbiter"
    else:  # uncertain
        # Parser/format uncertainty is exactly where keyword contracts are weakest.
        # Let a semantic judge choose between the two existing answers before paying
        # for another full reasoning+Python run. The arbiter may abstain and route
        # back to reconciliation without changing either candidate.
        status = "uncertain_arbitrating"
        match_result["routing_reason"] = "insufficient_equivalence_evidence_semantic_arbitration"
        next_node = "semantic_arbiter"

    history_entry["status"] = status
    return {
        "validation_status": status,
        "validation_details": match_result,
        "validated_answer": validated_answer,
        "next_node": next_node,
        "python_output": python_output,
        "python_evidence_status": evidence_status,
        "python_evidence_summary": evidence_summary,
        "python_contradictions": contradictions,
        "validation_history": [history_entry],
    }
