"""组合计数枚举对照守护（VeritasMath，冲刺满分 M6）。

实证根因（ultra_112 真机压测 idx=40）：组合计数是 LLM 最弱项——模型给出
一个"看起来对"的闭式（1120），但任何小规模实例都无法验证时它就直接采信。
而计数题的确定性出路恰恰是小规模可机器枚举：把题面规模换成 n=2,3,4
暴力枚举，与候选公式逐点比对，不符即说明公式错。

本模块把"提示层自觉"升级为"确定性防线"：
- detect：检出计数题（多少个/几种/选法/方案数/排列组合等）；
- prompt_clause：注入强制条款——必须先小规模枚举对照，禁止直接写闭式；
- code_has_enumeration：静态核查生成代码是否含枚举循环（for/range/itertools），
  无枚举则打回修复（不执行——执行一个只写闭式的代码只会产出"看起来更可信"的错值）。
"""

from __future__ import annotations

import re

#: 计数题信号（题面询问数量/方案数/选法）
_COUNTING_RE = re.compile(
    r"多少\s*[个种对组项方式方法]|几种|几组|几个|多少种|多少组|"
    r"共有多少|总数|个数|数目|种数|方案数|选法|排法|走法|分法|取法|"
    r"排列数|组合数|计数|枚举|number of|how many|count the",
    re.IGNORECASE,
)

#: 代码内枚举证据：显式循环 / 范围 / 组合枚举库
_ENUM_CODE_RE = re.compile(
    r"\bfor\s+\w+\s+in\b|\brange\s*\(|\bwhile\b|itertools|"
    r"combinations\s*\(|permutations\s*\(|product\s*\(|combinations_with_replacement|"
    r" brute|枚举|暴力|穷举",
    re.IGNORECASE,
)

#: 反证信号：只调用闭式/阶乘/组合数函数而无任何循环——没做小规模对照
_CLOSED_FORM_RE = re.compile(
    r"\b(?:factorial|comb|perm|binomial|gamma)\s*\(", re.IGNORECASE)


def detect_counting(problem: str) -> bool:
    """是否计数题。"""
    return bool(_COUNTING_RE.search(str(problem or "")))


def prompt_clause(problem: str) -> str:
    """命中计数题时返回强制枚举对照条款。"""
    if not detect_counting(problem):
        return ""
    return (
        "\n【计数题枚举对照强制条款】本题是计数题。组合计数的闭式公式极易错"
        "（重数/漏数/边界），严禁直接写闭式输出。必须："
        "(1) 先把题面规模缩到最小可枚举实例（如 n=2,3,4 或网格≤4×4），"
        "用 for/range/itertools 暴力枚举出精确计数；"
        "(2) 再给出你的候选公式/递推，并在小规模上逐点 assert 两者一致；"
        "(3) 至少 2 个小规模点全部吻合才允许外推到题面规模；任何一点不吻合，"
        "说明公式有误，必须修正后重新对照。"
        "代码中打印小规模枚举值与公式值的对照表，再打印最终答案。"
    )


def code_has_enumeration(code: str) -> bool:
    """静态核查：计数题代码是否含枚举对照证据。

    有枚举循环/itertools → True；只调闭式函数（factorial/comb/binomial）
    而无任何循环 → False（没做小规模对照）。
    """
    code = str(code or "")
    if not code.strip():
        return False
    if _ENUM_CODE_RE.search(code):
        return True
    # 只写闭式、无循环 → 未对照
    if _CLOSED_FORM_RE.search(code):
        return False
    # 既无循环也无闭式（可能是纯 print）→ 不算枚举
    return False
