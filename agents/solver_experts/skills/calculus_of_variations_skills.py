# ============================================================
# solvers/skills/calculus_of_variations_skills.py — 变分法技能
# ============================================================
from agents.solver_experts.skills import SolverSkill

CALCULUS_OF_VARIATIONS_SKILL = SolverSkill(
    skill_name="calculus_of_variations_skill", domain="calculus_of_variations", domain_cn="变分法",
    solver_name="calculus_of_variations_solver",
    system_prompt="""你是一位变分法专家，精通泛函极值问题和最优控制理论。
求解策略：
1. 建立泛函表达式，确定边界条件（固定/自由/周期性）
2. 应用 Euler-Lagrange 方程导出必要条件
3. 对于约束变分问题使用 Lagrange 乘子法
4. 利用 Hamilton 原理和 Noether 定理
5. 使用LaTeX格式书写所有数学公式""",
    strategies=[
        "Euler-Lagrange方程：∂L/∂y - d/dx(∂L/∂y') = 0",
        "Hamilton原理：真实运动使作用量泛函取极值",
        "Noether定理：对称性⇒守恒律",
        "直接法：Ritz法、Galerkin法近似求解",
        "约束变分：等周问题、Lagrange乘子法",
        "二阶变分与Legendre条件",
        "横截条件处理自由边界问题",
    ],
    keywords=[
        "变分法", "calculus of variations", "Euler-Lagrange", "Hamilton",
        "作用量", "泛函极值", "Noether", "守恒律", "等周问题",
        "最速降线", "最小曲面", "Ritz法", "variational",
    ],
    few_shot_examples=[{
        "problem": "求连接两点间的最速降线",
        "solution_steps": [
            {"step": 1, "description": "建立时间泛函", "formula": "T = ∫ds/v = ∫√(1+y'²)/√(2gy) dx"},
            {"step": 2, "description": "应用Euler-Lagrange方程", "formula": "∂L/∂y - d/dx(∂L/∂y') = 0"},
            {"step": 3, "description": "解得摆线参数方程"},
        ],
        "answer": "摆线(cycloid)", "method": "Euler-Lagrange方程"
    }],
    verification_strategy="Euler-Lagrange验证：检查是否满足必要条件。Legendre条件验证。数值验证：使用直接法数值对比。",
    json_output_hint='{"final_answer":"...","reasoning_steps":[...],"methods_used":[...],"educational_hint":"..."}',
)
