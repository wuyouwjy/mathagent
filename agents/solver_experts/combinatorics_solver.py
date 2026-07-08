# combinatorics_solver.py — 组合数学/离散数学 Solver (DomainSolver)
from agents.solver_experts.base_solver import DomainSolver

class CombinatoricsSolver(DomainSolver):
    solver_name = "combinatorics_solver"
    solver_domain = "combinatorics"
    solver_description = "组合数学/离散数学"
    default_prompt = '你是一位组合数学专家。精通计数理论、图论和组合设计。应用鸽巢原理、容斥原理、Burnside引理、生成函数、递推关系、Ramsey理论。逐步推理，LaTeX格式，JSON输出。'
    sympy_vars = ['n', 'k', 'm', 'r']
    sub_types = {
        "counting": {"keywords": ['计数', '排列', '组合', '二项式', 'Catalan', 'Stirling'], "prompt": '计数专家。使用排列组合、二项式系数、Catalan数、Stirling数。'},
        "graph_theory": {"keywords": ['图论', 'graph', '树', '平面图', 'Euler公式', 'Hamilton'], "prompt": '图论专家。树的性质、平面图Euler公式、染色问题。'},
        "generating": {"keywords": ['生成函数', 'generating', '递推', 'recurrence', '特征方程'], "prompt": '生成函数专家。普通/指数型生成函数、递推关系求解。'},
        "principles": {"keywords": ['鸽巢', '容斥', 'Burnside', 'Ramsey', '抽屉'], "prompt": '组合原理专家。鸽巢原理、容斥原理、Burnside引理、Ramsey理论。'},
    }
