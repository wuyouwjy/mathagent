# ============================================================
# solvers/skills/number_theory_skills.py — 数论技能
# ============================================================
from agents.solver_experts.skills import SolverSkill

NUMBER_THEORY_SKILL = SolverSkill(
    skill_name="number_theory_skill", domain="number_theory", domain_cn="数论",
    solver_name="number_theory_solver",
    system_prompt="""你是一位数论专家，精通初等数论、解析数论和代数数论。
求解策略：
1. 分析数的性质和结构（素数、整除性、同余）
2. 应用模运算和同余理论
3. 使用初等数论方法（算术基本定理、Euler定理、中国剩余定理）
4. 对于解析数论问题使用Dirichlet级数和特征函数
5. 使用LaTeX格式书写所有数学公式""",
    strategies=[
        "同余与模运算：线性同余、CRT（中国剩余定理）",
        "素数理论：素数分布、素数判定、算术基本定理",
        "Euler函数与费马小定理：a^(p-1)≡1(mod p)",
        "二次互反律：Legendre符号和Jacobi符号",
        "丢番图方程：线性丢番图方程、Pell方程",
        "原根与指数：离散对数问题",
        "Dirichlet特征与L-函数",
    ],
    keywords=[
        "数论", "number theory", "素数", "同余", "整除", "费马", "Euler",
        "丢番图", "模运算", "二次互反", "Legendre", "原根",
        "算术基本定理", "Dirichlet", "Riemann zeta", "素数定理",
        "prime", "congruence", "modular", "CRT",
    ],
    few_shot_examples=[{
        "problem": "证明：若 n 是合数，则 2^n-1 也是合数",
        "solution_steps": [
            {"step": 1, "description": "设n=ab", "formula": "2^n-1 = (2^a)^b - 1"},
            {"step": 2, "description": "因式分解", "formula": "= (2^a-1)(2^{a(b-1)}+...+1)"},
        ],
        "answer": "2^n-1为合数", "method": "因式分解"
    }],
    verification_strategy="代入验证：将答案代入原条件。同余验证：使用模运算验证。数值验证：小数值检验。",
    json_output_hint='{"final_answer":"...","reasoning_steps":[...],"methods_used":[...],"educational_hint":"..."}',
)
