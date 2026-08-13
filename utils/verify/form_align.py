# -*- coding: utf-8 -*-
"""V2 M4 答案形式对齐引擎 —— 攻"数学对但形式不合"失分。

实证（V1 真机 idx=94）：统计推断题，题面问"置信区间长度的一半（0.49）"，
智能体答完整区间 [2.01, 2.99]（数学正确）→ 官方 judger 判 partial。
数学对、形式错，是纯链路可修的失分。

设计：在 coordinator 成稿前做轻量形式检查：
  1. 从题面提取"期望答案形态"（单值/区间/判断/枚举）——零成本正则；
  2. 检查最终答案是否满足该形态；
  3. 错配 → 返回"需重述"信号，由调用方触发一次低成本 LLM 重述
     （~512 token，提示"从已有答案中提取题面要求的量"）。

成本：仅错配触发（~5% 题），每次 ~3s。收益：partial → correct。
"""

from __future__ import annotations

import re

#: 期望单值答案的题面信号（求值/求个数/求半长/求大小等）
_SINGLE_VALUE_RE = re.compile(
    r"(?:求|计算|为|等于|是多少|的值|大小|个数|数量|半长|长度|面积|体积|"
    r"总和|平均值|方差|期望|极限|导数|积分值|特征值|行列式|余数|模长|距离|"
    r"半径|直径|斜率|截距|概率|数值|结果)", re.IGNORECASE)

#: 期望区间/范围答案的题面信号
_INTERVAL_RE = re.compile(
    r"(?:区间|范围|解集|值域|定义域|取值范围|置信区间|满足.*的范围|"
    r"之间的所有|全部.*解)", re.IGNORECASE)

#: 期望判断（是/否/成立）答案的题面信号
_JUDGE_RE = re.compile(
    r"(?:是否|能否|判断|成立吗|对吗|是否成立|有没有|存在.*吗|是不是|"
    r"正确与否)", re.IGNORECASE)

#: 期望枚举（多个值/集合）答案的题面信号。
#: 注意："元素个数/集合大小"问的是个数（单值），不算枚举；
#: 只保留"列出/所有/全部/分别"等强枚举信号（2026-08-12 修正）。
_ENUM_RE = re.compile(
    r"(?:列出|列举|枚举|的所有解|的全部解|共有哪些|分别是|的所有取值|"
    r"的全部取值|全体|所有可能)", re.IGNORECASE)


def expected_form(problem: str) -> str:
    """从题面推断期望答案形态。

    Returns: "single" | "interval" | "judge" | "enum" | "unknown"

    优先级（2026-08-12 修正，idx=94 实证）："置信区间长度的一半"问的是
    半长（单值），不是区间——单值限定词（半长/长度/数值/大小）优先于
    区间/枚举信号；判断信号仍最优先（形态最特殊）。
    """
    text = str(problem or "")
    # 判断信号优先（"是否"类题目答案形态最特殊）
    if _JUDGE_RE.search(text):
        return "judge"
    # 单值限定词优先于区间：问"区间长度/半长/大小"时答案应是单值
    if re.search(r"(?:区间|范围|解集|值域|定义域|置信区间).{0,8}(?:长度|半长|大小|数值|宽度|半径)", text):
        return "single"
    if _INTERVAL_RE.search(text):
        return "interval"
    if _ENUM_RE.search(text):
        return "enum"
    if _SINGLE_VALUE_RE.search(text):
        return "single"
    return "unknown"


def _looks_numeric(s: str) -> bool:
    """粗判字符串是否"看起来是单值"（含数字/表达式/等号右端）。"""
    s = s.strip()
    if not s:
        return False
    if re.search(r"\d|π|pi|e\b|∞|infty", s):
        return True
    # 区间特征
    return False


def _looks_interval(s: str) -> bool:
    return bool(re.search(r"\[.*[,，].*\]|\(.*[,，].*\)|到.*之间", s)) or "[" in s


def _looks_judge(s: str) -> bool:
    # 剥离"结论：/最终答案：/答案："前缀再看判断词（2026-08-12 修正）
    core = re.sub(r"^(?:最终答案|结论|答案|判断|判定)\s*[：:]\s*", "", s.strip())
    head = core.strip().lower()
    return head.startswith(("是", "否", "能", "不能", "存在", "不存在",
                            "成立", "不成立", "yes", "no", "true", "false"))


def check_form_alignment(problem: str, answer: str) -> dict:
    """检查最终答案与题面期望形态是否错配。

    Returns:
      {"aligned": bool, "expected": str, "reason": str}
      aligned=False 时调用方可触发重述修正。
    """
    expected = expected_form(problem)
    answer_text = str(answer or "").strip()
    if expected == "unknown" or not answer_text:
        return {"aligned": True, "expected": expected, "reason": "无法判断"}
    if expected == "judge":
        ok = _looks_judge(answer_text)
        return {"aligned": ok, "expected": expected,
                "reason": "判断题需以是/否/成立开头" if not ok else ""}
    if expected == "interval":
        ok = _looks_interval(answer_text) or _looks_numeric(answer_text)
        return {"aligned": ok, "expected": expected,
                "reason": "区间题期望给出区间或数值" if not ok else ""}
    if expected == "single":
        ok = _looks_numeric(answer_text) and not _looks_interval(answer_text)
        return {"aligned": ok, "expected": expected,
                "reason": "单值题期望给出具体数值而非区间" if not ok else ""}
    # enum
    ok = not _looks_interval(answer_text)
    return {"aligned": ok, "expected": expected,
            "reason": "枚举题期望列出全部值" if not ok else ""}
