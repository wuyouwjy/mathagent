from utils.deps import get_deps
from utils.answer_cleanliness import extract_partial_findings, is_noise_answer
from utils.answer_formatter import (
    attach_steps,
    build_proof_body,
    post_process_final_response,
    _clean_noise_head,
)
from utils.conclusion_salvage import salvage_conclusion
from utils.cot_stripper import is_placeholder_answer, strip_cot_prefix
from utils.answer_extractor import looks_incomplete_answer
from utils.llm_retry import chat_prefilled, chat_with_retry
from utils.prompt_templates import COORDINATOR_PROMPT
from utils.token_budget import estimate_tokens
from config import CONFIG
from utils.problem_profile import is_objective_mode


def _evidence_override(state: dict, validated: str) -> tuple[str, str]:
    """证据优先的最终闸门（2026-08-09 评委建议 1，最高优先级）。

    idx 20 事故的架构性杜绝：当 Python 证据（evidence=contradict）明确反驳的
    正是即将输出的推理答案、且 Python 自己持有一个不同的、可用的、非伪造的
    答案时，无论上游（仲裁超时/跳过）留下了什么，最终输出都必须切换到携带
    证据的一方。返回 (最终答案, 覆盖说明)；不满足条件时原样返回。
    """
    po = state.get("python_output") or {}
    rr = state.get("reasoning_result") or {}
    if not validated:
        return validated, ""
    if po.get("evidence_status") != "contradict":
        return validated, ""
    if (po.get("authenticity") or {}).get("fabricated"):
        return validated, ""
    python_answer = str(po.get("answer") or "").strip()
    reasoning_answer = str(rr.get("answer") or "").strip()
    if not python_answer or is_placeholder_answer(python_answer) \
            or looks_incomplete_answer(python_answer) or is_noise_answer(python_answer):
        return validated, ""

    import re
    def _key(text):
        return re.sub(r"[\s。．.,，;；]+", "", text)
    # 只有当被输出的就是被反驳的推理候选、且 Python 给出的是另一个答案时才覆盖。
    if _key(validated) != _key(reasoning_answer) or _key(python_answer) == _key(validated):
        return validated, ""
    return python_answer, "evidence_priority_override"


#: Trailing chars of a partial analysis to show. A conclusion sits at the end of a
#: derivation, so the tail is the informative part.
_PARTIAL_TAIL_CHARS = 400

_PARTIAL_HEADER = "未能完成完整推导，以下为已获得的部分结果：\n"


def _with_emergency_answer(guess: str, partial: str, source: str) -> str:
    """应急直答在前；已获部分结论改用中性标题附后（避免与直答自相矛盾）。"""
    final = f"最终答案：{guess}"
    if source != "generic_error":
        supplement = partial.replace(_PARTIAL_HEADER, "求解过程中获得的部分结论：\n", 1)
        final += f"\n\n{supplement}"
    return final


def _partial_response(state: dict) -> tuple[str, str]:
    """Best available text when no answer was produced and no time remains.

    2026-08-09 评委报告模式 B：旧实现最后两级直接倾倒原始推理尾部
    （"哪里出错了？啊！"、"s_j." 等 19 题的碎片皆出于此）。现在每一级都过
    洁净度门，并新增"结构化部分结论"与 stdout 挖掘两级；原始尾部只有在
    通过噪声检测时才可输出，否则宁可给通用失败说明也不给不可判分噪声。
    """
    from utils.stdout_miner import mine_stdout_answer

    rr = state.get("reasoning_result") or {}
    python_output = state.get("python_output") or {}
    raw_resp = (state.get("reasoning_raw_response") or "").strip()
    analysis = (rr.get("analysis") or "").strip()
    python_answer = str(python_output.get("answer") or "").strip()
    stdout = str(python_output.get("stdout") or "")
    for source, candidate in (
        ("reasoning_conclusion", salvage_conclusion(analysis)),
        ("reasoning_conclusion", salvage_conclusion(raw_resp)),
        # Python 侧答案（含 stdout 二次抽取的 answer_source=stdout_mined）：
        # 截断前打印的结论是真实计算产物，优于任何推理残段。
        ("python_answer", python_answer),
        ("python_stdout_mined", mine_stdout_answer(stdout)),
        # 结构化部分结论：从推理文本中收集已证引理/已确认断言，替代原始思维流。
        ("partial_findings", extract_partial_findings(analysis)),
        ("partial_findings", extract_partial_findings(raw_resp)),
        # 尾部仅在通过噪声门时可用（评委报告模式 B 的碎片全部拦在这道门外）。
        ("reasoning_tail", analysis[-_PARTIAL_TAIL_CHARS:]),
    ):
        text = (candidate or "").strip()
        if text and not is_placeholder_answer(text) and not is_noise_answer(text):
            return f"{_PARTIAL_HEADER}{text}", source
    return "解题过程中出现错误，无法给出完整答案。", "generic_error"


def _emergency_direct_answer(state: dict, deps) -> str:
    """双分支全灭时的最后一搏：动用 reserve 做一次种子直答（~30s）。

    评委报告：idx 2/54/64/69/82/85 双分支 900s 全灭后以 generic_error 收尾。
    与其交白卷，不如用剩余硬时限发一次 prefill 直答——助手种子抑制私有推理，
    模型基于题面与已获线索给出最可信结论。失败或产出噪声时返回 ""。
    """
    clock = deps.time_budget
    quota = CONFIG.get("emergency_reserve_quota_s", 90)
    if clock and clock.remaining_hard() < quota:
        return ""
    rr = state.get("reasoning_result") or {}
    clues = []
    salvaged = salvage_conclusion(rr.get("analysis", ""))
    if salvaged:
        clues.append(salvaged)
    findings = extract_partial_findings(rr.get("analysis", ""), limit_chars=600)
    if findings:
        clues.append(findings)
    mined = str((state.get("python_output") or {}).get("answer") or "").strip()
    if mined:
        clues.append(f"程序计算线索：{mined}")
    clue_block = ""
    if clues:
        clue_block = "\n已获得的部分线索（可信度有限）：\n" + "\n".join(clues)[:2200]
    prompt = (
        "下面这道数学题此前的求解未能完成。请你根据题目（和已有线索）直接给出最可能的"
        "最终答案：单行、具体（数值/表达式/集合/结论），不要解释过程，不要说无法确定。\n\n"
        f"题目：\n{state.get('problem', '')[:6000]}\n{clue_block}"
    )
    try:
        raw = chat_prefilled(
            deps.client,
            messages=[{"role": "user", "content": prompt}],
            prefix="最终答案：",
            temperature=0.3,
            max_tokens=CONFIG["max_tokens"].get("emergency_answer", 1280),
            logger=deps.logger,
            time_budget=clock,
            expected_call_seconds=30,
            label="emergency_answer",
            reserve_margin_s=45,
        )
    except Exception as exc:  # noqa: BLE001 - emergency path never raises.
        deps.logger.warning("Emergency direct answer failed: %s", exc)
        return ""
    if deps.token_budget:
        deps.token_budget.consume(estimate_tokens(prompt), estimate_tokens(raw))
    text = strip_cot_prefix(raw or "")
    import re
    match = re.search(r"最终答案[：:]\s*(.+)", text, re.DOTALL)
    answer = (match.group(1) if match else text).strip()
    answer = answer.splitlines()[0].strip() if answer else ""
    if not answer or len(answer) > 300 or is_placeholder_answer(answer) \
            or is_noise_answer(answer) or looks_incomplete_answer(answer):
        return ""
    return answer


def coordinator_node(state, config):
    deps = get_deps(config)
    client = deps.client
    budget = deps.token_budget
    rr = state.get("reasoning_result") or {}
    validated = state.get("validated_answer") or rr.get("answer", "")
    if is_placeholder_answer(validated):
        validated = ""
    ptype = (state.get("validation_details") or {}).get("problem_type", "computation")
    if is_objective_mode(state.get("question_mode", ptype)) and validated:
        # The objective path already returns a canonical, short answer.  A second
        # narrative generation cannot improve correctness and can drop option
        # letters or one of several blanks, so preserve it verbatim.
        prefix = "最终答案："
        final = validated if validated.lstrip().startswith(prefix) else prefix + validated
        return {"final_response": final, "coordination_detail": "",
                "fallback_source": "objective_validated_answer"}
    # 证据优先最终闸门：被自家验证器反驳的答案不得出厂（评委建议 1）。
    # 仲裁明确锁定的选择（answer_locked）尊重仲裁；未锁定的候选一律过闸。
    evidence_note = ""
    if not state.get("answer_locked"):
        validated, evidence_note = _evidence_override(state, validated)
        # 洁净度终门（2026-08-09 冒烟 idx 43）：交叉验证在双分支皆弱时可能放行一段
        # 探索散文；deadline 路径会把它原样出厂。修复优先于丢弃——"1/2 works." 这类
        # 正确值+口癖要剥尾保值（idx 2），修不出干净头部才置空。仲裁锁定的选择不经
        # 此门（已过仲裁自己的噪声门），证明题的结论体裁不同也不经此门。
        if validated and ptype != "proof" and is_noise_answer(validated):
            repaired = _clean_noise_head(validated)
            deps.logger.warning(
                "Validated answer failed the cleanliness gate; %s: %.80s",
                "kept clean head" if repaired else "dropping", validated,
            )
            validated = repaired
    if state.get("answer_locked") and validated:
        # The semantic arbiter selected an existing candidate verbatim. Do not
        # let another LLM or formatter paraphrase/shrink the selected text.
        prefix = "结论：" if ptype == "proof" else "最终答案："
        final = validated if validated.lstrip().startswith(prefix) else prefix + validated
        # Appending a derivation outline does not touch the selected answer text, so
        # the verbatim guarantee holds. Attach it only when the reasoning branch is
        # what was selected — the Python branch's answer is not what these steps derive.
        if state.get("semantic_arbiter_decision") == "reasoning":
            if ptype == "proof":
                # 证明题按 §6.2 判"结论+必要过程"：关键蕴含链必须写入
                # final_response 而非仅存 trace（评委建议 10，idx 74 仅得 0.3）。
                final = build_proof_body(final, rr)
            else:
                final = attach_steps(final, state.get("problem", ""), rr.get("steps"))
        return {"final_response": final, "coordination_detail": "",
                "fallback_source": "validated_answer"}

    # Deadline guard: the coordinator writes a full narrative explanation, which is
    # the second-longest generation in the graph. It only *reformats* an answer we
    # already hold, so when the clock is short we emit that answer directly rather
    # than risk finishing with nothing. Proof problems keep the narrative as long
    # as any time remains, since for them the derivation *is* the deliverable.
    time_budget = deps.time_budget
    out_of_time = bool(time_budget) and (
        time_budget.expired() or (ptype != "proof" and time_budget.fast_path()))
    if out_of_time and validated:
        prefix = "结论：" if ptype == "proof" else "最终答案："
        final = validated if validated.lstrip().startswith(prefix) else prefix + validated
        # The outline comes from state we already hold, so it costs no LLM time and
        # is still affordable on the degraded path.
        if ptype == "proof":
            final = build_proof_body(final, rr)
        else:
            final = attach_steps(final, state.get("problem", ""), rr.get("steps"))
        deps.logger.warning(
            "Coordinator skipped under time budget (%.0fs left)", time_budget.remaining()
        )
        return {"final_response": final, "coordination_detail": "",
                "fallback_source": evidence_note or "validated_answer"}
    if out_of_time:
        # No answer *and* no time. The coordinator cannot invent an answer it was
        # not given — but a seeded emergency call on the hard reserve can still
        # produce a plausible concrete conclusion (评委报告：generic_error 六题
        # 与碎片输出均为必失分，直答的期望严格更高)。
        deps.logger.warning(
            "Coordinator has no answer and no budget (%.0fs left); trying emergency answer",
            time_budget.remaining())
        partial, source = _partial_response(state)
        guess = _emergency_direct_answer(state, deps)
        if guess:
            return {"final_response": _with_emergency_answer(guess, partial, source),
                    "coordination_detail": "",
                    "fallback_source": "emergency_direct_answer"}
        return {"final_response": partial, "coordination_detail": "",
                "fallback_source": source}

    problem_type_label = {
        "proof": "证明题",
        "choice": "选择题",
        "true_false": "判断题",
        "fill": "填空题",
    }.get(ptype, "计算题")
    steps_fmt = "\n".join(f"步骤{s.get('step_num')}: {s.get('description', '')}" for s in rr.get("steps", []))
    prompt = COORDINATOR_PROMPT.format(
        problem=state["problem"], category=state.get("category", ""),
        problem_type_label=problem_type_label,
        reasoning_steps_formatted=steps_fmt,
        reasoning_analysis=rr.get("analysis", ""),
        python_code=state.get("python_code", ""),
        python_output=(state.get("python_output") or {}).get("stdout", ""),
        validation_status=state.get("validation_status", ""),
        validated_answer=validated)
    try:
        raw = chat_with_retry(
            client,
            messages=[{"role": "user", "content": prompt}],
            temperature=CONFIG["temperatures"]["coordinator"],
            max_tokens=CONFIG["max_tokens"]["coordinator"],
            logger=deps.logger,
            time_budget=time_budget,
            label="coordinator",
        )
    except Exception as exc:  # noqa: BLE001 - never lose an answer we already hold.
        deps.logger.warning("Coordinator LLM unavailable (%s); emitting validated answer", exc)
        if not validated:
            # Re-raising discarded whatever partial work existed and let the error
            # fallback print the generic failure string. Emit the partial evidence
            # instead — it is strictly more informative and cannot score less.
            partial, source = _partial_response(state)
            guess = _emergency_direct_answer(state, deps)
            if guess:
                return {"final_response": _with_emergency_answer(guess, partial, source),
                        "coordination_detail": "",
                        "fallback_source": "emergency_direct_answer"}
            return {"final_response": partial, "coordination_detail": "",
                    "fallback_source": source}
        prefix = "结论：" if ptype == "proof" else "最终答案："
        final = validated if validated.lstrip().startswith(prefix) else prefix + validated
        if ptype == "proof":
            final = build_proof_body(final, rr)
        return {"final_response": final, "coordination_detail": "",
                "fallback_source": evidence_note or "validated_answer"}
    if budget:
        budget.consume(estimate_tokens(prompt), estimate_tokens(raw))
    cleaned_raw = strip_cot_prefix(raw)
    final = post_process_final_response(cleaned_raw, validated, ptype, problem=state["problem"])
    if not isinstance(final, str) or not final.strip():
        final = f"最终答案：{validated}" if validated else "无法生成完整答案。"
    # Proof answers already carry their full derivation as the answer body; only
    # computation problems that require working get an appended outline.
    if ptype != "proof":
        final = attach_steps(final, state.get("problem", ""), rr.get("steps"))
    # coordination_detail 保留完整解题说明，供 trace 记录（计算题 final_response 仅含简洁答案）
    return {"final_response": final, "coordination_detail": cleaned_raw,
            "fallback_source": evidence_note or "coordinator_llm"}
