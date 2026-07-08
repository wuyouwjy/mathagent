# group_theory_solver.py — 群论 Solver (DomainSolver)
from agents.solver_experts.base_solver import DomainSolver

class GroupTheorySolver(DomainSolver):
    solver_name = "group_theory_solver"
    solver_domain = "group_theory"
    solver_description = "群论"
    default_prompt = '你是一位群论专家。精通有限群论和群表示论。应用Sylow定理、群作用、轨道-稳定子定理、同构定理、Jordan-Hölder定理、有限生成Abel群分类。逐步推理，LaTeX格式，JSON输出。'
    sympy_vars = []
    sub_types = {
        "finite": {"keywords": ['有限群', '阶', 'Sylow', 'Lagrange', 'p-群'], "prompt": '有限群专家。应用Sylow定理分析p-子群的存在性和共轭性。'},
        "group_action": {"keywords": ['群作用', '轨道', '稳定子', 'Burnside', '共轭'], "prompt": '群作用专家。使用轨道-稳定子定理和Burnside引理。'},
        "abelian": {"keywords": ['Abel', '交换', '循环', 'cyclic', '有限生成'], "prompt": 'Abel群专家。应用有限生成Abel群分类定理。'},
        "structure": {"keywords": ['同构', 'Jordan-Hölder', '合成列', '单群', '正规'], "prompt": '群结构专家。同构定理、Jordan-Hölder定理、合成列分析。'},
    }
