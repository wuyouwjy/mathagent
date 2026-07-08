# number_theory_solver.py — 数论 Solver (DomainSolver)
from agents.solver_experts.base_solver import DomainSolver

class NumberTheorySolver(DomainSolver):
    solver_name = "number_theory_solver"
    solver_domain = "number_theory"
    solver_description = "数论"
    default_prompt = '你是一位数论专家。精通初等数论和解析数论。应用算术基本定理、模运算、Euler定理、费马小定理、中国剩余定理、二次互反律。逐步推理，LaTeX格式，JSON输出。'
    sympy_vars = ['n', 'a', 'b', 'p', 'q']
    sub_types = {
        "modular": {"keywords": ['同余', '模', 'mod', '费马', 'Euler', 'φ', 'CRT'], "prompt": '模运算专家。使用同余、Euler定理、中国剩余定理(CRT)。'},
        "diophantine": {"keywords": ['丢番图', 'diophantine', '不定方程', 'Pell'], "prompt": '丢番图方程专家。求解线性丢番图方程、Pell方程。'},
        "prime": {"keywords": ['素数', 'prime', '因数分解', '分布', '素数定理'], "prompt": '素数理论专家。素数判定、因数分解、算术基本定理。'},
        "quadratic": {"keywords": ['二次互反', 'Legendre', 'Jacobi', '平方剩余'], "prompt": '二次互反律专家。使用Legendre符号和Jacobi符号。'},
    }
