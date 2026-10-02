"""统计推断题检测（供 cross_validator 采信判断用）。

实证根因（2026-10-02 50 题诊断 idx=28/36）：统计推断 fill 题的数值空，
reasoning 心算易丢失精度（idx=28 的 critical value 心算 3.85 而 Python 算出
3.8549，差 0.0049 超判分容差）或用 2σ 近似（idx=36 的 95.5% 写 z=2.0 而非
2.0046）。Python 用 scipy/sympy 确定性算出的精确值应优先于心算。

本模块只提供 `detect_statistical_inference`，供 cross_validator 在客观题
路径上判断"该题是统计推断 fill 题、Python 成功时应采信 Python 数值答案"。
（曾尝试 prompt 注入"强制 scipy 精确分位数"条款救 idx=36 的知识盲区，
但 intern-s2 对 95.5% 的条件反射就是 z=2.0，prompt 层突破不了，已弃用。）
"""

from __future__ import annotations

import re

#: 统计推断信号（假设检验/置信区间/样本量/分位数）
_STATS_RE = re.compile(
    r"significance\s+level|test\s+statistic|critical\s+value|confidence\s+interval|"
    r"p[- ]?value|null\s+hypothesis|hypothesis\s+test|sample\s+size|"
    r"population\s+proportion|population\s+mean|margin\s+of\s+error|"
    r"standard\s+deviation|normal\s+distribution|z[- ]?(score|value)|"
    r"t[- ]?(test|distribution|statistic)|f[- ]?test|chi[- ]?square|"
    r"显著性水平|检验统计量|临界值|置信区间|置信水平|假设检验|样本量|"
    r"总体比例|总体均值|标准差|正态分布",
    re.IGNORECASE,
)


def detect_statistical_inference(problem: str) -> bool:
    """是否统计推断/假设检验题（需要精确分位数/临界值）。"""
    return bool(_STATS_RE.search(str(problem or "")))
