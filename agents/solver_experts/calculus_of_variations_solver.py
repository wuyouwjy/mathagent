# calculus_of_variations_solver.py — 变分法 Solver (DomainSolver)
from agents.solver_experts.base_solver import DomainSolver

class CalculusOfVariationsSolver(DomainSolver):
    solver_name = "calculus_of_variations_solver"
    solver_domain = "calculus_of_variations"
    solver_description = "变分法"
    default_prompt = '你是一位变分法专家。精通泛函极值问题和最优控制。应用Euler-Lagrange方程、Hamilton原理、Noether定理、直接法（Ritz法）。逐步推理，LaTeX格式，JSON输出。'
    sympy_vars = ['x', 'y', 't', 'u']
    sub_types = {
        "euler_lagrange": {"keywords": ['Euler-Lagrange', '变分', '泛函', '极值', '最速降线'], "prompt": 'Euler-Lagrange方程专家。导出泛函极值的必要条件。'},
        "hamilton": {"keywords": ['Hamilton', '作用量', 'Noether', '守恒律', '正则方程'], "prompt": 'Hamilton力学专家。使用Hamilton原理和Noether定理。'},
        "constraints": {"keywords": ['约束', '等周', 'Lagrange乘子', '横截条件'], "prompt": '约束变分专家。等周问题、Lagrange乘子法、横截条件。'},
    }
