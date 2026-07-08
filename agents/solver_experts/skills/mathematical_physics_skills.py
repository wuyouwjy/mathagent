# ============================================================
# solvers/skills/mathematical_physics_skills.py — 数学物理技能
# ============================================================
from agents.solver_experts.skills import SolverSkill

MATHEMATICAL_PHYSICS_SKILL = SolverSkill(
    skill_name="mathematical_physics_skill", domain="mathematical_physics", domain_cn="数学物理",
    solver_name="mathematical_physics_solver",
    system_prompt="""你是一位数学物理专家，精通物理中的数学方法和方程。
求解策略：
1. 识别物理背景和数学结构（ODE/PDE/变分原理）
2. 建立数学模型（守恒律、对称性、变分原理）
3. 应用数学物理方法（分离变量、积分变换、特殊函数）
4. 使用LaTeX格式书写所有数学公式""",
    strategies=[
        "Navier-Stokes方程：流体运动的动量守恒",
        "Maxwell方程组：电磁场的统一描述",
        "Schrödinger方程：量子力学波函数演化",
        "分离变量法：时空分离求解线性PDE",
        "特殊函数：Bessel函数、Legendre多项式、球谐函数",
        "积分变换：Fourier/Laplace变换在物理中的应用",
        "守恒律与对称性：Noether定理",
    ],
    keywords=[
        "数学物理", "mathematical physics", "Navier-Stokes", "Maxwell",
        "Schrödinger", "波动方程", "热传导", "守恒律", "对称性",
        "Bessel", "Legendre", "球谐函数", "Green函数",
        "流体", "电磁", "量子", "相对论", "扩散",
    ],
    few_shot_examples=[{
        "problem": "求解一维谐振子的Schrödinger方程",
        "solution_steps": [
            {"step": 1, "description": "无量纲化方程", "formula": "-ħ²/2m ψ'' + ½mω²x²ψ = Eψ"},
            {"step": 2, "description": "利用Hermite多项式求解"},
        ],
        "answer": "E_n = ħω(n+1/2)", "method": "级数解法"
    }],
    verification_strategy="量纲验证。边界条件验证。守恒律验证：能量/动量守恒。",
    json_output_hint='{"final_answer":"...","reasoning_steps":[...],"methods_used":[...],"educational_hint":"..."}',
)
