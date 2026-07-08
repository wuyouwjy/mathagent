# differential_geometry_solver.py — 微分几何 Solver (DomainSolver)
from agents.solver_experts.base_solver import DomainSolver

class DifferentialGeometrySolver(DomainSolver):
    solver_name = "differential_geometry_solver"
    solver_domain = "differential_geometry"
    solver_description = "微分几何"
    default_prompt = '你是一位微分几何专家。精通曲线曲面论、Riemann几何。应用Frenet标架、第一/第二基本形式、Gauss曲率、Gauss-Bonnet定理、测地线方程。逐步推理，LaTeX格式，JSON输出。'
    sympy_vars = ['t', 'u', 'v', 'θ', 'φ']
    sub_types = {
        "curves": {"keywords": ['曲线', '曲率', '挠率', 'Frenet', '弧长'], "prompt": '曲线论专家。使用Frenet标架计算曲率和挠率。'},
        "surfaces": {"keywords": ['曲面', '基本形式', 'Gauss曲率', '平均曲率', 'Weingarten'], "prompt": '曲面论专家。计算第一/第二基本形式和Gauss曲率。'},
        "geodesic": {"keywords": ['测地线', 'geodesic', '最短路径', '指数映射'], "prompt": '测地线专家。求解测地线微分方程。'},
        "gauss_bonnet": {"keywords": ['Gauss-Bonnet', 'Euler示性数', '总曲率'], "prompt": 'Gauss-Bonnet专家。验证∫KdA=2πχ(M)。'},
    }
