# ============================================================
# solvers/skills/algebraic_geometry_skills.py — 代数几何技能
# ============================================================
from agents.solver_experts.skills import SolverSkill

ALGEBRAIC_GEOMETRY_SKILL = SolverSkill(
    skill_name="algebraic_geometry_skill", domain="algebraic_geometry", domain_cn="代数几何",
    solver_name="algebraic_geometry_solver",
    system_prompt="""你是一位代数几何专家，精通代数簇、概形理论和交截理论。
求解策略：
1. 将几何问题转化为代数问题（坐标环、理想）
2. 应用Hilbert零点定理建立代数集与理想的对应
3. 使用Bézout定理计算交点重数
4. 应用Riemann-Roch定理于代数曲线
5. 使用LaTeX格式书写所有数学公式""",
    strategies=[
        "Hilbert零点定理（Nullstellensatz）：代数集↔根理想",
        "Bézout定理：代数曲线的交点个数定理",
        "Riemann-Roch定理：除子的维数公式 l(D)-l(K-D)=deg(D)-g+1",
        "Gröbner基：多项式理想的消元计算",
        "奇点解消：吹开(blow-up)技术",
        "除子类群与Picard群",
        "交截理论：Chow环与交截重数",
    ],
    keywords=[
        "代数几何", "algebraic geometry", "代数簇", "概形", "Hilbert零点定理",
        "Nullstellensatz", "Bézout", "Riemann-Roch", "除子", "Gröbner",
        "奇点", "吹开", "blow-up", "交截", "Chow", "射影空间",
        "variety", "scheme", "divisor", "genus", "intersection",
    ],
    few_shot_examples=[{
        "problem": "利用Bézout定理求两个平面代数曲线的交点个数",
        "solution_steps": [
            {"step": 1, "description": "确定曲线的次数", "formula": "deg(C1)=m, deg(C2)=n"},
            {"step": 2, "description": "应用Bézout定理", "formula": "|C1∩C2| = m·n（计重数）"},
        ],
        "answer": "m·n个交点（一般位置）", "method": "Bézout定理"
    }],
    verification_strategy="Bézout验证：交点总数=次数之积。维数验证：使用Krull维数。奇点验证。",
    json_output_hint='{"final_answer":"...","reasoning_steps":[...],"methods_used":[...],"educational_hint":"..."}',
)
