"""验证路由（VeritasMath，冲刺满分治本机制）。

实证根因（ultra_112 真机 idx=13/40）：需要实算的填空题（含绝对值的导数、
组合计数）被判为客观题走快速路径——**跳过 Python 验证，单采样定生死**。
而这两类恰恰是 LLM 最容易算错的题型，最缺机器验证。

设计：把填空题细分——
- 纯概念填空（填术语/定义/定理名）：保持快速路径，零成本；
- 实算填空（要算数值/表达式/计数/最值）：升级为完整双路验证
  （reasoning + python 独立求解 + 交叉验证 + 冲突时 playoff），
  让机器计算给第二证据，不再单采样。

判定用"纯概念信号"反向排除：只要题面是"是指/称为/定义/术语/哪本教材概念"
这类，才留在快速路径；其余填空一律实算双路。宁可多算一道，不放过算错一道。
"""

from __future__ import annotations

import re

#: 纯概念填空信号（填术语/定义/名称，无需计算）
_CONCEPT_RE = re.compile(
    r"是指|是指什么|称为|叫做|定义为|的定义|术语|概念是|定理名|性质是|"
    r"哪个定理|哪个性质|哪本|is called|is defined as|the name of",
    re.IGNORECASE,
)


def needs_python_verify(problem: str, question_mode: str) -> bool:
    """该题是否需要 Python 验证第二证据（即使它是客观题）。

    只对填空题生效：纯概念填空返回 False（保持快速路径），
    实算填空返回 True（升级完整双路验证）。其他题型维持原逻辑（非客观题
    本来就跑双路，无需此函数介入）。
    """
    if question_mode != "fill":
        return False
    if not str(problem or "").strip():
        return False
    return not _CONCEPT_RE.search(problem)
