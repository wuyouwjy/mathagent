# numerical_analysis_solver.py — 数值分析 Solver (DomainSolver)
from agents.solver_experts.base_solver import DomainSolver

class NumericalAnalysisSolver(DomainSolver):
    solver_name = "numerical_analysis_solver"
    solver_domain = "numerical_analysis"
    solver_description = "数值分析"
    default_prompt = '你是一位数值分析专家。精通数值方法和误差分析。应用Newton法、Lagrange插值、梯形/Simpson数值积分、Runge-Kutta方法、收敛阶分析。使用SymPy辅助计算，逐步推理，LaTeX格式，JSON输出。'
    sympy_vars = ['x', 'y', 't', 'h']
    sub_types = {
        "root_finding": {"keywords": ['Newton', '二分', '迭代', '方程求根', '收敛阶', '割线'], "prompt": '方程求根专家。Newton法、二分法、割线法，收敛阶分析。'},
        "interpolation": {"keywords": ['插值', 'Lagrange', 'Newton插值', '样条', '最小二乘'], "prompt": '插值专家。Lagrange/Newton插值、样条插值、最小二乘拟合。'},
        "integration_num": {"keywords": ['数值积分', '梯形', 'Simpson', 'Romberg', 'Gauss求积'], "prompt": '数值积分专家。梯形/Simpson/Romberg/Gauss求积公式。'},
        "ode_num": {"keywords": ['Runge-Kutta', 'Euler法', '数值解ODE', '线性多步法'], "prompt": 'ODE数值解专家。Euler法、Runge-Kutta法、线性多步法。'},
        "linear_num": {"keywords": ['Gauss消去', 'LU分解', 'Jacobi', 'Gauss-Seidel', '条件数'], "prompt": '数值线性代数专家。Gauss消去、LU分解、Jacobi/Gauss-Seidel迭代。'},
    }
