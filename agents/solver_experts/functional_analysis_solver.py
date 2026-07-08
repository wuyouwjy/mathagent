# functional_analysis_solver.py — 泛函分析 Solver (DomainSolver)
from agents.solver_experts.base_solver import DomainSolver

class FunctionalAnalysisSolver(DomainSolver):
    solver_name = "functional_analysis_solver"
    solver_domain = "functional_analysis"
    solver_description = "泛函分析"
    default_prompt = '你是一位泛函分析专家。精通Banach空间、Hilbert空间、算子理论。应用Hahn-Banach定理、Banach-Steinhaus定理、开映射定理、闭图像定理、Riesz表示定理。逐步推理，LaTeX格式，JSON输出。'
    sympy_vars = []
    sub_types = {
        "hilbert": {"keywords": ['Hilbert', '内积', '正交', 'Riesz', '投影'], "prompt": 'Hilbert空间专家。使用内积、正交投影、Riesz表示定理。'},
        "banach": {"keywords": ['Banach', '赋范', '对偶', '弱收敛', '自反'], "prompt": 'Banach空间专家。使用赋范、对偶空间、弱收敛分析。'},
        "operators": {"keywords": ['算子', 'operator', '紧算子', '自伴', '谱'], "prompt": '算子理论专家。分析紧算子、自伴算子、谱分解。'},
        "theorems": {"keywords": ['Hahn-Banach', '开映射', '闭图像', '一致有界'], "prompt": '泛函分析定理专家。Hahn-Banach延拓、开映射、闭图像、一致有界原理。'},
    }
