# ============================================================
# solvers/skills/differential_geometry_skills.py — 微分几何技能
# ============================================================
from agents.solver_experts.skills import SolverSkill

DIFFERENTIAL_GEOMETRY_SKILL = SolverSkill(
    skill_name="differential_geometry_skill", domain="differential_geometry", domain_cn="微分几何",
    solver_name="differential_geometry_solver",
    system_prompt="""你是一位微分几何专家，精通曲线曲面论、Riemann几何和张量分析。
求解策略：
1. 计算曲线/曲面的基本量（弧长、曲率、挠率、基本形式）
2. 应用Frenet标架理论和Gauss-Bonnet定理
3. 计算内蕴量（Gauss曲率、测地线）
4. 使用活动标架法和Cartan结构方程
5. 使用LaTeX格式书写所有数学公式""",
    strategies=[
        "Frenet标架：曲线论基本定理，曲率和挠率计算",
        "第一/第二基本形式：曲面的度量与弯曲信息",
        "Gauss曲率与平均曲率：Weingarten映射的特征值",
        "Gauss绝妙定理：Gauss曲率是内蕴量",
        "Gauss-Bonnet定理：∫KdA = 2πχ(M)",
        "测地线方程：曲面上最短路径的微分方程",
        "活动标架法：Cartan结构方程",
    ],
    keywords=[
        "微分几何", "differential geometry", "曲率", "挠率", "Gauss",
        "测地线", "基本形式", "Frenet", "标架", "Riemann",
        "流形", "张量", "Christoffel", "Gauss-Bonnet",
        "curvature", "torsion", "geodesic", "manifold",
    ],
    few_shot_examples=[{
        "problem": "求球面S^2的Gauss曲率",
        "solution_steps": [
            {"step": 1, "description": "球面参数化", "formula": "r(θ,φ)=(R sinθ cosφ, R sinθ sinφ, R cosθ)"},
            {"step": 2, "description": "计算基本形式", "formula": "I=R²dθ²+R²sin²θ dφ², II=-R dθ²-R sin²θ dφ²"},
            {"step": 3, "description": "Gauss曲率", "formula": "K = det(II)/det(I) = 1/R²"},
        ],
        "answer": "K=1/R²", "method": "基本形式法"
    }],
    verification_strategy="Gauss-Bonnet验证：∫KdA=2πχ。内蕴量验证：不同参数化下内蕴量不变。Frenet公式验证。",
    json_output_hint='{"final_answer":"...","reasoning_steps":[...],"methods_used":[...],"educational_hint":"..."}',
)
