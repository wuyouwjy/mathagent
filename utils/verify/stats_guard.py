"""统计推断题检测与收窄采信判断（供 cross_validator 使用）。

实证根因（2026-10-02/03 诊断 idx=28/36）：统计推断 fill 题的数值空，
reasoning 心算易丢失精度（idx=28 的 critical value 心算 3.85 而 Python 算出
3.8549，差 0.0049 超判分容差）或用 2σ 近似（idx=36 的 95.5% 写 z=2.0/2.1
而非 2.0046）。Python 确定性算出的精确值应优先于心算——但前提是 Python
与 reasoning 对题目的理解一致，否则 Python 的"精确"可能建立在错误模型上。

G5-78 复盘的教训：无条件采信 Python（只看 detect_statistical_inference、
不看内容）把 idx=36（硬编码 z=2.1 得 764，比 reasoning 的 693 更离谱）改错。
第一版收窄用了 uses_exact_scipy（检测代码是否调 ppf/isf），但它依赖模型
生成代码的写法——idx=28 第二次跑改用 sympy nsolve 精确求解、代码里没有 ppf，
就被误判为"不精确"而漏采。最终改用数值一致性判据（python_agrees_with_reasoning）：
两个独立答案接近说明建模一致、Python 只是更精确，差远说明至少一方错。
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


def extract_labeled_values(answer: str) -> str:
    """从 "label = value; label = value" 输出提取纯值序列。

    idx=28 的 Python 输出 "test statistic = 1.9102; larger critical value =
    3.8549; conclusion = A" 若原样作为 fill 答案，judge 的 tokens 拆分会把
    "conclusion = A" 归为 na（字母 A 混在英文标签里提取不出），第三空失分。
    这里逐项取 "="/"：" 后的值，拼成 "1.9102; 3.8549; A" 纯值串。
    reasoning 的 "空1: 1.91；空2: 3.85；空3: A" 同样适用。
    """
    parts = re.split(r"[;；\n]", str(answer or ""))
    vals = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        m = re.split(r"[=＝：:]", part)
        val = (m[-1] or "").strip() if len(m) > 1 else part
        if val:
            vals.append(val)
    return "; ".join(vals)


def _numeric_sequence(values: str) -> list[float]:
    """从纯值串提取数值序列（跳过字母/文字项）。"""
    seq = []
    for part in re.split(r"[;；]", str(values or "")):
        part = part.strip()
        if not part:
            continue
        try:
            seq.append(float(part.replace(",", "")))
        except ValueError:
            continue
    return seq


def python_agrees_with_reasoning(py_values: str, rr_values: str, tol: float = 0.05) -> bool:
    """Python 与 reasoning 的数值答案是否彼此接近（理解一致 → 采信更精确的 Python）。

    idx=28：reasoning 心算 3.85，Python 精确 3.8549（差 0.13%）→ 采信 Python；
    idx=36：reasoning 693，Python 硬编码 z=2.1 得 764（差 10%）→ 不采信。
    两个独立答案接近说明对题目建模一致、Python 只是数值更精确；差远说明至少
    一方建错模型，此时 Python 不比 reasoning 更可信，保守回退 reasoning。
    """
    py_nums = _numeric_sequence(py_values)
    rr_nums = _numeric_sequence(rr_values)
    if not py_nums or not rr_nums or len(py_nums) != len(rr_nums):
        return False
    for p, r in zip(py_nums, rr_nums):
        if r == 0:
            if abs(p) > tol:
                return False
        elif abs(p - r) > tol * max(1.0, abs(r)):
            return False
    return True


def _decimal_places(num: str) -> int:
    """数值字符串的小数位数（无小数点返回 0）。"""
    m = re.search(r"\.(\d+)", str(num))
    return len(m.group(1)) if m else 0


def python_more_precise(py_values: str, rr_values: str) -> bool:
    """Python 数值的小数位是否严格多于 reasoning（至少一处更多、无处更少）。

    idx=28：Python 3.8549（4 位）vs reasoning 3.85（2 位）→ 采信 Python；
    idx=31：Python 用 %.2f 打印 19.70（2 位）vs reasoning 19.77（2 位）→ 精度
    相同，且 Python 其实建错模型（t 分布而非 z），此时采信 Python 会把 19.77
    的正确 reasoning 换成 19.70 的错答，故不采信。
    单看"数值接近"无法区分 idx=28/31（都接近），但"Python 是否真的更精确地
    求解"通常体现在有效位数上：精确求解会保留更多小数位，粗糙打印则与
    reasoning 一样只有 2 位。
    """
    py_parts = [p for p in re.split(r"[;；]", str(py_values or "")) if p.strip()]
    rr_parts = [p for p in re.split(r"[;；]", str(rr_values or "")) if p.strip()]
    if not py_parts or len(py_parts) != len(rr_parts):
        return False
    more = False
    for p, r in zip(py_parts, rr_parts):
        dp, dr = _decimal_places(p), _decimal_places(r)
        if dp < dr:
            return False
        if dp > dr:
            more = True
    return more
