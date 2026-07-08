# real_analysis_solver.py — 实分析 Solver (DomainSolver)
from agents.solver_experts.base_solver import DomainSolver

class RealAnalysisSolver(DomainSolver):
    solver_name = "real_analysis_solver"
    solver_domain = "real_analysis"
    solver_description = "实分析"
    default_prompt = '你是一位实分析专家。精通极限、连续性、微分、积分、级数理论。使用ε-δ语言进行严格论证，应用中值定理、Weierstrass定理、级数收敛判别法。请逐步推理，LaTeX格式，JSON输出。'
    sympy_vars = ['x', 'n', 'a', 'b']
    sub_types = {
        "limits": {"keywords": ['极限', 'limit', 'ε-δ', 'epsilon', '收敛'], "prompt": '极限计算专家。使用ε-δ论证、单调有界定理、夹逼定理。'},
        "continuity": {"keywords": ['连续', 'continuity', '一致连续', '介值'], "prompt": '连续性分析专家。应用介值定理、最值定理、一致连续性。'},
        "differentiation": {"keywords": ['导数', 'derivative', '微分', '中值定理', 'Taylor'], "prompt": '微分学专家。使用中值定理(Rolle/Lagrange/Cauchy)、Taylor展开。'},
        "integration": {"keywords": ['积分', 'integral', 'Riemann', '黎曼', '不定积分'], "prompt": '积分学专家。使用Riemann可积条件、Newton-Leibniz公式、反常积分判别。'},
        "series": {"keywords": ['级数', 'series', '收敛半径', '幂级数', 'Fourier'], "prompt": '级数分析专家。使用比较/比值/根值/积分判别法，幂级数收敛半径。'},
    }
