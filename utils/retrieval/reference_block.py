"""题库参考示例区块的唯一构造入口。

推理节点与 Python 节点各自内联拼装过同一段文本，两份实现的截断长度不同、
措辞也会各自漂移。检索条数（`db_retrieval_top_k`）与注入契约"两条全部同时进
两个子代理"必须在一处可验证，故收敛到这里；调用方只保留各自的截断额度。

2026-08-20：区块必须自带**反锚定**说明。检索是向量近邻，命中的常常是"看起来
几乎一样、答案却不同"的近似题，而这正是评测中最贵的一类失分：

* idx 48（黑板上 1997 个 1 的取数博弈）：题库以 0.773 命中 ISL 2020 的同题型
  （2020 个 1、B 可自由选择），其解法用二进制数字和 S₂(n)。代理照搬得
  S₂(1997)=8，而本题因为**个数是奇数**且**硬币剥夺了 B 的选择权**，正解是 999。
* idx 17（x²+y²+z²=xy³+yz³+zx³=3 的实数解个数）：题库以 0.814 命中 USAMO 1973
  的 x+y+z=x²+y²+z²=x³+y³+z³=3（答案只有对称解 1,1,1），代理据此只数出对称解
  得 2，而本题的非对称轨道使正解为 8。

两次都不是"检索没找到"，而是"找到了近似题并把它的结论当成本题的结论"。因此
区块除了给出示例，还必须（1）显式声明结论不可迁移，(2) 把两边题面的数值差异
直接摆出来，让模型无法忽略参数已经变了这件事。
"""

from __future__ import annotations

import re
from typing import Any, Dict, List

_HEADER = "\n\n参考示例（来自数学竞赛题库的相似题目与解答）：\n"

#: 反锚定说明。放在示例**之前**——写在后面时模型往往已经先读完解答并锚定了结论。
_ANTI_ANCHOR_NOTE = """
⚠️ 这些是按相似度检索出来的**近似题，不是本题**。相似度高只说明措辞接近，
不说明结论相同；把近似题的答案搬过来是本项目已确认的头号失分来源。使用规则：

1. 先逐项核对差异：参数数值（个数/上界/模数）、**奇偶性**、谁做选择、目标是
   最大化还是最小化、约束方向（≤ 还是 <、"所有解"还是"一个解"）。
2. 只要有一项不同，示例的**结论就不可迁移**——它的答案不是本题的答案。此时最多
   借用它的**方法**，并且必须在本题自己的参数下从头重算，再把结果代回本题题面验证。
3. 核对后若不能确认两题严格同构，就完全忽略示例，独立求解。宁可自己算，也不要
   抄一个参数不同的结论。
"""

#: 题面里有判别力的整数字面量：跳过 0/1 这类到处都是的数，也跳过 LaTeX 命令里
#: 的上下标数字（\\sqrt[3]、x^{2}），只留下真正描述规模的参数。
_INT_RE = re.compile(r"(?<![\\^_{\w])(\d{2,})(?![}\w])")


def _scale_numbers(text: str) -> list[int]:
    seen: list[int] = []
    for match in _INT_RE.finditer(str(text or "")):
        value = int(match.group(1))
        if value not in seen:
            seen.append(value)
    return seen


def _numeric_diff_line(problem: str, example_problem: str) -> str:
    """把两边题面的规模参数差异摆出来；无从比较时返回空串。"""
    ours = _scale_numbers(problem)
    theirs = _scale_numbers(example_problem)
    if not ours or not theirs:
        return ""
    only_ours = [n for n in ours if n not in theirs][:6]
    only_theirs = [n for n in theirs if n not in ours][:6]
    if not only_ours and not only_theirs:
        return ""
    parts = []
    if only_ours:
        parity = "奇" if only_ours[0] % 2 else "偶"
        parts.append(f"本题独有 {only_ours}（首个为{parity}数）")
    if only_theirs:
        parity = "奇" if only_theirs[0] % 2 else "偶"
        parts.append(f"示例独有 {only_theirs}（首个为{parity}数）")
    return ("**⚠ 参数差异**：" + "；".join(parts)
            + "。参数不同则结论不同，必须在本题参数下重算。\n")


def build_reference_block(
    examples: List[Dict[str, Any]] | None,
    problem_chars: int,
    solution_chars: int,
    problem: str = "",
) -> str:
    """把检索到的每一条相似题拼成参考区块；无检索结果时返回空串。

    Args:
        examples: `retrieved_examples`，按相似度降序。全部注入，不再二次筛选。
        problem_chars: 每条题面的截断长度。
        solution_chars: 每条解答的截断长度。
        problem: 本题题面。给出时逐条附上与示例的规模参数差异（反锚定）。
    """
    usable = [ex for ex in (examples or []) if isinstance(ex, dict)]
    if not usable:
        return ""
    parts = [_HEADER, _ANTI_ANCHOR_NOTE]
    for i, example in enumerate(usable, 1):
        try:
            similarity = float(example.get("similarity") or 0.0)
        except (TypeError, ValueError):
            similarity = 0.0
        example_problem = str(example.get("problem") or "")
        parts.append(f"\n### 示例 {i} (相似度: {similarity:.3f}，**不是本题**)\n")
        diff = _numeric_diff_line(problem, example_problem) if problem else ""
        if diff:
            parts.append(diff)
        parts.append(f"**题目：**\n{example_problem[:problem_chars]}\n\n")
        parts.append(f"**解答：**\n{str(example.get('solution') or '')[:solution_chars]}\n")
        if i < len(usable):
            parts.append("\n---\n")
    return "".join(parts)
