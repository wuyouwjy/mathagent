# statistics_solver.py — 统计学/统计推断 Solver (DomainSolver)
from agents.solver_experts.base_solver import DomainSolver

class StatisticsSolver(DomainSolver):
    solver_name = "statistics_solver"
    solver_domain = "statistics"
    solver_description = "统计学/统计推断"
    default_prompt = '你是一位统计学专家。精通参数估计、假设检验和回归分析。应用最大似然估计(MLE)、矩估计、Neyman-Pearson引理、Cramér-Rao下界、t检验/F检验。逐步推理，LaTeX格式，JSON输出。'
    sympy_vars = ['x', 'n', 'μ', 'σ', 'α']
    sub_types = {
        "estimation": {"keywords": ['估计', 'MLE', '矩估计', 'Bayes估计', '无偏', 'Cramér-Rao'], "prompt": '参数估计专家。使用MLE、矩估计、Bayes估计，计算Cramér-Rao下界。'},
        "testing": {"keywords": ['假设检验', 't检验', 'F检验', '卡方', '显著性', 'p值'], "prompt": '假设检验专家。使用t检验、F检验、卡方检验，p值计算。'},
        "confidence": {"keywords": ['置信区间', 'confidence interval', '区间估计'], "prompt": '置信区间专家。使用枢轴量法构建置信区间。'},
        "regression": {"keywords": ['回归', 'regression', '最小二乘', '线性模型'], "prompt": '回归分析专家。最小二乘法、线性回归模型。'},
    }
