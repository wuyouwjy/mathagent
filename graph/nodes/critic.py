"""过程审计智能体（Critic）：定稿前的最后一道质量门（移植自 VeritasMath）。

基线架构的缺口：交叉验证只回答"两路答案是否一致"，仲裁只回答"哪个候选更完整"，
没有任何环节系统性地回答"**答案是否覆盖了题面的全部要求**"。评委报告显示这是
稳定失分源——多问漏答（idx 14 三值报一）、契约缺项（idx 86 三空答零空）、
证明过程留在 trace 没进 final_response。

Critic 在 coordinator 之前运行，做两级审计：
1. 确定性契约（answer_contract，零成本）+ LLM 契约审计（prefill，~15s）合并判定；
2. LLM 对 1-3 个中间计算做抽核（calc_error 是比"缺项"更强的重算信号）。

路由哲学：审计不制造答案，只产生**定向修复提示**——缺口明确且预算可负担时回调
solving 做定点补算（复用既有重试定价与轮次上限），否则带缺口标记进 coordinator
（formatter 仍有最后一次从完整说明回捞的机会）。audit 轮次由 critic_rounds 独立
计数，最多触发 1 次修复，杜绝审计-重算死循环。
"""

from __future__ import annotations

from config import CONFIG
from utils.answer.contract import missing_components
from utils.answer.cot_stripper import is_placeholder_answer
from utils.verify.critic_audit import (
    build_repair_hint,
    merge_with_deterministic,
    parse_critic_verdict,
)
from utils.deps import get_deps
from utils.llm.retry import chat_prefilled
from utils.llm.templates import (
    CRITIC_PREFILL,
    CRITIC_PROMPT,
    CRITIC_SYSTEM_PROMPT,
)
from utils.problem.profile import is_objective_mode
from utils.verify.reconciliation_policy import reconciliation_retry_available
from utils.budget.token import estimate_tokens

_MAX_ANSWER_CHARS = 6000
_MAX_PROBLEM_CHARS = 8000
#: 抽核与契约判定是轻量判断，prefill 后输出 ~200-400 token；给 1024 防截断。
_CRITIC_MAX_TOKENS = 1024
_CRITIC_CALL_ESTIMATE_S = 25
#: Critic 最多购买一次修复重算；第二次到 Critic 时无论缺口如何都放行。
_MAX_CRITIC_REPAIR_ROUNDS = 1


def _bounded(value, limit: int) -> str:
    text = value if isinstance(value, str) else str(value or "")
    return text if len(text) <= limit else text[:limit].rstrip() + "\n...[truncated]"


def _process_summary(state: dict) -> str:
    """供审计参考的过程摘要：推理分析 + 步骤 + Python 证据，定长截断。"""
    rr = state.get("reasoning_result") or {}
    po = state.get("python_output") or {}
    parts = []
    analysis = str(rr.get("analysis") or "").strip()
    if analysis:
        parts.append("推理分析：" + _bounded(analysis, 1500))
    steps = [f"步骤{s.get('step_num', '?')}: {s.get('description', '')}"
             for s in (rr.get("steps") or [])][:12]
    if steps:
        parts.append("推理步骤：\n" + _bounded("\n".join(steps), 2500))
    evidence = str(po.get("evidence_summary") or state.get("python_evidence_summary") or "").strip()
    if evidence:
        parts.append("程序验证证据：" + _bounded(evidence, 800))
    return "\n\n".join(parts) or "（无过程记录）"


def _llm_audit(state: dict, deps, answer: str) -> dict | None:
    """prefill 契约审计调用；失败/超时/解析失败返回 None（不阻塞主链路）。"""
    clock = deps.time_budget
    margin = CONFIG.get("critic_reserve_margin_s", 60)
    if clock and clock.remaining_hard() - margin < _CRITIC_CALL_ESTIMATE_S:
        return None
    prompt = CRITIC_PROMPT.format(
        problem=_bounded(state.get("problem", ""), _MAX_PROBLEM_CHARS),
        process_summary=_process_summary(state),
        answer=_bounded(answer, _MAX_ANSWER_CHARS),
    )
    try:
        raw = chat_prefilled(
            deps.client,
            messages=[
                {"role": "system", "content": CRITIC_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            prefix=CRITIC_PREFILL,
            temperature=0.1,
            max_tokens=_CRITIC_MAX_TOKENS,
            logger=deps.logger,
            time_budget=clock,
            expected_call_seconds=_CRITIC_CALL_ESTIMATE_S,
            label="critic_prefill",
            reserve_margin_s=margin,
        )
    except Exception as exc:  # noqa: BLE001 - 审计失败不阻塞出答案
        deps.logger.warning("Critic LLM audit unavailable: %s", exc)
        return None
    if deps.token_budget:
        deps.token_budget.consume(estimate_tokens(prompt), estimate_tokens(raw))
    return parse_critic_verdict(raw)


def critic_node(state, config):
    if not CONFIG.get("enable_critic", True):
        return {"critic_status": "skipped", "critic_trace": [],
                "next_node": "coordinator"}
    deps = get_deps(config)
    trace = list(state.get("critic_trace") or [])
    rounds = state.get("critic_rounds", 0)
    question_mode = state.get("question_mode", "")

    answer = str(state.get("validated_answer") or "").strip()
    if not answer:
        rr = state.get("reasoning_result") or {}
        answer = str(rr.get("answer") or "").strip()
    if not answer or is_placeholder_answer(answer):
        # 没有候选可审：coordinator 的部分结论/应急直答通道接管，审计无对象。
        trace.append({"round": rounds, "status": "skipped", "reason": "no_answer"})
        return {"critic_status": "skipped", "critic_trace": trace,
                "next_node": "coordinator"}

    # 客观题走自己的完整性检查（空位数对齐已在 cross_validator 做过并降置信），
    # LLM 审计对单字母/单值答案没有增量信息，跳过以保快速路径。
    if is_objective_mode(question_mode):
        trace.append({"round": rounds, "status": "pass", "reason": "objective_fast_path"})
        return {"critic_status": "pass", "critic_trace": trace, "critic_rounds": rounds,
                "next_node": "coordinator"}

    deterministic_missing = missing_components(state.get("problem", ""), answer)
    # 推导矛盾自检：推理链内同一变量出现两个不同数值说明中间步骤自相矛盾。
    # 纯正则零 API，命中即按 calc_error 级处理（比缺项更重，优先触发定向修复）。
    from utils.verify.derivation_conflict import detect_derivation_conflict
    conflict = detect_derivation_conflict(_process_summary(state))
    llm_verdict = _llm_audit(state, deps, answer)
    merged = merge_with_deterministic(llm_verdict, deterministic_missing)
    verdict = merged["verdict"]
    if conflict and verdict == "pass":
        verdict = "calc_error"
        merged["verdict"] = "calc_error"
        merged.setdefault("calc_checks", []).append(
            {"check": "推导矛盾自检", "ok": False, "note": conflict})
    elif conflict:
        merged.setdefault("calc_checks", []).append(
            {"check": "推导矛盾自检", "ok": False, "note": conflict})
    trace.append({
        "round": rounds,
        "status": verdict,
        "missing": merged.get("missing", []),
        "calc_checks": merged.get("calc_checks", []),
        "llm_available": merged.get("llm_available", False),
        "deterministic_missing": list(deterministic_missing or []),
        "derivation_conflict": conflict or "",
    })

    if verdict == "pass":
        return {"critic_status": "pass", "critic_trace": trace,
                "critic_missing": merged.get("missing", []),
                "critic_rounds": rounds, "next_node": "coordinator"}

    # 缺口成立。可负担且未超修复轮次时回调解做定向补算；否则带缺口标记进
    # coordinator（answer 不被改写，缺口信息供 formatter 回捞与 trace 留证）。
    can_repair = (
        rounds < _MAX_CRITIC_REPAIR_ROUNDS
        and reconciliation_retry_available(state, config)
    )
    if can_repair:
        hint = build_repair_hint(merged, answer)
        return {
            "critic_status": verdict,
            "critic_missing": merged.get("missing", []),
            "critic_trace": trace,
            "critic_rounds": rounds + 1,
            "reasoning_retry_hint": hint,
            "python_retry_hint": hint + "\n请用代码独立验证补齐后的结论。",
            "repair_hint_source": "critic",
            "next_node": "reconciliation",
        }
    return {
        "critic_status": verdict,
        "critic_missing": merged.get("missing", []),
        "critic_trace": trace,
        "critic_rounds": rounds,
        "next_node": "coordinator",
    }
