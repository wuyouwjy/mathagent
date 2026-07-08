# ============================================================
# solvers/skills/numerical_analysis_skills.py — 数值分析技能
# ============================================================
from agents.solver_experts.skills import SolverSkill

NUMERICAL_ANALYSIS_SKILL = SolverSkill(
    skill_name="numerical_analysis_skill", domain="numerical_analysis", domain_cn="数值分析",
    solver_name="numerical_analysis_solver",
    system_prompt="""你是一位数值分析专家，精通数值方法、误差分析和算法设计。
求解策略：
1. 选择合适的数值方法（迭代法/直接法/插值法/积分法）
2. 分析方法的收敛性、稳定性和误差界
3. 进行误差估计（截断误差+舍入误差）
4. 给出数值结果并评估精度
5. 使用LaTeX格式书写所有数学公式""",
    strategies=[
        "方程求根：Newton法、二分法、割线法及其收敛阶分析",
        "线性方程组：Gauss消去法、LU分解、迭代法（Jacobi/Gauss-Seidel）",
        "插值与逼近：Lagrange插值、Newton插值、样条插值、最小二乘",
        "数值积分：梯形法则、Simpson法则、Romberg积分、Gauss求积",
        "ODE数值解：Euler法、Runge-Kutta法、线性多步法",
        "特征值计算：幂法、QR算法、Householder变换",
        "误差分析：Lax等价定理（相容性+稳定性⇒收敛性）",
    ],
    keywords=[
        "数值分析", "numerical analysis", "Newton法", "迭代", "收敛",
        "插值", "Lagrange", "梯形法则", "Simpson", "Romberg",
        "Runge-Kutta", "LU分解", "Gauss-Seidel", "QR分解",
        "误差", "稳定性", "condition number", "条件数",
    ],
    few_shot_examples=[{
        "problem": "用Newton迭代法求√3，x_0=2，迭代三次",
        "solution_steps": [
            {"step": 1, "description": "Newton迭代公式", "formula": "x_{n+1}=x_n-f(x_n)/f'(x_n)"},
            {"step": 2, "description": "f(x)=x²-3", "formula": "x_{n+1}=(x_n+3/x_n)/2"},
            {"step": 3, "description": "迭代计算", "formula": "x_1=1.75, x_2≈1.73214, x_3≈1.73205"},
        ],
        "answer": "x_3≈1.73205", "method": "Newton迭代法"
    }],
    verification_strategy="误差验证：|x_{n+1}-x_n|<ε。收敛阶验证。代入验证：f(x)≈0。",
    json_output_hint='{"final_answer":"...","reasoning_steps":[...],"methods_used":[...],"educational_hint":"..."}',
)
