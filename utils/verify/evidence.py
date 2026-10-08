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
#: 求解漏解/未找到的表述——Python 自报「解集为空/未筛/未找到」，是求解无能，不是
#: 找到了证伪候选的具体反例。这种 FAIL 不得升级为 contradict（idx 16 事故：fsolve
#: 数值扫描漏 6 个非对称解，自报「解集=[]」「未筛」FAIL，被误当确定性反例覆盖
#: reasoning 消元得 8 的正确答案）。
_MISSED_SOLUTION_RE = re.compile(
    r"(?:not\s+found|no\s+solution|none\s+found|0\s+solutions?|"
    r"未找到|未发现|没找到|未筛|漏解|找不到|"
    r"解集\s*[:：=]\s*\[\]|解集为空|"
    r"solutions?\s*[:：=]\s*\[\]|"
    r"search\s+range)",
    re.IGNORECASE,
)
#: 确定性反例值信号——证据里出现这些表述，说明 Python 找到了具体冲突/反例（而非只是
#: 「没找到」）。出现任一信号即认为存在确定性反驳，不做漏解降级。
_CONCRETE_COUNTEREXAMPLE_RE = re.compile(
    r"(?:counterexample|violations?|mismatch|match\s*=\s*False|"
    r"fails?\s+at|fail\s+at|computed\s*=|result\s*:|expected\s*:|"
    r"predicted\s*=|actual\s*=|代入|当\s*\w+\s*=)",
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


def _is_missed_solution_fail(
    evidence_summary: str, contradictions: list[str], has_ratio_refutation: bool = False
) -> bool:
    """FAIL 证据是否只是「求解漏解/未找到」而非确定性反例。

    确定性反例三要素（满足任一即非漏解）：
    1. has_ratio_refutation：_MAX_RATIO_RE 找到 observed > candidate 的数值反例；
    2. 证据含具体反例值信号（_CONCRETE_COUNTEREXAMPLE_RE）；
    3. 证据里没有漏解信号（_MISSED_SOLUTION_RE）。
    仅当「有漏解信号 且 无上述任何确定性反例信号」时才判为漏解 FAIL。
    """
    texts = [str(t) for t in [evidence_summary] + list(contradictions) if t and str(t).strip()]
    if not texts or has_ratio_refutation:
        return False
    joined = "\n".join(texts)
    if not _MISSED_SOLUTION_RE.search(joined):
        return False
    if _CONCRETE_COUNTEREXAMPLE_RE.search(joined):
        return False
    return True


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
    has_ratio_refutation = False
    if candidate_value is not None:
        for match in _MAX_RATIO_RE.finditer(stdout):
            observed = float(match.group(1))
            if observed > candidate_value + 1e-12:
                text = match.group(0).strip()
                if text not in contradictions:
                    contradictions.append(text)
                has_ratio_refutation = True

    if contradictions:
        # 2026-10-08 idx 16：Python 求解漏解（fsolve 数值扫描漏 6 个非对称解）时自报
        # 「验证状态: FAIL」+「验证证据: 解集=[]/未筛」，被上面的 marker_status==FAIL
        # 分支升级成 contradict，进而被 _evidence_override 采信覆盖 reasoning 消元得 8
        # 的正确答案。判别边界：确定性反例必带具体反例值（Counterexample/Violations/
        # Mismatch/FAIL at .../result...expected...）或 _MAX_RATIO_RE 数值反例；而
        # 「解集=[]/未筛/未找到/Not found/0 solutions」只是求解无能（漏解），不是证伪。
        # 后者降级 inconclusive，复用已修好的「inconclusive 弱证据不得覆盖 reasoning」链。
        if _is_missed_solution_fail(evidence_summary, contradictions, has_ratio_refutation):
            status = "inconclusive"
            if not evidence_summary:
                evidence_summary = "程序求解未得到完整解集（可能漏解），不构成反驳证据。"
        else:
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
    # 降级 support（contradict 的反例本身就是计算产物，不受权威引用污染）；
    # 且「无实质计算」的伪造代码 print 出的数字本身也是伪造产物，一并作废，
    # 不得进入候选池被 playoff 采信（idx 7 事故：伪造 388.5 覆盖正确 603729）。
    authenticity = assess_verification_authenticity(code, stdout) if code else \
        {"fabricated": False, "reasons": [], "has_compute": False}
    if authenticity["fabricated"]:
        if status == "support":
            status = "inconclusive"
            warning = "；".join(authenticity["reasons"])
            evidence_summary = f"[反伪造] {warning}。原声明不作为验证证据。"
        if not authenticity.get("has_compute", False):
            result["answer"] = ""
            result["answer_source"] = "fabricated_suppressed"

    result.update({
        "evidence_status": status,
        "evidence_summary": _bounded(evidence_summary or stdout),
        "contradictions": contradictions,
        "evidence_marker": bool(marker),
        "authenticity": authenticity,
    })
    return result
