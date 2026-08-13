"""推导矛盾自检（VeritasMath，移植自启元 MathAgent 思路重写）。

推导链中同一变量出现 ≥2 个不同数值（"第1步得 x=3" 与 "第4步得 x=5" 并存）
说明中间步骤自相矛盾——这类解答即使最终答案"碰巧"对，推理过程分也会丢，
且最终答案本身大概率错（错的推导链碰巧对是小概率）。

纯正则零 API。不误杀（每条都经启元实测校准）：
- 数值归一：x=3 ≡ x=3.0 ≡ x=3/1（Fraction 归一后才比较，字符串不同不误报）；
- 排除假设句/疑问/不等式（"若 x=3""令 a=1""x≠3"）；
- 排除多解/分段（"x=2 或 x=-2""a=1 和 b=2"）；
- 排除同行枚举/解集（"x=1, x=2"——同一行同变量多次赋值不判矛盾）。
"""

from __future__ import annotations

import re
from fractions import Fraction
from typing import Optional

#: 推导行信号：含推导词才算"链内断言"
_DERIVE_CUE_RE = re.compile(r"步|得|则|因此|所以|代入|解得|计算得|于是|从而|推出|故")

#: 排除：假设/令/疑问/不等式/约等
_EXCLUDE_RE = re.compile(r"若\s*[A-Za-z]\s*=|假设|令\s*[A-Za-z]\s*=|≠|≈|≤|≥|<|>")

#: 排除：多解/分段连接词
_MULTISOL_RE = re.compile(r"\s(?:或|和|且|与)\s")

#: 变量赋值（x=3 / x=3.0 / x=3/2 / x=-1）
_ASSIGN_RE = re.compile(r"([A-Za-z])\s*=\s*(-?\d+(?:\.\d+)?(?:\s*/\s*-?\d+)?)")

#: 等号后的合法收尾（排除 x=3y / x=3时 这类续写）
_TAIL_OK = set("，,。．；;\n)） ")


def _norm_val(v: str) -> str:
    try:
        return str(Fraction(v.replace(" ", "")))
    except Exception:  # noqa: BLE001
        return v.replace(" ", "")


def detect_derivation_conflict(text: str) -> Optional[str]:
    """检测推导文本中的变量赋值矛盾。返回矛盾描述或 None。"""
    if not text:
        return None
    vals: dict[str, set] = {}
    for line in re.split(r"[\n；;]", str(text)):
        line = line.strip()
        if not line or not _DERIVE_CUE_RE.search(line):
            continue
        if _EXCLUDE_RE.search(line) or _MULTISOL_RE.search(line):
            continue
        for m in _ASSIGN_RE.finditer(line):
            var, val = m.group(1), m.group(2)
            after = line[m.end():]
            if after and after[0] not in _TAIL_OK:
                continue
            # 同行同变量多次赋值 = 解集/枚举（x=1, x=2），不判矛盾
            if len(re.findall(re.escape(var) + r"\s*=", line)) > 1:
                continue
            vals.setdefault(var, set()).add(_norm_val(val))
    conflicts = [f"{var} 同时取值 {'/'.join(sorted(v))}"
                 for var, v in vals.items() if len(v) >= 2]
    return "；".join(conflicts) if conflicts else None
