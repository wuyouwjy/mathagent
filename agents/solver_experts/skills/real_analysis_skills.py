# ============================================================
# solvers/skills/real_analysis_skills.py — 实分析技能
# ============================================================
from agents.solver_experts.skills import SolverSkill

REAL_ANALYSIS_SKILL = SolverSkill(
    skill_name="real_analysis_skill", domain="real_analysis", domain_cn="实分析",
    solver_name="real_analysis_solver",
    system_prompt="""你是一位实分析专家，精通极限理论、连续性、微分和积分理论。
求解策略：
1. 明确函数定义域和性质（连续性、可微性、可积性）
2. 应用 ε-δ 语言进行严格论证
3. 使用相关定理（中值定理、Weierstrass定理、Bolzano-Weierstrass定理等）
4. 对于级数问题，使用各种收敛判别法
5. 使用LaTeX格式书写所有数学公式""",
    strategies=[
        "ε-δ论证：逐点极限、一致收敛的严格证明",
        "中值定理：Rolle定理、Lagrange中值定理、Cauchy中值定理",
        "Taylor展开：函数的Taylor级数展开及余项估计",
        "收敛判别：比较判别法、比值判别法、根值判别法、积分判别法",
        "一致收敛：Weierstrass M-判别法、Dini定理",
        "连续函数性质：介值定理、最值定理、一致连续性",
        "Riemann可积条件：达布上下和、Lebesgue判别法",
    ],
    keywords=[
        "实分析", "real analysis", "极限", "limit", "连续", "continuity",
        "导数", "derivative", "积分", "integral", "级数", "series",
        "一致收敛", "uniform convergence", "中值定理", "mean value",
        "Taylor", "ε-δ", "Riemann", "黎曼", "Weierstrass",
    ],
    few_shot_examples=[{
        "problem": "证明 lim(n→∞) (1+1/n)^n = e",
        "solution_steps": [
            {"step": 1, "description": "利用单调有界定理", "formula": "证明数列单调递增且有上界"},
            {"step": 2, "description": "利用二项式展开", "formula": "(1+1/n)^n = ΣC(n,k)/n^k"},
        ],
        "answer": "极限为e", "method": "单调有界定理"
    }],
    verification_strategy="代入验证：极限值是否满足定义。不等式验证：检查上下界估计。数值验证：代入大n值数值验证。",
    json_output_hint='{"final_answer":"...","reasoning_steps":[...],"methods_used":[...],"educational_hint":"..."}',
)
