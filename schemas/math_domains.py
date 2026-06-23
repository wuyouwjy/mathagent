# ============================================================
# schemas/math_domains.py — 数学领域分类定义
# 定义18个数学子领域的元数据，供 Classifier Agent 使用
# ============================================================

from enum import Enum
from typing import Dict, List


class MathDomain(str, Enum):
    """
    数学领域枚举 — 覆盖竞赛数据集中的18个数学子领域
    每个领域对应一个 Solver 策略
    """
    # --- 分析与方程 ---
    PARTIAL_DIFFERENTIAL_EQUATIONS = "partial_differential_equations"   # 偏微分方程
    ORDINARY_DIFFERENTIAL_EQUATIONS = "ordinary_differential_equations" # 常微分方程
    COMPLEX_ANALYSIS = "complex_analysis"                                # 复分析
    REAL_ANALYSIS = "real_analysis"                                      # 实分析
    FUNCTIONAL_ANALYSIS = "functional_analysis"                          # 泛函分析
    CALCULUS_OF_VARIATIONS = "calculus_of_variations"                    # 变分法

    # --- 代数与结构 ---
    ALGEBRA = "algebra"                          # 代数（抽象代数、线性代数）
    NUMBER_THEORY = "number_theory"              # 数论
    GROUP_THEORY = "group_theory"                # 群论

    # --- 几何与拓扑 ---
    TOPOLOGY = "topology"                        # 拓扑学
    DIFFERENTIAL_GEOMETRY = "differential_geometry"  # 微分几何
    ALGEBRAIC_GEOMETRY = "algebraic_geometry"        # 代数几何

    # --- 应用数学 ---
    OPTIMIZATION = "optimization"                # 运筹学 / 最优化
    PROBABILITY = "probability"                  # 概率论
    STATISTICS = "statistics"                    # 统计学
    NUMERICAL_ANALYSIS = "numerical_analysis"    # 数值分析
    COMBINATORICS = "combinatorics"              # 组合数学
    MATHEMATICAL_PHYSICS = "mathematical_physics"  # 数学物理


# ============================================================
# 领域 → Solver 路由映射表
# 将18个领域映射到6个核心 Solver Agent
# ============================================================

DOMAIN_TO_SOLVER: Dict[MathDomain, str] = {
    # PDE Solver
    MathDomain.PARTIAL_DIFFERENTIAL_EQUATIONS:  "pde_solver",
    MathDomain.MATHEMATICAL_PHYSICS:            "pde_solver",

    # ODE Solver
    MathDomain.ORDINARY_DIFFERENTIAL_EQUATIONS: "ode_solver",
    MathDomain.CALCULUS_OF_VARIATIONS:          "ode_solver",
    MathDomain.FUNCTIONAL_ANALYSIS:             "ode_solver",

    # Complex Analysis Solver
    MathDomain.COMPLEX_ANALYSIS:                "complex_analysis_solver",

    # Topology Solver（含几何类）
    MathDomain.TOPOLOGY:                        "topology_solver",
    MathDomain.DIFFERENTIAL_GEOMETRY:           "topology_solver",
    MathDomain.ALGEBRAIC_GEOMETRY:              "topology_solver",

    # Optimization Solver（含应用数学类）
    MathDomain.OPTIMIZATION:                    "optimization_solver",
    MathDomain.PROBABILITY:                     "optimization_solver",
    MathDomain.STATISTICS:                      "optimization_solver",
    MathDomain.NUMERICAL_ANALYSIS:              "optimization_solver",
    MathDomain.COMBINATORICS:                   "optimization_solver",

    # Algebra Solver（含代数结构类）
    MathDomain.ALGEBRA:                         "algebra_solver",
    MathDomain.NUMBER_THEORY:                   "algebra_solver",
    MathDomain.GROUP_THEORY:                    "algebra_solver",
    MathDomain.REAL_ANALYSIS:                   "algebra_solver",
}


# ============================================================
# 领域中文名映射（用于日志与可视化）
# ============================================================

DOMAIN_CN_NAME: Dict[MathDomain, str] = {
    MathDomain.PARTIAL_DIFFERENTIAL_EQUATIONS:  "偏微分方程",
    MathDomain.ORDINARY_DIFFERENTIAL_EQUATIONS: "常微分方程",
    MathDomain.COMPLEX_ANALYSIS:                "复分析",
    MathDomain.REAL_ANALYSIS:                   "实分析",
    MathDomain.FUNCTIONAL_ANALYSIS:             "泛函分析",
    MathDomain.CALCULUS_OF_VARIATIONS:          "变分法",
    MathDomain.ALGEBRA:                         "代数",
    MathDomain.NUMBER_THEORY:                   "数论",
    MathDomain.GROUP_THEORY:                    "群论",
    MathDomain.TOPOLOGY:                        "拓扑学",
    MathDomain.DIFFERENTIAL_GEOMETRY:           "微分几何",
    MathDomain.ALGEBRAIC_GEOMETRY:              "代数几何",
    MathDomain.OPTIMIZATION:                    "运筹学/最优化",
    MathDomain.PROBABILITY:                     "概率论",
    MathDomain.STATISTICS:                      "统计学",
    MathDomain.NUMERICAL_ANALYSIS:              "数值分析",
    MathDomain.COMBINATORICS:                   "组合数学",
    MathDomain.MATHEMATICAL_PHYSICS:            "数学物理",
}


# ============================================================
# 每个 Solver 的调度优先级（用于 Router 决策）
# ============================================================

SOLVER_PRIORITY: Dict[str, int] = {
    "pde_solver":               1,
    "ode_solver":               2,
    "complex_analysis_solver":  3,
    "topology_solver":          4,
    "optimization_solver":      5,
    "algebra_solver":           6,
}


def get_solver_for_domain(domain: str) -> str:
    """
    根据数学领域字符串返回对应的 Solver 名称

    参数:
        domain: 领域字符串（可以是 MathDomain 值或中文名）

    返回:
        str: Solver 名称（如 "pde_solver"）

    异常:
        ValueError: 当领域无法匹配时抛出
    """
    # 尝试直接匹配枚举值
    for math_domain, solver in DOMAIN_TO_SOLVER.items():
        if domain == math_domain.value or domain == DOMAIN_CN_NAME.get(math_domain):
            return solver

    # 尝试部分匹配
    domain_lower = domain.lower().replace(" ", "_")
    for math_domain, solver in DOMAIN_TO_SOLVER.items():
        if domain_lower in math_domain.value or math_domain.value in domain_lower:
            return solver

    # 默认回退到 algebra_solver（通用推理能力最强）
    return "algebra_solver"


def list_all_domains() -> List[Dict[str, str]]:
    """
    列出所有18个数学领域及其元数据

    返回:
        List[Dict]: 包含领域信息的字典列表
    """
    return [
        {
            "domain_key": domain.value,
            "domain_cn": DOMAIN_CN_NAME.get(domain, ""),
            "solver": DOMAIN_TO_SOLVER.get(domain, ""),
        }
        for domain in MathDomain
    ]
