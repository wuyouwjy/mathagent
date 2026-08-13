"""Raise the injected client's socket timeout so slow-but-healthy calls survive.

Measured failure, 2026-07-29 judge run: every reasoning attempt on Q1 died with
`reasoning:failed` at 363s — exactly 3 x the client's 120s socket timeout, i.e. the
client's internal retries all expired. The call was not hung; a single reasoning
call on this model legitimately runs 77-116s solo, and under four-problem parallel
load it exceeds 120s. So a 120s socket timeout does not protect against hangs here,
it *guarantees* failure on hard problems and returns nothing at all.

This became visible only after classification dropped from ~40s to ~1s: that delay
had been accidentally staggering the parallel problems, and removing it made all
four fire their reasoning calls at once. Fixing the stage exposed the real limit.

Scope: transport only. The platform still owns the client, the model, rate limiting
and token accounting — this reaches for one attribute, best-effort, and leaves the
client untouched if it is absent or read-only. It is deliberately conservative
because the injected client is not ours to reshape.
"""

from __future__ import annotations

import logging

#: A hard problem's reasoning call is the longest single request in the graph. The
#: per-problem deadline (TimeBudget) is what actually bounds runtime, so the socket
#: timeout only needs to be long enough not to sever a healthy call.
#:
#: 2026-08-09 评委工程备注：900s 贴近单题 20 分钟硬上限，叠加重试有撞线风险。
#: 首轮 max_tokens 已降为 24576（典型 ~450s，慢速负载下 ~700s），780s 足以覆盖
#: 最慢的健康调用，同时任何在软窗口内发出的调用都能在硬上限前收尾或超时返回。
DESIRED_SOCKET_TIMEOUT_S = 780
MAX_INTERNAL_RETRIES = 1


def raise_socket_timeout(client, desired: int = DESIRED_SOCKET_TIMEOUT_S, logger=None) -> dict:
    """Best-effort raise of `client.timeout`. Never lowers it, never raises.

    Returns a small report so the caller can record what actually happened rather
    than assuming it worked.
    """
    log = logger or logging.getLogger("math_agent")
    report = {"attempted": desired, "before": None, "after": None, "changed": False}

    current = getattr(client, "timeout", None)
    report["before"] = current
    if current is None:
        log.info("Client exposes no socket timeout; leaving transport as provided.")
        return report
    try:
        numeric = float(current)
    except (TypeError, ValueError):
        log.info("Client socket timeout %r is not numeric; leaving as provided.", current)
        return report
    if numeric >= desired:
        report["after"] = current
        return report

    try:
        client.timeout = desired
    except Exception as exc:  # noqa: BLE001 - read-only property or frozen client.
        log.warning("Could not raise client socket timeout (%s); keeping %ss.", exc, numeric)
        report["after"] = current
        return report

    report["after"] = getattr(client, "timeout", None)
    report["changed"] = report["after"] != current
    if report["changed"]:
        log.info("Raised client socket timeout %ss -> %ss so long reasoning calls "
                 "are not severed mid-generation.", numeric, report["after"])
    return report


def cap_internal_retries(client, maximum: int = MAX_INTERNAL_RETRIES, logger=None) -> dict:
    """Best-effort cap for a client's *inner* transport retry loop.

    The graph owns an outer, deadline-aware retry wrapper.  Leaving an injected
    ``retry=3`` client untouched creates a multiplicative retry budget (3 inner x
    3 outer requests), which can exceed the per-problem wall-clock limit after a
    long socket timeout.  Clients without a mutable ``retry`` attribute are left
    unchanged and reported as such.
    """
    log = logger or logging.getLogger("math_agent")
    report = {"attempted": int(maximum), "before": None, "after": None, "changed": False}
    current = getattr(client, "retry", None)
    report["before"] = current
    if current is None:
        log.info("Client exposes no internal retry count; leaving transport as provided.")
        return report
    try:
        numeric = int(current)
    except (TypeError, ValueError):
        log.info("Client internal retry count %r is not numeric; leaving it unchanged.", current)
        return report
    target = max(1, int(maximum))
    if numeric <= target:
        report["after"] = current
        return report
    try:
        client.retry = target
    except Exception as exc:  # noqa: BLE001 - injected clients may be read-only.
        log.warning("Could not cap client internal retries (%s); keeping %s.", exc, numeric)
        report["after"] = current
        return report
    report["after"] = getattr(client, "retry", None)
    report["changed"] = report["after"] != current
    if report["changed"]:
        log.info("Capped client internal retries %s -> %s; outer retries remain deadline-aware.",
                 numeric, report["after"])
    return report
