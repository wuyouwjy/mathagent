# ============================================================
# solvers/solver_registry.py — Solver 注册中心
# 工厂模式：根据 solver_name 创建对应的 Solver 实例
# ============================================================

from typing import Dict, Optional, Type
from loguru import logger

from solvers.base_solver import BaseSolver
from solvers.pde_solver import PDESolver
from solvers.ode_solver import ODESolver
from solvers.complex_analysis_solver import ComplexAnalysisSolver
from solvers.topology_solver import TopologySolver
from solvers.optimization_solver import OptimizationSolver
from solvers.algebra_solver import AlgebraSolver


# ============================================================
# Solver 注册表
# ============================================================

SOLVER_REGISTRY: Dict[str, Type[BaseSolver]] = {
    "pde_solver":                PDESolver,
    "ode_solver":                ODESolver,
    "complex_analysis_solver":   ComplexAnalysisSolver,
    "topology_solver":           TopologySolver,
    "optimization_solver":       OptimizationSolver,
    "algebra_solver":            AlgebraSolver,
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
