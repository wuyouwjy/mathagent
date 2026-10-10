"""选择性多采样投票（self-consistency）。

对"低置信"题，用全卷剩余 surplus 做 N 次独立采样（高温度）取多数票，把
G9 浪费的 ~2.5h 空余墙钟兑换成正确率。

触发（三者同时满足）：
  1. 题型适用：question_mode ∈ {computation, choice, true_false, fill}（非 proof，
     证明题的结论无法标量投票）；
  2. 低置信：fallback_source 为兜底来源（emergency/partial/tail/generic_error 等，
     这些几乎必错/白卷），或 validation_status 落于仲裁未定论（mismatch/uncertain/
     contradict → arbitrating）；
  3. 时间充裕：PaperPacer.surplus_budget_s() ≥ N×采样估时 + 余量（从全卷"多出来的
     时间"出钱，不碰"剩余题 × MIN_SOFT"的完成底线）。

保守覆盖：只有当 N 次采样里出现"≥2 票一致（多数）且不同于原答案"的共识时才
覆盖 final_response，否则保留原答案（避免把"对但低置信"的仲裁答案改错）。

采样复用 reasoning 首轮的同一套 prompt 与解析器（REASONING_PROMPT +
mode_instruction + structure_instruction），但温度抬到 0.7 提供采样多样性；
**不注入首轮答案**，保证采样独立性（self-consistency 的核心假设）。
"""

from __future__ import annotations

import re

from config import CONFIG
from utils.llm.templates import REASONING_PROMPT
from utils.llm.retry import LLMRetryWrapper
from utils.answer.cot_stripper import is_placeholder_answer
from utils.answer.matcher import AnswerMatcher
from utils.budget.token import estimate_tokens
from utils.problem.profile import (
    count_blanks,
    is_objective_mode,
    mode_instruction,
    structure_instruction,
)
from utils.skills_util.excerpt import select_skill_excerpt
from graph.nodes.reasoning import _reference_examples_block, _parse_reasoning_output

#: 采样次数（多数票：≥2/3 一致才视为共识）。3 比 2 更优——对单采样正确率
#: p≈0.6 的"心算/选项"题，3 采样多数票共识正确率 ≈ 0.65 > 0.5（正收益），
#: 而 2 采样全票 ≈ 0.36 < 0.5（负收益）。
N_SAMPLES = 3

#: 单次采样估时（秒）。完整 CoT reasoning 实测 72-164s，取偏上值作保守定价。
SAMPLE_ESTIMATE_S = 150.0

#: 采样后仍需保有的全卷完成底线余量（秒）。
SURPLUS_MARGIN_S = 120.0

#: 采样温度：高于首轮 0.3，提供采样多样性（主办方已确认 temperature 生效）。
SAMPLE_TEMPERATURE = 0.7

#: 采样后的"单题硬限余量"（秒）：采样用 remaining_hard 定价（reserve_margin_s
#: 模式）——invoke 后单题软预算已耗尽（首轮 784s+），但 20min 硬限还剩 400s+。
#: 采样只许在 remaining_hard ≥ 采样估时 + 本余量 时发起，保证不把单题顶过
#: 20min 平台硬限；采样次数由硬限自然截断（medium/hard 约 2 次，easy 约 3 次）。
SAMPLE_HARD_MARGIN_S = 90.0

#: 兜底来源（几乎必错/白卷）：双分支全灭或只拿到残片时的 fallback_source。
_LOW_CONFIDENCE_FALLBACK = {
    "emergency_direct_answer", "generic_error", "reasoning_tail",
    "partial_findings", "reasoning_conclusion", "python_answer",
    "python_stdout_mined",
}

#: 仲裁未定论状态：语义仲裁靠"二选一"而非确定性验证，仍属低置信。
_LOW_CONFIDENCE_STATUS = {
    "mismatch_arbitrating", "uncertain_arbitrating", "contradict_arbitrating",
}


def _is_low_confidence(state: dict) -> bool:
    """本题是否"低置信"（值得花 surplus 做多采样）。"""
    if state.get("fallback_source", "") in _LOW_CONFIDENCE_FALLBACK:
        return True
    status = state.get("validation_status", "") or ""
    # 所有 *_arbitrating 后缀（mismatch/uncertain/contradict/reconciliation_exhausted）
    # 都是仲裁未定论。用后缀兜底而非只枚举集合，避免新增状态值漏触发（实测 idx 0
    # 是 reconciliation_exhausted_arbitrating，首次枚举版漏了它 → 采样未触发）。
    return status in _LOW_CONFIDENCE_STATUS or status.endswith("_arbitrating")


def should_consistency_vote(state: dict) -> bool:
    """触发判定：题型适用 + 低置信 + 全卷 surplus 充裕。"""
    if not CONFIG.get("enable_consistency_vote", False):
        return False
    question_mode = state.get("question_mode", "")
    if question_mode == "proof":
        return False
    if not _is_low_confidence(state):
        return False
    cost = N_SAMPLES * SAMPLE_ESTIMATE_S + SURPLUS_MARGIN_S
    try:
        from utils.budget.paper_pacer import PaperPacer
        return PaperPacer.get_instance().surplus_budget_s() >= cost
    except Exception:  # noqa: BLE001 - 无全卷引擎则保守跳过
        return False


def _build_objective_sample_prompt(problem: str, category: str,
                                   question_mode: str, skill_doc: str) -> str:
    """客观题采样 prompt：两行契约（与首轮一致），保证答案可规范化解析。"""
    if question_mode == "fill":
        blank_count = count_blanks(problem)
        blank_note = f"题面共 {blank_count} 个空位。" if blank_count >= 2 else ""
        answer_shape = (
            f"{blank_note}答案行按空位顺序写全部结果，多空用分号分隔"
            "（如：空1: <结果>；空2: <结果>）。每空必须填教材术语/数值/明确方向，"
            "禁止填'不确定'，禁止输出任何操作说明文字"
        )
    elif question_mode == "true_false":
        answer_shape = "答案行只写：正确 或 错误"
    else:
        answer_shape = "先判断单选/多选，答案行列出全部正确选项字母；措辞不精确的选项一律不选"
    return (
        "你是数学、统计学与计量经济学教师。严格按题库教材定义逐项核对题面选项/空位，"
        "特别检查相近概念的边界。不要展开长篇推导，不要输出 Thinking Process。"
        "必须只输出两行：\n"
        f"答案：<{answer_shape}>\n"
        "依据：<不超过三句的定理/计算核对>\n\n"
        f"题型：{question_mode}\n学科：{category}\n技能参考：\n"
        f"{select_skill_excerpt(skill_doc, problem, 2200)}\n\n题目：\n{problem}"
    )


def _build_sample_prompt(problem: str, category: str, question_mode: str,
                         skill_doc: str, retrieved: list | None) -> str:
    """采样 prompt：复用 reasoning 首轮的同一套（不含首轮答案，保证独立）。"""
    if is_objective_mode(question_mode):
        return _build_objective_sample_prompt(problem, category, question_mode, skill_doc)
    examples_text = _reference_examples_block(retrieved, problem)
    prompt = REASONING_PROMPT.format(
        category=category,
        skill_document=select_skill_excerpt(skill_doc, problem, 3000) + examples_text,
        problem=problem,
    )
    prompt += mode_instruction(question_mode)
    prompt += structure_instruction(problem)
    # 采样要的是"独立的新答案"，不是完整推导：引导答案优先，省 token 提速。
    prompt += (
        "\n\n[独立求解] 请独立重新求解本题，不要受任何已有答案影响。"
        "先在思考中锁定最可信的最终结论，再写出关键推导步骤，确保 '## 最终答案' "
        "给出明确结论。"
    )
    return prompt


def _answers_equivalent(a: str, b: str) -> bool:
    """两个答案是否等价（用于投票分组）。"""
    a = (a or "").strip()
    b = (b or "").strip()
    if not a or not b:
        return False
    if is_placeholder_answer(a) or is_placeholder_answer(b):
        return False
    if a == b:
        return True
    ka = re.sub(r"[\s。．.,，;；、和及&]+", "", a)
    kb = re.sub(r"[\s。．.,，;；、和及&]+", "", b)
    if ka and kb and ka == kb:
        return True
    try:
        if AnswerMatcher._sympy_equivalent(a, b, 1e-6) is True:
            return True
    except Exception:  # noqa: BLE001 - 解析失败退回字符串比较
        pass
    return False


def _extract_answer_value(state: dict) -> str:
    """从 state 提取"原答案"（用于判断共识是否不同）。尽力而为，不准也仅影响
    "是否覆盖"的判定，最坏是覆盖成一个等价答案（不影响判分）。"""
    validated = str(state.get("validated_answer") or "").strip()
    if validated and not is_placeholder_answer(validated):
        return validated
    final = state.get("final_response", "")
    m = re.search(r"(?:最终答案|结论)\s*[：:]\s*(.+?)(?:\n|$)", final or "")
    return m.group(1).strip() if m else ""


def _sample_answer(deps, prompt: str, question_mode: str) -> str:
    """独立采样一次，返回解析出的答案（失败/空返回 ""）。

    时钟用 reserve_margin_s（remaining_hard 定价）：采样本应从全卷 surplus 出钱
    （PaperPacer.surplus_budget_s），而 invoke 后单题软预算已耗尽——若仍用
    chat_with_retry 的 can_afford（软预算）会把采样整体挡住（实测 "116s left,
    need ~150s"）。改为只要求单题硬限 remaining_hard ≥ 采样估时 + 余量，采样
    次数由 20min 硬限自然截断；全卷完成底线由调用方采样前的 surplus 复查保证。
    """
    wrapper = LLMRetryWrapper(
        deps.client,
        max_retries=CONFIG["llm_max_retries"],
        backoff_factor=CONFIG["backoff_factor"],
        logger=deps.logger,
        time_budget=deps.time_budget,
        expected_call_seconds=SAMPLE_ESTIMATE_S,
        reserve_margin_s=SAMPLE_HARD_MARGIN_S,
    )
    try:
        resp = wrapper.chat(
            messages=[{"role": "user", "content": prompt}],
            temperature=SAMPLE_TEMPERATURE,
            max_tokens=CONFIG["max_tokens"]["reasoning"],
            label="consistency_sample",
        )
    except Exception as exc:  # noqa: BLE001 - 硬限耗尽/传输失败则跳过本次采样
        deps.logger.warning("Consistency sample failed: %s", exc)
        return ""
    if deps.token_budget:
        deps.token_budget.consume(estimate_tokens(prompt), estimate_tokens(resp))
    parsed = _parse_reasoning_output(resp, question_mode=question_mode)
    answer = str(parsed.get("answer") or "").strip()
    if not answer or is_placeholder_answer(answer):
        return ""
    return answer


def _consensus_override(original: str, samples: list[str]) -> str | None:
    """多数票共识：返回覆盖答案，或无共识/共识等于原答案时返回 None。"""
    valid = [s for s in samples if s and not is_placeholder_answer(s)]
    if len(valid) < 2:
        return None
    groups: list[list] = []  # [representative, count]
    for s in valid:
        for g in groups:
            if _answers_equivalent(g[0], s):
                g[1] += 1
                break
        else:
            groups.append([s, 1])
    best = max(groups, key=lambda g: g[1])
    if best[1] < 2:
        return None
    if _answers_equivalent(original, best[0]):
        return None
    return best[0]


def maybe_consistency_vote(state: dict, deps) -> dict:
    """多采样投票后处理：返回要合并进 final_state 的更新 dict（不触发则空 dict）。

    供 MathAgentGraph.run() 在 invoke 之后调用；不侵入任何 LangGraph 节点。
    """
    if not should_consistency_vote(state):
        return {}
    problem = state.get("problem", "")
    category = state.get("category", "")
    question_mode = state.get("question_mode", "")
    skill_doc = ""
    try:
        if deps.skills_loader:
            skill_doc = deps.skills_loader.get_skill_document(category) or ""
    except Exception:  # noqa: BLE001 - skill 加载失败用空文档采样
        skill_doc = ""
    prompt = _build_sample_prompt(
        problem, category, question_mode, skill_doc, state.get("retrieved_examples"))
    original = _extract_answer_value(state)

    samples: list[str] = []
    for _ in range(N_SAMPLES):
        # 每次采样前都复查全卷 surplus，避免采样把完成底线花穿。
        try:
            from utils.budget.paper_pacer import PaperPacer
            if PaperPacer.get_instance().surplus_budget_s() < SAMPLE_ESTIMATE_S:
                deps.logger.info("Consistency vote: surplus exhausted after %d samples",
                                 len(samples))
                break
        except Exception:  # noqa: BLE001
            pass
        samples.append(_sample_answer(deps, prompt, question_mode))

    consensus = _consensus_override(original, samples)
    trace = {
        "step": "consistency_vote",
        "question_mode": question_mode,
        "n_samples": len(samples),
        "original": original[:200],
        "samples": [s[:200] for s in samples],
        "consensus": (consensus or "")[:200],
        "overridden": consensus is not None,
    }
    if consensus is None:
        return {"consistency_vote_trace": trace}
    prefix = "结论：" if question_mode == "proof" else "最终答案："
    final_response = consensus if consensus.lstrip().startswith(prefix) else prefix + consensus
    deps.logger.info("Consistency vote overrode answer (%.60s → %.60s)",
                     original, consensus)
    return {"final_response": final_response, "consistency_vote_trace": trace}
