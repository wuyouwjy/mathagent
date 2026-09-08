"""Shared reconciliation-round policy for validation and retry routing.

A reconciliation round re-runs the whole solving subgraph — another reasoning call
plus another Python call. On this model that is the most expensive action available
(a single reasoning call measured 77-116s on a mid-difficulty problem, and hard
problems run longer), so the round limit is gated by both budgets: tokens, and now
wall clock. Buying a rerun we cannot finish is strictly worse than answering with
what we already have.
"""

from config import CONFIG
from utils.deps import get_deps
from utils.budget.affordability import DEFAULT_ATTEMPT_COST_S, last_attempt_cost
from utils.problem.profile import classify_question_mode


def _deps(config):
    try:
        return get_deps(config)
    except Exception:  # noqa: BLE001 - callers may pass a bare config in tests.
        return None


def reconciliation_round_limit(config) -> int:
    deps = _deps(config)
    budget = getattr(deps, "token_budget", None)
    clock = getattr(deps, "time_budget", None)
    if clock is not None and clock.fast_path():
        # No room for another full solving pass; allow only the round already done.
        return 1
    if budget and budget.is_tight():
        return 1
    return CONFIG["reconciliation_max_rounds"]


def projected_solving_seconds(time_budget) -> float:
    """Estimate one more parallel reasoning/Python pass from observed costs."""
    if time_budget is None:
        return 0.0
    return max(
        last_attempt_cost(time_budget, "reasoning"),
        last_attempt_cost(time_budget, "python"),
        DEFAULT_ATTEMPT_COST_S,
    )


def reconciliation_retry_available(state, config, *, force: bool = False) -> bool:
    """Whether entering reconciliation can still produce another solving run.

    ``force`` 用于未决证据缺口，可动用硬时钟 reserve，但绝不绕过断路器或快路径；
    默认路径对既有调用方保持不变。
    V3 证明题重试收敛：proof 无 Python 锚定，critic 判缺项后第 2 次完整 reasoning
    的边际收益≈0。实测 idx 1「60阶单群≅A5」：第 2 次 reasoning（280s）仍被判缺项、
    其产出从未被采纳（validated_answer 保持第 1 次的中间结论，最终靠 coordinator_llm
    独立成稿才正确）。证明题直接成稿，省一次完整推理（~280-527s），几乎不损正确率。
    force 也不得绕过这条：证明题不存在"代回复算"的独立复核价值。
    """
    question_mode = state.get("question_mode") or classify_question_mode(state.get("problem", ""))
    if question_mode == "proof":
        return False
    completed_rounds = state.get("reconciliation_round", 0)
    if completed_rounds + 1 >= reconciliation_round_limit(config):
        return False
    if force and state.get("forced_recheck_used"):
        return False
    deps = _deps(config)
    clock = getattr(deps, "time_budget", None)
    if clock is None:
        return True
    if clock.fast_path():
        return False
    projected = projected_solving_seconds(clock)
    if force:
        reserve = float(CONFIG.get("forced_recheck_reserve_s", 240))
        hard_remaining = getattr(clock, "remaining_hard", clock.remaining)()
        return hard_remaining >= projected + reserve
    return clock.can_afford(projected)
