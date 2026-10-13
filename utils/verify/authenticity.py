"""验证代码反伪造检测（评委建议 2，针对失分模式 C）。

评委报告定性为"认识论上最危险的失败模式"：idx 19、28、45、66 的验证代码不做
任何计算，直接以注释/打印断言结论——"基于已知竞赛结果验证…PASS"、"已知 n=5
存在构造"、"该结论来自组合极值理论"——然后以 evidence=support 通过交叉验证并
被仲裁锁定。验证器退化成了结论的回声。

检测思路（纯静态、保守）：

1. **计算实质度**：代码里是否存在真实计算——循环/推导式/递归、sympy·itertools
   等求解调用、对变量的算术运算。没有计算而打印 PASS/FAIL 的，证据不可信。
2. **权威引用断言**：注释或打印字符串里出现"已知/经分析/竞赛结果/well-known/
   known result"且伴随结论数值——把外部记忆当验证。
3. **无条件 PASS**：``print("验证状态: PASS")`` 的实参是字面量而非依赖任何
   分支/比较的变量，代码里也没有任何 assert/if 比较。

被判伪造的证据一律降级为 inconclusive，且不得作为仲裁锁定依据（调用方负责）。
判定宁可放过：只要代码含有实质计算就不算伪造——误伤真实验证会废掉整条
Python 分支，损失比放过一段回声大得多。
"""

from __future__ import annotations

import re


#: 实质计算信号：任何一个出现即认为代码"确实算了点什么"。
_COMPUTE_RE = re.compile(
    r"(?m)^\s*(?:for|while)\s|"                      # 循环
    r"\[[^\]]*\bfor\b[^\]]*\]|"                      # 推导式
    r"\b(?:solve|solveset|nsolve|dsolve|simplify|expand|factor|gcd|lcm|"
    r"binomial|factorial|summation|integrate|diff|limit|det|rref|nullspace|"
    r"eig|jordan_form|diagonalize|isprime|factorint|totient|"
    r"permutations|combinations|product|accumulate|"
    r"minimize|maximize|linprog|fsolve|brentq|"
    r"sum|max|min|sorted|range)\s*\(|"               # 求解/枚举/聚合调用
    r"\bdef\s+\w+\s*\([^)]*\)\s*:"                   # 定义了函数（递归/记忆化）
)

#: 对变量的真实算术（排除纯字面量算式 "1+1"）。
_VAR_ARITH_RE = re.compile(r"[A-Za-z_]\w*\s*[*/+\-%]{1,2}\s*[\w(]|[\w)]\s*\*\*\s*\w")

#: 比较/断言：验证结论至少要有一次比较。
_ASSERT_RE = re.compile(r"\bassert\b|==|!=|<=|>=|\bis\s+not\b")

#: 权威引用式断言（注释与字符串里）。
_AUTHORITY_RE = re.compile(
    r"已知(?:结论|结果|竞赛|存在)|经分析|由.{0,12}(?:定理|理论|结果)可?(?:知|得)|"
    r"竞赛结果|标准答案|参考答案|(?i:well[- ]known|known\s+result|it\s+is\s+known|"
    r"by\s+the\s+known|from\s+the\s+literature)"
)

#: PASS 的打印形态：实参是字面量（伪造嫌疑）还是变量（正常）。
_LITERAL_PASS_RE = re.compile(
    r"""print\s*\(\s*["']验证状态\s*[:：]?\s*(?:PASS|通过)["']|"""
    r"""print\s*\(\s*["']验证状态["']\s*,\s*["'](?:PASS|通过)["']"""
)
_STATUS_MARKER_RE = re.compile(r"验证状态")


def _strip_comments_and_strings(code: str) -> tuple[str, str]:
    """(可执行骨架, 注释+字符串文本)。粗粒度扫描即可，不求完美解析。"""
    comments: list[str] = []

    def _grab_comment(match: re.Match) -> str:
        comments.append(match.group(0))
        return ""

    text = str(code or "")
    # 字符串字面量（含三引号）
    strings = re.findall(r'"""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\'|"[^"\n]*"|\'[^\'\n]*\'', text)
    skeleton = re.sub(r'"""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\'|"[^"\n]*"|\'[^\'\n]*\'', '""', text)
    skeleton = re.sub(r"#[^\n]*", _grab_comment, skeleton)
    return skeleton, "\n".join(comments + strings)


def assess_verification_authenticity(code: str, stdout: str = "") -> dict:
    """静态评估验证代码的可信度。

    返回 {"fabricated": bool, "reasons": [str, ...]}。fabricated=True 表示
    该代码的 PASS/support 证据不可作为数学正确性的依据。
    """
    text = str(code or "")
    if not text.strip():
        return {"fabricated": False, "reasons": []}

    skeleton, prose = _strip_comments_and_strings(text)
    has_compute = bool(_COMPUTE_RE.search(skeleton)) or bool(_VAR_ARITH_RE.search(skeleton))
    has_assert = bool(_ASSERT_RE.search(skeleton))
    claims_pass = bool(_LITERAL_PASS_RE.search(text)) or (
        "PASS" in str(stdout or "") and _STATUS_MARKER_RE.search(str(stdout or "")) is not None
    )
    cites_authority = bool(_AUTHORITY_RE.search(prose))

    reasons: list[str] = []
    if claims_pass and not has_compute:
        reasons.append("代码未含循环/求解/枚举等实质计算却宣称验证通过")
    if claims_pass and has_compute and not has_assert and cites_authority:
        reasons.append("验证结论依赖注释中的已知结论引用而非代码比较")
    if cites_authority and not has_compute:
        reasons.append("以'已知/竞赛结果'等权威引用代替计算")
    # 字面量 PASS + 无任何比较：结论与代码执行结果无关。
    if _LITERAL_PASS_RE.search(text) and not has_assert and not has_compute:
        if "代码未含循环/求解/枚举等实质计算却宣称验证通过" not in reasons:
            reasons.append("验证状态为硬编码字面量，与计算结果无关")

    return {"fabricated": bool(reasons), "reasons": reasons}
