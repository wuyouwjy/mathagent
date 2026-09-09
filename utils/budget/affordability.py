"""How much would one more attempt cost? Ask the clock, not an optimistic constant.

An agent node's retry is only worth buying if the deadline can fund a call that costs
what the last one cost. The failure this prevents (olympiad-level problem, 2026-07-29):
reasoning and Python each ran twice at 510-552s per attempt, the second attempt on each
branch was authorised with ~349s of budget left, and the problem overran its deadline by
198s to finish with no answer at all. Both branches had spent everything and delivered
nothing — the worst possible trade.
"""

from __future__ import annotations

#: Fallback estimate when nothing comparable has been measured yet this problem. Chosen
#: from measured hard-problem calls (510-552s) rather than easy ones, because the whole
#: point is to avoid authorising an attempt we cannot finish.
DEFAULT_ATTEMPT_COST_S = 300.0

#: 压缩重试（reasoning_compressed / python_compressed）是"便宜的短调用"，不能用来
#: 给完整调用定价：用它实测的 27s 去授权一次 132s 的完整二次验证，等于让预算判断
#: 永远说"付得起"（2026-09-09 idx 0 实测：compressed 27s → full_retry 132s 被放行）。
#: 定价只看完整调用；预算充足时结论不变（DEFAULT_ATTEMPT_COST_S=300 仍付得起），
#: 只有在 PaperPacer 收紧后才会拒绝——那正是该拒绝的时候。
_COMPRESSED_MARKER = "compressed"


def last_attempt_cost(time_budget, label_prefix: str) -> float:
    """Cost of the most recent full call whose label starts with `label_prefix`.

    Falls back to DEFAULT_ATTEMPT_COST_S when this problem has no comparable call yet.
    Failed attempts count: a transport failure that burned 363s will burn it again.
    Compressed retries are excluded — see _COMPRESSED_MARKER.
    """
    if time_budget is None:
        return 0.0
    matching = [entry["seconds"] for entry in time_budget.spend_log()
                if str(entry.get("label", "")).startswith(label_prefix)
                and _COMPRESSED_MARKER not in str(entry.get("label", ""))]
    return matching[-1] if matching else DEFAULT_ATTEMPT_COST_S


def can_afford_retry(time_budget, label_prefix: str) -> bool:
    """Whether another attempt of this kind fits in the remaining optional-work window."""
    if time_budget is None:
        return True
    return time_budget.can_afford(last_attempt_cost(time_budget, label_prefix))


def first_attempt_cap(time_budget, ceiling: float, compressed_estimate: float,
                      margin: float = 30.0, floor: float = 90.0) -> float:
    """首轮调用的墙钟上限：给压缩救援留出额度，不让首轮吃掉整题预算。

    首轮被切断后调用方会就地转入压缩重试/重生成（~150-200s）。若首轮上限固定为
    550s，PaperPacer 收紧后的 soft_total（落后时 ~480-540s）会被首轮一次吃光，
    压缩救援随即被 node_wrapper 的节点超时掐掉——而 reasoning_agent 被掐断时
    fallback 返回**空 answer**（见 utils/error_handler._fallback_for_node）。
    所以节点超时钳制（TimeBudget.timeout_for）与首轮上限必须一起收紧，只钳其一
    等于把救援挤掉，"省时"直接变成"丢答案"。

    健康预算（soft_total 未被收紧）下返回 ceiling 本身，行为与改动前一致。
    """
    if time_budget is None:
        return float(ceiling)
    avail = time_budget.soft_total - time_budget.elapsed()
    return min(float(ceiling),
               max(float(floor), avail - float(compressed_estimate) - float(margin)))
