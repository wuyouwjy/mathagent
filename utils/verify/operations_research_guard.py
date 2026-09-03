"""运筹学确定性求解守护（A9）：线性规划/最优化题的求解器范式注入。

offline-eval-diagnosis 实证：运筹学 3/3 全错（零命中）——不是"偶尔错"，而是系统
性缺对口求解范式。通用 PYTHON_PROMPT 只教"小规模枚举对照/极值双构造"，但运筹学
计算题（LP/非线性优化/运输指派）有现成的确定性求解器：scipy.optimize.linprog
（线性规划）、scipy.optimize.minimize（非线性）、scipy.optimize.milp（整数规划）。
模型不知道用它们，而是手算单纯形/拉格朗日/KKT——手算正是算错的根源。

本模块仿照 modular_guard / counting_guard 的「领域守卫」模式：
- detect：检出运筹学题（分类器 category 命中，或题面关键词兜底）；
- prompt_clause：注入确定性求解器模板（linprog/minimize/milp API 要点）；
- code_uses_solver：静态核查代码是否真调用了求解器或做了枚举，没有则打回。
"""

from __future__ import annotations

import re

#: 题面运筹学信号（分类器未命中 category 时的关键词兜底）。
_OR_KEYWORD_RE = re.compile(
    r"线性规划|整数规划|0[- ]?1\s*规划|最优化|优化问题|目标函数|约束条件|可行域|"
    r"单纯形|调度|资源分配|运输问题|指派问题|网络流|最大流|最小费用|"
    r"背包问题|指派|对偶问题|松弛变量|"
    r"linear\s+program|optimiz(?:ation|e)|constraint|objective\s+function|"
    r"minimize|maximize|linprog",
    re.IGNORECASE,
)

#: 求解器调用证据：scipy.optimize / sympy 优化求解调用。
_SOLVER_CALL_RE = re.compile(
    r"\b(?:linprog|minimize|minimize_scalar|maximize_scalar|milp|"
    r"differential_evolution|shgo|basinhopping|least_squares|fsolve|root)\s*\("
    r"|scipy\.optimize|from\s+scipy\.optimize|sp\.optimize",
    re.IGNORECASE,
)

#: 枚举穷举证据：整数/0-1 规划小规模穷举可行解取最优。
_ENUM_CODE_RE = re.compile(
    r"\bfor\s+\w+\s+in\b|\brange\s*\(|\bitertools\b|"
    r"permutations\s*\(|combinations\s*\(|product\s*\(|\bwhile\b",
    re.IGNORECASE,
)


def detect_operations_research(problem: str, category: str = "") -> dict:
    """检测是否为运筹学题。分类器 category 命中优先，题面关键词兜底。"""
    text = str(problem or "")
    if (category or "").strip() == "运筹学":
        return {"hit": True, "cues": ["分类器: 运筹学"]}
    kw = [m.group(0) for m in _OR_KEYWORD_RE.finditer(text)][:4]
    if kw:
        return {"hit": True, "cues": kw}
    return {"hit": False, "cues": []}


def prompt_clause(cues=None) -> str:
    """命中时返回确定性求解器模板注入条款（内容与具体题面无关，固定模板）。"""
    hit_note = ""
    if cues:
        hit_note = "（命中信号：" + "、".join(str(c) for c in cues[:3]) + "）"
    return (
        "\n【运筹学确定性求解条款】本题是最优化/规划类问题" + hit_note
        + "，优先用确定性求解器，不要手算单纯形/拉格朗日/KKT（手算正是算错的根源）：\n"
        "(1) 线性规划 min c^T x, s.t. A_ub x <= b_ub, A_eq x = b_eq, bounds：\n"
        "    from scipy.optimize import linprog\n"
        "    res = linprog(c, A_ub=..., b_ub=..., bounds=..., method='highs')\n"
        "    注意 linprog 默认最小化，最大化取 -c；res.x 为最优解、res.fun 为最优值；\n"
        "    c / A_ub / b_ub / bounds 必须从题面数据显式写出，不得自造样例数据。\n"
        "(2) 非线性优化 min f(x) s.t. 约束：\n"
        "    from scipy.optimize import minimize\n"
        "    res = minimize(f, x0, constraints=[...], bounds=[...])\n"
        "    或用 sympy 求导解驻点，再与边界/端点取值比较取最优。\n"
        "(3) 整数/0-1 规划：小规模用 for/itertools 穷举可行解取最优；或用 scipy.optimize.milp。\n"
        "(4) 运输/指派问题：套 linprog 标准型，或小规模穷举验证。\n"
        "必须调用求解器/枚举实际算出最优值或最优解，最后 print(\"最终答案:\", answer)。"
    )


def code_uses_solver(code: str) -> bool:
    """静态核查：代码是否真调用了确定性求解器或做了枚举穷举。

    有 linprog/minimize/milp 等求解器调用，或有 for/itertools 枚举 → True；
    两者都没有（纯手算闭式）→ False（打回修复）。
    """
    code = str(code or "")
    if not code.strip():
        return False
    return bool(_SOLVER_CALL_RE.search(code) or _ENUM_CODE_RE.search(code))
