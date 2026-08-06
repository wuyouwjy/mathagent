# ============================================================
# solvers/solver_registry.py — Solver 注册中心
# 工厂模式：根据 solver_name 创建对应的 Solver 实例
# ============================================================

from typing import Dict, Optional, Type
from loguru import logger

from agents.solver_experts.base_solver import BaseSolver

# ── 逐文件安全导入 —— 单个文件语法错误不影响其他 Solver ──

def _safe_import(module_name: str, class_name: str) -> Optional[type]:
    """安全导入 Solver 类，导入失败时记录错误并返回 None"""
    try:
        mod = __import__(module_name, fromlist=[class_name])
        return getattr(mod, class_name)
    except Exception as e:
        logger.error(f"[SolverRegistry] 导入 {class_name} 失败: {e}")
        return None

_PDESolver = _safe_import("agents.solver_experts.pde_solver", "PDESolver")
_ODESolver = _safe_import("agents.solver_experts.ode_solver", "ODESolver")
_ComplexAnalysisSolver = _safe_import("agents.solver_experts.complex_analysis_solver", "ComplexAnalysisSolver")
_TopologySolver = _safe_import("agents.solver_experts.topology_solver", "TopologySolver")
_OptimizationSolver = _safe_import("agents.solver_experts.optimization_solver", "OptimizationSolver")
_AlgebraSolver = _safe_import("agents.solver_experts.algebra_solver", "AlgebraSolver")
_RealAnalysisSolver = _safe_import("agents.solver_experts.real_analysis_solver", "RealAnalysisSolver")
_FunctionalAnalysisSolver = _safe_import("agents.solver_experts.functional_analysis_solver", "FunctionalAnalysisSolver")
_CalculusOfVariationsSolver = _safe_import("agents.solver_experts.calculus_of_variations_solver", "CalculusOfVariationsSolver")
_NumberTheorySolver = _safe_import("agents.solver_experts.number_theory_solver", "NumberTheorySolver")
_GroupTheorySolver = _safe_import("agents.solver_experts.group_theory_solver", "GroupTheorySolver")
_DifferentialGeometrySolver = _safe_import("agents.solver_experts.differential_geometry_solver", "DifferentialGeometrySolver")
_AlgebraicGeometrySolver = _safe_import("agents.solver_experts.algebraic_geometry_solver", "AlgebraicGeometrySolver")
_ProbabilitySolver = _safe_import("agents.solver_experts.probability_solver", "ProbabilitySolver")
_StatisticsSolver = _safe_import("agents.solver_experts.statistics_solver", "StatisticsSolver")
_NumericalAnalysisSolver = _safe_import("agents.solver_experts.numerical_analysis_solver", "NumericalAnalysisSolver")
_CombinatoricsSolver = _safe_import("agents.solver_experts.combinatorics_solver", "CombinatoricsSolver")
_MathematicalPhysicsSolver = _safe_import("agents.solver_experts.mathematical_physics_solver", "MathematicalPhysicsSolver")


# ============================================================
# Solver 注册表 — 18个领域 1:1 对应18个Solver专家
# ============================================================

SOLVER_REGISTRY: Dict[str, Optional[Type[BaseSolver]]] = {
    "pde_solver":                     _PDESolver,
    "ode_solver":                     _ODESolver,
    "complex_analysis_solver":        _ComplexAnalysisSolver,
    "topology_solver":                _TopologySolver,
    "optimization_solver":            _OptimizationSolver,
    "algebra_solver":                 _AlgebraSolver,
    "real_analysis_solver":           _RealAnalysisSolver,
    "functional_analysis_solver":     _FunctionalAnalysisSolver,
    "calculus_of_variations_solver":  _CalculusOfVariationsSolver,
    "number_theory_solver":           _NumberTheorySolver,
    "group_theory_solver":            _GroupTheorySolver,
    "differential_geometry_solver":   _DifferentialGeometrySolver,
    "algebraic_geometry_solver":      _AlgebraicGeometrySolver,
    "probability_solver":             _ProbabilitySolver,
    "statistics_solver":              _StatisticsSolver,
    "numerical_analysis_solver":      _NumericalAnalysisSolver,
    "combinatorics_solver":           _CombinatoricsSolver,
    "mathematical_physics_solver":    _MathematicalPhysicsSolver,
}


# ============================================================
# Solver 工厂函数
# ============================================================

def create_solver(solver_name: str) -> BaseSolver:
    """
    创建 Solver 实例（工厂方法）

    参数:
        solver_name: Solver 名称（如 "pde_solver"）

    返回:
        BaseSolver: Solver 实例

    异常:
        ValueError: 当 solver_name 未注册时
        RuntimeError: 当所有可用 Solver 都不可用时
    """
    if solver_name not in SOLVER_REGISTRY:
        logger.warning(
            f"[SolverRegistry] 未知 Solver: '{solver_name}'，"
            f"回退到 algebra_solver"
        )
        solver_name = "algebra_solver"

    solver_cls = SOLVER_REGISTRY.get(solver_name)

    # ── 如果目标 Solver 导入失败，遍历找第一个可用的 ──
    if solver_cls is None:
        logger.warning(
            f"[SolverRegistry] Solver '{solver_name}' 不可用，"
            f"尝试回退到其他 Solver"
        )
        for name, cls in SOLVER_REGISTRY.items():
            if cls is not None:
                solver_cls = cls
                logger.info(f"[SolverRegistry] 回退到: {name}")
                break

    if solver_cls is None:
        raise RuntimeError("[SolverRegistry] 所有 Solver 均不可用")

    solver = solver_cls()
    logger.debug(f"[SolverRegistry] 创建 Solver: {solver.solver_name}")
    return solver


def list_registered_solvers() -> Dict[str, str]:
    """
    列出所有已注册的 Solver

    返回:
        Dict[str, str]: {solver_name: description}
    """
    result = {}
    for name, cls in SOLVER_REGISTRY.items():
        if cls is not None:
            result[name] = cls().solver_description
        else:
            result[name] = f"[不可用] {name}"
    return result


def get_solver_metadata(solver_name: str) -> Optional[Dict[str, str]]:
    """
    获取单个 Solver 的元数据

    参数:
        solver_name: Solver 名称

    返回:
        Optional[Dict]: 元数据字典
    """
    if solver_name in SOLVER_REGISTRY:
        cls = SOLVER_REGISTRY[solver_name]
        if cls is not None:
            solver = cls()
            return solver.get_metadata()
    return None
