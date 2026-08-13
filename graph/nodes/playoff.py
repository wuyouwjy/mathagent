"""确定性复算季后赛（Playoff）：候选冲突时的"代回裁决"（移植自 VeritasMath）。

基线架构在两路答案冲突时只有两条路：整轮 solving 子图重跑（最贵动作，~500-900s），
或语义仲裁（只能从既有候选中选——两个都错时必输，各对一半时只能选一边）。
评委报告 idx 20 是典型：Python 枚举出的公式与推理的 "4" 冲突，系统最终输出了
被自家程序反驳的答案。

Playoff 提供第三条路：不解原题，只做**候选代回核验**——方程回代看残差、极值
比较目标函数实测值、计数缩小规模暴力枚举对照、存在性实际搜索构造。一次 playoff
≈ 一次 LLM 代码生成（prefill 压缩通道，~60-150s）+ 一次沙箱执行（≤60s），成本
显著低于整轮重跑，且产出的是**确定性证据**而非又一次采样判断。

裁决结果：
- A / B / BOTH：某候选被独立计算支持 → validated_answer 直接锁定，进 Critic；
- NEITHER：两候选都被证伪（强信号）→ 带证伪信息回调解，换方法重算；
- INCONCLUSIVE / 执行失败 / 超时：不消耗额外预算，退回既有仲裁通道。
"""

from __future__ import annotations

import re

from config import CONFIG
from graph.nodes.python_exec import _extract_code
from utils.answer.cot_stripper import is_placeholder_answer
from utils.deps import get_deps
from utils.llm.retry import chat_prefilled
from utils.llm.templates import PLAYOFF_PROMPT
from utils.budget.token import estimate_tokens

#: 季后赛代码生成走 prefill 压缩通道（种子 "```python\n" 抑制私有推理），
#: 8192 token 全部用于代码；估时含一次执行时限。
_PLAYOFF_GEN_ESTIMATE_S = 150
_PLAYOFF_PREFILL = "```python\n"

# 长词必须排在短词前（BOTH 先于 B），否则交替匹配永远先命中前缀短词。
_RESULT_RE = re.compile(
    r"PLAYOFF_RESULT[：:]\s*(BOTH|NEITHER|INCONCLUSIVE|A|B)\b", re.IGNORECASE)
_CHECK_A_RE = re.compile(r"候选\s*A\s*核验[：:]\s*PASS", re.IGNORECASE)
_CHECK_B_RE = re.compile(r"候选\s*B\s*核验[：:]\s*PASS", re.IGNORECASE)


def _bounded(value, limit: int) -> str:
    text = value if isinstance(value, str) else str(value or "")
    return text if len(text) <= limit else text[:limit].rstrip() + "\n...[truncated]"


def _usable(value) -> str:
    text = str(value or "").strip()
    if not text or is_placeholder_answer(text):
        return ""
    return text


def playoff_candidates(state: dict) -> tuple[str, str]:
    """取冲突双方：主推理 vs Python；Python 缺席时用第二推理路径。都缺则无可季后赛。"""
    rr = _usable((state.get("reasoning_result") or {}).get("answer"))
    po = _usable((state.get("python_output") or {}).get("answer"))
    alt = _usable((state.get("reasoning_result_alt") or {}).get("answer"))
    if rr and po:
        return rr, po
    if rr and alt:
        return rr, alt
    if po and alt:
        return po, alt
    return "", ""


def parse_playoff_result(stdout: str) -> str:
    """从执行输出解析裁决：优先显式 PLAYOFF_RESULT 标记；缺失时由候选核验行推断。"""
    text = str(stdout or "")
    matches = _RESULT_RE.findall(text)
    if matches:
        return matches[-1].upper()
    a_pass = bool(_CHECK_A_RE.search(text))
    b_pass = bool(_CHECK_B_RE.search(text))
    if a_pass and b_pass:
        return "BOTH"
    if a_pass:
        return "A"
    if b_pass:
        return "B"
    return "INCONCLUSIVE"


def playoff_node(state, config):
    trace = list(state.get("playoff_trace") or [])
    if not CONFIG.get("enable_playoff", True):
        trace.append({"status": "skipped", "reason": "disabled"})
        return {"playoff_status": "skipped", "playoff_trace": trace,
                "next_node": "semantic_arbiter"}

    deps = get_deps(config)
    clock = deps.time_budget

    candidate_a, candidate_b = playoff_candidates(state)
    if not candidate_a or not candidate_b:
        trace.append({"status": "skipped", "reason": "insufficient_candidates"})
        return {"playoff_status": "skipped", "playoff_trace": trace,
                "next_node": "semantic_arbiter"}

    # 季后赛是"便宜的重跑替代"，预算规则与压缩重试同档：软预算可尽，但硬上限前
    # 必须容得下生成 + 执行 + 后续收尾。
    if clock and clock.remaining_hard() - CONFIG.get("compressed_reserve_margin_s", 150) \
            < (_PLAYOFF_GEN_ESTIMATE_S + CONFIG["node_timeouts"]["python_mcp_execute"]):
        trace.append({"status": "skipped", "reason": "unaffordable"})
        return {"playoff_status": "skipped", "playoff_trace": trace,
                "next_node": "semantic_arbiter"}

    prompt = PLAYOFF_PROMPT.format(
        problem=_bounded(state.get("problem", ""), 8000),
        candidate_a=_bounded(candidate_a, 2500),
        candidate_b=_bounded(candidate_b, 2500),
    )
    try:
        resp = chat_prefilled(
            deps.client,
            messages=[{"role": "user", "content": prompt}],
            prefix=_PLAYOFF_PREFILL,
            temperature=CONFIG["temperatures"]["python"],
            max_tokens=CONFIG["max_tokens"]["python_compressed"],
            logger=deps.logger,
            time_budget=clock,
            expected_call_seconds=_PLAYOFF_GEN_ESTIMATE_S,
            label="playoff_generate",
            reserve_margin_s=CONFIG.get("compressed_reserve_margin_s", 150),
        )
    except Exception as exc:  # noqa: BLE001 - 季后赛失败退回仲裁，不放大损失
        deps.logger.warning("Playoff generation failed: %s", exc)
        trace.append({"status": "error", "reason": str(exc)[:200]})
        return {"playoff_status": "error", "playoff_trace": trace,
                "next_node": "semantic_arbiter"}
    if deps.token_budget:
        deps.token_budget.consume(estimate_tokens(prompt), estimate_tokens(resp))

    code = _extract_code(resp)
    if not code:
        # 裁决代码缺失本身说明模型判断无法机械核验（证明题/概念题）——
        # 这不是故障，按 INCONCLUSIVE 退回语义仲裁。
        trace.append({"status": "indecisive", "reason": "no_verification_code"})
        return {"playoff_status": "indecisive", "playoff_trace": trace,
                "next_node": "semantic_arbiter"}

    if deps.mcp_client is None:
        trace.append({"status": "error", "reason": "executor_unavailable"})
        return {"playoff_status": "error", "playoff_trace": trace,
                "next_node": "semantic_arbiter"}
    output = deps.mcp_client.execute(
        code, timeout=CONFIG["node_timeouts"]["python_mcp_execute"])
    stdout = str(output.get("stdout") or "")
    verdict = parse_playoff_result(stdout)
    trace.append({
        "status": "executed",
        "verdict": verdict,
        "execute_success": bool(output.get("success")),
        "stdout_excerpt": _bounded(stdout, 1200),
        "stderr_excerpt": _bounded(output.get("stderr") or "", 400),
    })

    if verdict in {"A", "B", "BOTH"}:
        # BOTH：两候选数学等价，保留可读性更好的推理形态；A/B：锁定被支持方。
        if verdict == "A":
            chosen = candidate_a
        elif verdict == "B":
            chosen = candidate_b
        else:
            chosen = candidate_a if len(candidate_a) <= len(candidate_b) else candidate_b
        details = dict(state.get("validation_details") or {})
        details["playoff"] = {"verdict": verdict, "method": "deterministic_recompute"}
        return {
            "playoff_status": "decisive",
            "playoff_answer": chosen,
            "playoff_trace": trace,
            "validated_answer": chosen,
            "validation_details": details,
            "next_node": "critic",
        }
    if verdict == "NEITHER":
        # 双证伪是强信号：既有候选都不可信，值得换方法重算（走调解的既有轮次与
        # 定价闸门；负担不起时仲裁兜底仍可选一个"较不残"的候选）。
        hint = ("两个候选答案经独立复算均未通过核验（代回残差非零/小规模枚举不符/"
                "约束不可行）。两者都不可信，请彻底更换解题方法重新独立求解，"
                "并在最终答案前用代码验证新结论。")
        return {
            "playoff_status": "neither",
            "playoff_trace": trace,
            "reasoning_retry_hint": hint,
            "python_retry_hint": hint,
            "repair_hint_source": "playoff",
            "next_node": "reconciliation",
        }
    # 执行后仍无法裁决（INCONCLUSIVE/执行异常）：这是真正的语义僵局。playoff_trace
    # 非空保证不会再次进入季后赛，循环在结构上被排除。
    from utils.verify.reconciliation_policy import reconciliation_retry_available
    if reconciliation_retry_available(state, config):
        trace.append({"status": "indecisive", "verdict": verdict,
                      "routing": "reconciliation"})
        return {"playoff_status": "indecisive", "playoff_trace": trace,
                "next_node": "reconciliation"}
    trace.append({"status": "indecisive", "verdict": verdict,
                  "routing": "semantic_arbiter"})
    return {"playoff_status": "indecisive", "playoff_trace": trace,
            "next_node": "semantic_arbiter"}
