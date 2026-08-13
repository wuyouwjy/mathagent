"""Normalize Python executor output into evidence separate from process status.

2026-08-09 评委报告接线（建议 1/2）：
* 高置信答案通道（"最终答案:" 标记）为空时，从 stdout 保守挖掘候选答案并
  打上 ``answer_source="stdout_mined"``——正确公式已打印却因缺标记被丢弃的
  idx 20/76 类事故由此堵住；
* 携带 ``code`` 时做反伪造静态检查：无实质计算却宣称 PASS 的证据一律降级
  inconclusive，不得再被仲裁当作支持性证据锁定（idx 19/28/45/66）。
"""

from __future__ import annotations

import re

from utils.verify.stdout_miner import mine_stdout_answer
from utils.verify.authenticity import assess_verification_authenticity


_STATUS_RE = re.compile(
    r"验证状态\s*[:：]\s*(PASS|FAIL|INCONCLUSIVE)", re.IGNORECASE
)
_EVIDENCE_RE = re.compile(r"验证证据\s*[:：]\s*(.+)", re.IGNORECASE)
_MAX_RATIO_RE = re.compile(
    r"(?i)(?:maximum|max(?:imum)?|最大(?:值|比值)?|ratio|f\s*\(\s*n\s*\)\s*/\s*n)"
    r"[^:\n]{0,80}[:：=]\s*([-+]?\d+(?:\.\d+)?)"
)
_NUMBER_RE = re.compile(r"[-+]?\d+(?:\.\d+)?")
_CONTRADICTION_RE = re.compile(
    r"(?:反例|矛盾|不一致|失败断言|counterexample|contradict|FAIL)",
    re.IGNORECASE,
)


def _scalar(value: str):
    """Return a simple scalar from an answer, or None for compound answers."""
    text = str(value or "")
    numbers = _NUMBER_RE.findall(text)
    if len(numbers) != 1:
        return None
    try:
        return float(numbers[0])
    except ValueError:
        return None


def _bounded(text: str, limit: int = 1000) -> str:
    text = str(text or "").strip()
    return text if len(text) <= limit else text[:limit].rstrip() + "...[truncated]"


def parse_verification_evidence(
    output: dict | None, candidate_answer: str = "", code: str = ""
) -> dict:
    """Add conservative evidence fields without changing executor success semantics."""
    result = dict(output or {})
    stdout = str(result.get("stdout") or "")

    # 低置信答案通道：执行器只认 "最终答案:" 标记；标记缺失但 stdout 明确给出
    # 结论时（"f(2015)=3024"、"both match binomial(2k,k)^2"），把它挖出来作候选。
    # 只在高置信通道为空时启用，且不改变 success 语义。
    if not str(result.get("answer") or "").strip() and stdout:
        mined = mine_stdout_answer(stdout)
        if mined:
            result["answer"] = mined
            result["answer_source"] = "stdout_mined"

    marker = _STATUS_RE.search(stdout)
    marker_status = marker.group(1).upper() if marker else ""
    evidence_match = _EVIDENCE_RE.search(stdout)
    evidence_summary = evidence_match.group(1).strip() if evidence_match else ""

    contradictions = []
    for line in stdout.splitlines():
        if _STATUS_RE.search(line):
            continue
        if _CONTRADICTION_RE.search(line):
            text = line.strip()
            if text and text not in contradictions:
                contradictions.append(text)

    if marker_status == "FAIL":
        if evidence_summary and evidence_summary not in contradictions:
            contradictions.insert(0, evidence_summary)
        elif not contradictions:
            contradictions.append("验证状态: FAIL")

    candidate_value = _scalar(candidate_answer or result.get("answer", ""))
    if candidate_value is not None:
        for match in _MAX_RATIO_RE.finditer(stdout):
            observed = float(match.group(1))
            if observed > candidate_value + 1e-12:
                text = match.group(0).strip()
                if text not in contradictions:
                    contradictions.append(text)

    if contradictions:
        status = "contradict"
        if not evidence_summary:
            evidence_summary = contradictions[0]
    elif marker_status == "PASS":
        # A failed process can leave a partial PASS line behind. Treat that as
        # inconclusive rather than allowing process failure to authorize a match.
        status = "support" if result.get("success") is not False else "inconclusive"
    else:
        status = "inconclusive"
        if not evidence_summary and marker_status == "INCONCLUSIVE":
            evidence_summary = "程序明确声明无法判定。"

    # 反伪造：不做计算却宣称 PASS 的代码，其 support 不构成数学证据。
    # 只降级 support（contradict 的反例本身就是计算产物，不受权威引用污染）。
    authenticity = assess_verification_authenticity(code, stdout) if code else \
        {"fabricated": False, "reasons": []}
    if authenticity["fabricated"] and status == "support":
        status = "inconclusive"
        warning = "；".join(authenticity["reasons"])
        evidence_summary = f"[反伪造] {warning}。原声明不作为验证证据。"

    result.update({
        "evidence_status": status,
        "evidence_summary": _bounded(evidence_summary or stdout),
        "contradictions": contradictions,
        "evidence_marker": bool(marker),
        "authenticity": authenticity,
    })
    return result
