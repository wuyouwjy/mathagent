"""模结构守护（VeritasMath）：F_2 / Z_m / 模运算语境的确定性防线。

评委报告 idx 7 的失败形态：函数 f: Q → F_2 的六个取值被按普通整数相加得 3，
而值域是二元域，正确聚合必须模 2（答案 1）。这类错误的特点：
- 推理提示里写"注意模结构"没用——模型在最终求和时仍会滑回整数算术；
- 只能靠两道确定性防线：(a) 生成代码前把"结构内聚合"写进强制条款；
  (b) 生成代码后静态核查聚合确实发生在模结构内，缺失则打回修复。

检出是保守的：只在意图信号（值域/运算域明确为有限结构）出现时命中，
避免给普通实数题注入无关条款增加提示负担。
"""

from __future__ import annotations

import re

# 意图信号：值域/运算域被题面明确限定为有限结构。
_MODULUS_RE = re.compile(
    r"(\\mathbb\{F\}_?\{?2|F_2|GF\(2\)|二元域|二元素域|模\s*2|mod\s*2|"
    r"\\mathbb\{Z\}\s*/|Z/mZ|Z_m|模\s*m|模\s*n|模\s*p|模运算|同余|"
    r"\\pmod|在\s*F_2\s*中|取值于\s*F_2|值域.{0,12}F_2)",
    re.IGNORECASE,
)

# 聚合动作信号：求和/计数/合并等需要在结构内完成的最终动作。
_AGGREGATE_RE = re.compile(
    r"(求和|之和|总和|相加|合计|\\sum|\\sum_|sum_|合计值|共有|计数|总数|"
    r"多少种|多少个|number of|total)",
    re.IGNORECASE,
)

# 代码内"模结构内聚合"的静态证据：显式取模 / GF 域 / 位异或（F_2 加法即 XOR）。
_MOD_CODE_RE = re.compile(
    r"(%\s*2\b|%\s*m\b|%\s*n\b|%\s*p\b|mod\b|Mod\(|GF\(|galois|\^=|\bxor\b|"
    r"functools\.reduce\(.*xor)",
    re.IGNORECASE,
)


def detect_modular_context(problem: str) -> dict:
    """检测题面是否含模结构聚合语境。返回 {"hit": bool, "cues": [...]}。

    需要"结构信号"与"聚合信号"同时命中：只说 F_2 而无求和动作的题
    （如"证明该映射是 F_2 线性的"）不触发聚合守护。
    """
    text = str(problem or "")
    structure_hits = [m.group(0) for m in _MODULUS_RE.finditer(text)][:4]
    if not structure_hits:
        return {"hit": False, "cues": []}
    aggregate_hits = [m.group(0) for m in _AGGREGATE_RE.finditer(text)][:4]
    if not aggregate_hits:
        return {"hit": False, "cues": []}
    return {"hit": True, "cues": structure_hits + aggregate_hits}


def prompt_clause(problem: str) -> str:
    """命中时返回注入 Python/推理提示的强制条款；未命中返回 ""。

    条款只约束最终聚合动作，不规定中间计算——中间步骤用普通整数再累加
    是合法的，最后一步必须在结构内完成。
    """
    guard = detect_modular_context(problem)
    if not guard["hit"]:
        return ""
    return (
        "\n【模结构强制条款】本题值域/运算域含有限结构（命中信号："
        + "、".join(guard["cues"][:3])
        + "）。所有中间量可以按普通整数计算，但最终求和/计数/合并必须在该结构内完成："
        "F_2 中 1+1=0（等价于 XOR / % 2），Z_m 中取 % m。"
        "代码必须显式写出取模/异或操作（如 total % 2），并在打印最终答案前"
        '用一行 print("结构核验:", total % 2) 展示模内聚合结果；'
        "禁止把结构中的元素按普通整数直接相加后输出。"
    )


def code_complies(code: str) -> bool:
    """静态核查：生成代码是否含模结构内聚合证据。"""
    return bool(_MOD_CODE_RE.search(code or ""))
