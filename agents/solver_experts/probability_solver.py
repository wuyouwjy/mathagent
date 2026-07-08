# probability_solver.py — 概率论 Solver (DomainSolver)
from agents.solver_experts.base_solver import DomainSolver

class ProbabilitySolver(DomainSolver):
    solver_name = "probability_solver"
    solver_domain = "probability"
    solver_description = "概率论"
    default_prompt = '你是一位概率论专家。精通概率分布、极限定理和随机过程基础。应用Bayes定理、全概率公式、大数定律、中心极限定理、Markov/Chebyshev不等式、特征函数。逐步推理，LaTeX格式，JSON输出。'
    sympy_vars = ['x', 'n', 'λ', 'μ', 'σ']
    sub_types = {
        "distributions": {"keywords": ['分布', '正态', '泊松', '指数', '均匀', '二项', '几何'], "prompt": '概率分布专家。计算各分布的期望、方差、特征函数。'},
        "limit_theorems": {"keywords": ['大数定律', '中心极限', 'LLN', 'CLT', '依概率收敛'], "prompt": '极限定理专家。应用大数定律(LLN)和中心极限定理(CLT)。'},
        "conditional": {"keywords": ['条件概率', 'Bayes', '全概率', '独立', '条件期望'], "prompt": '条件概率专家。使用Bayes定理和全概率公式。'},
        "moments": {"keywords": ['期望', '方差', '协方差', '矩', '特征函数', '矩母函数'], "prompt": '矩计算专家。计算期望、方差、协方差、特征函数、矩母函数。'},
    }
