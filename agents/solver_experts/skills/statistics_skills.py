# ============================================================
# solvers/skills/statistics_skills.py — 统计学技能
# ============================================================
from agents.solver_experts.skills import SolverSkill

STATISTICS_SKILL = SolverSkill(
    skill_name="statistics_skill", domain="statistics", domain_cn="统计学/统计推断",
    solver_name="statistics_solver",
    system_prompt="""你是一位统计学专家，精通参数估计、假设检验和回归分析。
求解策略：
1. 选择合适的估计方法（MLE、矩估计、Bayes估计）
2. 构建置信区间和进行假设检验
3. 计算估计量的性质（无偏性、一致性、有效性）
4. 使用LaTeX格式书写所有数学公式""",
    strategies=[
        "最大似然估计（MLE）：选择使观测概率最大的参数",
        "矩估计法：用样本矩代替总体矩",
        "Neyman-Pearson引理：似然比检验的最优性",
        "Cramér-Rao下界：无偏估计量方差的下界",
        "t检验与F检验：均值和方差的显著性检验",
        "置信区间构造：枢轴量法",
        "Bayes估计：先验分布+似然→后验分布",
    ],
    keywords=[
        "统计", "statistics", "最大似然", "MLE", "假设检验", "置信区间",
        "Neyman-Pearson", "Cramér-Rao", "t检验", "F检验", "卡方检验",
        "Bayes估计", "先验", "后验", "无偏估计", "充分统计量",
        "hypothesis test", "confidence interval", "estimator",
    ],
    few_shot_examples=[{
        "problem": "X_1,...,X_n ~ N(μ,σ²)，求μ的95%置信区间",
        "solution_steps": [
            {"step": 1, "description": "构造枢轴量", "formula": "T=(X̄-μ)/(S/√n) ~ t(n-1)"},
            {"step": 2, "description": "利用t分布分位数", "formula": "X̄ ± t_{α/2}·S/√n"},
        ],
        "answer": "X̄ ± t_{0.025}(n-1)·S/√n", "method": "枢轴量法"
    }],
    verification_strategy="无偏性验证：E[θ̂]=θ。置信区间覆盖率验证。假设检验功效验证。",
    json_output_hint='{"final_answer":"...","reasoning_steps":[...],"methods_used":[...],"educational_hint":"..."}',
)
