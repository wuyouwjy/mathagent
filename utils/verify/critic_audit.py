"""过程审计解析器（VeritasMath）：把 Critic 的 JSON 判定解析为路由决策。

Critic 是"只审计、不改写"的节点：LLM 产出结构化判定（complete / missing /
calc_checks / verdict），本模块负责：
- 从 prefill 片段或普通回复中稳健解析 JSON（复用分类器同款的容错策略）；
- 把判定映射为路由动作：pass → coordinator；incomplete/calc_error 且可负担
  → reconciliation（携带定向修复提示）；否则 → coordinator（带缺口标记）。
- 与确定性契约（answer_contract）合并：两边都报告缺失时取并集，任何一边
  能证明缺失就按缺失处理（宁可多修一次，不放行残缺答案）。

LLM 判定是采样判断，会失手；所以 LLM 说 pass 而确定性契约说缺失时，
以确定性契约为准（保守方向：多一次修复提示不会丢分，放行残缺答案会）。
"""

from __future__ import annotations

import json
import re

_VALID_VERDICTS = {"pass", "incomplete", "calc_error"}


def _parse_json_object(text: str) -> dict | None:
    """从可能带 CoT 包装/种子前缀的文本中解析第一个完整 JSON 对象。"""
    text = (text or "").strip()
    if not text:
        return None
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        pass
    start = text.find("{")
    while start != -1:
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        parsed = json.loads(text[start:i + 1])
                        return parsed if isinstance(parsed, dict) else None
                    except Exception:
                        break
        start = text.find("{", start + 1)
    return None


def parse_critic_verdict(raw: str) -> dict | None:
    """解析 Critic 回复为标准判定 dict；解析失败返回 None。

    标准形态：{"complete": bool, "missing": [...], "calc_checks": [...],
    "verdict": "pass|incomplete|calc_error"}
    prefill 回复以 {"complete": 开头（种子已给出），json.loads 可直接解析；
    容错路径处理模型在中途插入说明文字的情况。
    """
    parsed = _parse_json_object(raw)
    if parsed is None:
        return None
    verdict = str(parsed.get("verdict") or "").strip().lower()
    complete = parsed.get("complete")
    missing = parsed.get("missing")
    calc_checks = parsed.get("calc_checks")
    if verdict not in _VALID_VERDICTS:
        # 从 complete/missing 推断 verdict，容忍模型漏写字段。
        if complete is True:
            verdict = "pass"
        elif isinstance(missing, list) and missing:
            verdict = "incomplete"
        else:
            return None
    return {
        "complete": bool(complete) if isinstance(complete, bool) else verdict == "pass",
        "missing": [str(m)[:200] for m in missing][:8] if isinstance(missing, list) else [],
        "calc_checks": calc_checks if isinstance(calc_checks, list) else [],
        "verdict": verdict,
    }


def merge_with_deterministic(llm_verdict: dict | None, deterministic_missing: list[str]) -> dict:
    """LLM 判定与确定性契约缺失列表合并，返回最终审计结论。

    方向是保守的：任一方报缺即缺；LLM 报 calc_error 时即使契约无意见也成立
    （契约看不到计算错误）。
    """
    llm_verdict = llm_verdict or {}
    llm_missing = list(llm_verdict.get("missing") or [])
    det_missing = [str(m) for m in (deterministic_missing or [])]
    merged_missing = list(dict.fromkeys(det_missing + llm_missing))[:10]
    verdict = llm_verdict.get("verdict")
    if verdict == "calc_error":
        final = "calc_error"
    elif merged_missing:
        final = "incomplete"
    elif verdict == "pass" or (llm_verdict and not merged_missing):
        final = "pass"
    else:
        # LLM 判定不可用且契约无缺失：不制造阻塞，放行。
        final = "pass"
    return {
        "verdict": final,
        "missing": merged_missing,
        "calc_checks": llm_verdict.get("calc_checks") or [],
        "llm_available": bool(llm_verdict),
    }


def build_repair_hint(merged: dict, answer: str) -> str:
    """把审计缺口转成给 solving 子图的定向修复提示。"""
    parts = ["上一次解答经过程审计未通过。"]
    missing = merged.get("missing") or []
    if missing:
        parts.append("缺失交付物（必须逐项补齐，不得只补其一）："
                     + "；".join(missing[:6]) + "。")
    bad_checks = [c for c in (merged.get("calc_checks") or [])
                  if isinstance(c, dict) and c.get("ok") is False][:3]
    if bad_checks:
        notes = "；".join(f"{c.get('check', '?')}（{c.get('note', '')[:80]}）" for c in bad_checks)
        parts.append(f"抽核发现计算错误：{notes}。请重做对应步骤。")
    current = str(answer or "").strip()
    if current:
        parts.append(f"当前待修复答案：{current[:600]}")
    parts.append("请保持正确部分不变，只针对上述缺口补充推导；最终答案必须逐项覆盖题面全部问项。")
    return "\n".join(parts)
