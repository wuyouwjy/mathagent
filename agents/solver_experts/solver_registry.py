# ============================================================
# solvers/solver_registry.py — Solver 注册中心
# 工厂模式：根据 solver_name 创建对应的 Solver 实例
# ============================================================

from typing import Dict, Optional, Type
from loguru import logger

from agents.solver_experts.base_solver import BaseSolver
from agents.solver_experts.pde_solver import PDESolver
from agents.solver_experts.ode_solver import ODESolver
from agents.solver_experts.complex_analysis_solver import ComplexAnalysisSolver
from agents.solver_experts.topology_solver import TopologySolver
from agents.solver_experts.optimization_solver import OptimizationSolver
from agents.solver_experts.algebra_solver import AlgebraSolver
from agents.solver_experts.real_analysis_solver import RealAnalysisSolver
from agents.solver_experts.functional_analysis_solver import FunctionalAnalysisSolver
from agents.solver_experts.calculus_of_variations_solver import CalculusOfVariationsSolver
from agents.solver_experts.number_theory_solver import NumberTheorySolver
from agents.solver_experts.group_theory_solver import GroupTheorySolver
from agents.solver_experts.differential_geometry_solver import DifferentialGeometrySolver
from agents.solver_experts.algebraic_geometry_solver import AlgebraicGeometrySolver
from agents.solver_experts.probability_solver import ProbabilitySolver
from agents.solver_experts.statistics_solver import StatisticsSolver
from agents.solver_experts.numerical_analysis_solver import NumericalAnalysisSolver
from agents.solver_experts.combinatorics_solver import CombinatoricsSolver
from agents.solver_experts.mathematical_physics_solver import MathematicalPhysicsSolver


# ============================================================
# Solver 注册表 — 18个领域 1:1 对应18个Solver专家
# ============================================================

SOLVER_REGISTRY: Dict[str, Type[BaseSolver]] = {
    "pde_solver":                     PDESolver,
    "ode_solver":                     ODESolver,
    "complex_analysis_solver":        ComplexAnalysisSolver,
    "topology_solver":                TopologySolver,
    "optimization_solver":            OptimizationSolver,
    "algebra_solver":                 AlgebraSolver,
    "real_analysis_solver":           RealAnalysisSolver,
    "functional_analysis_solver":     FunctionalAnalysisSolver,
    "calculus_of_variations_solver":  CalculusOfVariationsSolver,
    "number_theory_solver":           NumberTheorySolver,
    "group_theory_solver":            GroupTheorySolver,
    "differential_geometry_solver":   DifferentialGeometrySolver,
    "algebraic_geometry_solver":      AlgebraicGeometrySolver,
    "probability_solver":             ProbabilitySolver,
    "statistics_solver":              StatisticsSolver,
    "numerical_analysis_solver":      NumericalAnalysisSolver,
    "combinatorics_solver":           CombinatoricsSolver,
    "mathematical_physics_solver":    MathematicalPhysicsSolver,
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
        KeyError: 当 solver_name 无效时
    """
    if solver_name not in SOLVER_REGISTRY:
        logger.warning(
            f"[SolverRegistry] 未知 Solver: '{solver_name}'，"
            f"回退到 algebra_solver"
        )
        solver_name = "algebra_solver"

    solver_cls = SOLVER_REGISTRY[solver_name]
    solver = solver_cls()
    logger.debug(f"[SolverRegistry] 创建 Solver: {solver.solver_name}")
    return solver


def list_registered_solvers() -> Dict[str, str]:
    """
    列出所有已注册的 Solver

    返回:
        Dict[str, str]: {solver_name: description}
    """
    return {
        name: cls().solver_description
        for name, cls in SOLVER_REGISTRY.items()
    }


def get_solver_metadata(solver_name: str) -> Optional[Dict[str, str]]:
    """
    获取单个 Solver 的元数据

    参数:
        solver_name: Solver 名称

    返回:
        Optional[Dict]: 元数据字典
    """
    if solver_name in SOLVER_REGISTRY:
        solver = SOLVER_REGISTRY[solver_name]()
        return solver.get_metadata()
    return None
