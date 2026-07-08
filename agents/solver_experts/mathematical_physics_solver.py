# mathematical_physics_solver.py — 数学物理 Solver (DomainSolver)
from agents.solver_experts.base_solver import DomainSolver

class MathematicalPhysicsSolver(DomainSolver):
    solver_name = "mathematical_physics_solver"
    solver_domain = "mathematical_physics"
    solver_description = "数学物理"
    default_prompt = '你是一位数学物理专家。精通物理中的数学方法和方程。应用分离变量法、积分变换（Fourier/Laplace）、特殊函数（Bessel/Legendre/球谐）、Green函数、变分原理。逐步推理，LaTeX格式，JSON输出。'
    sympy_vars = ['x', 't', 'u', 'ψ', 'ω']
    sub_types = {
        "quantum": {"keywords": ['Schrödinger', '量子', '波函数', '谐振子', '势阱'], "prompt": '量子力学专家。求解Schrödinger方程、谐振子、无限深势阱。'},
        "electromag": {"keywords": ['Maxwell', '电磁', '电场', '磁场', '波动'], "prompt": '电磁学专家。应用Maxwell方程组分析电磁场。'},
        "fluid": {"keywords": ['Navier-Stokes', '流体', 'Euler方程', 'Bernoulli'], "prompt": '流体力学专家。使用Navier-Stokes方程和Euler方程。'},
        "wave_heat": {"keywords": ['波动方程', '热传导', '扩散', "d'Alembert"], "prompt": '波动/热传导专家。使用分离变量法和积分变换求解。'},
    }
