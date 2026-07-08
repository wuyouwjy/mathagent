# algebraic_geometry_solver.py — 代数几何 Solver (DomainSolver)
from agents.solver_experts.base_solver import DomainSolver

class AlgebraicGeometrySolver(DomainSolver):
    solver_name = "algebraic_geometry_solver"
    solver_domain = "algebraic_geometry"
    solver_description = "代数几何"
    default_prompt = '你是一位代数几何专家。精通代数簇、概形和交截理论。应用Hilbert零点定理(Nullstellensatz)、Bézout定理、Riemann-Roch定理。逐步推理，LaTeX格式，JSON输出。'
    sympy_vars = ['x', 'y', 'z']
    sub_types = {
        "varieties": {"keywords": ['代数簇', 'variety', '理想', '零点', '坐标环'], "prompt": '代数簇专家。应用Hilbert零点定理(Nullstellensatz)建立代数集与理想的对应。'},
        "curves": {"keywords": ['代数曲线', 'Riemann-Roch', '亏格', 'genus', '除子'], "prompt": '代数曲线专家。使用Riemann-Roch定理计算除子维数。'},
        "intersection": {"keywords": ['交截', 'Bézout', 'Bezout', '重数', 'Chow'], "prompt": '交截理论专家。应用Bézout定理计算交点重数。'},
        "singularities": {"keywords": ['奇点', 'singularity', '吹开', 'blow-up', '解消'], "prompt": '奇点解消专家。使用吹开(blow-up)技术分析奇点。'},
    }
