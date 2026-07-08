# ============================================================
# solvers/skills/probability_skills.py — 概率论技能
# ============================================================
from agents.solver_experts.skills import SolverSkill

PROBABILITY_SKILL = SolverSkill(
    skill_name="probability_skill", domain="probability", domain_cn="概率论",
    solver_name="probability_solver",
    system_prompt="""你是一位概率论专家，精通概率分布、极限定理和随机过程基础。
求解策略：
1. 确定随机变量的分布类型（离散/连续/混合）
2. 计算期望、方差、矩、特征函数
3. 应用极限定理（大数定律、中心极限定理）
4. 使用条件概率和Bayes定理
5. 使用LaTeX格式书写所有数学公式""",
    strategies=[
        "Bayes定理与条件概率：P(A|B)=P(B|A)P(A)/P(B)",
        "全概率公式：P(B)=ΣP(B|A_i)P(A_i)",
        "大数定律（LLN）：样本均值依概率收敛于期望",
        "中心极限定理（CLT）：独立同分布之和近似正态分布",
        "特征函数法：φ(t)=E[e^{itX}]用于求分布",
        "Markov/Chebyshev不等式：概率上界估计",
        "条件期望与鞅：E[Y|X]的性质",
    ],
    keywords=[
        "概率", "probability", "随机变量", "分布", "期望", "方差",
        "大数定律", "中心极限", "Bayes", "Markov", "Chebyshev",
        "条件概率", "特征函数", "矩母函数", "协方差",
        "random variable", "distribution", "expectation", "LLN", "CLT",
    ],
    few_shot_examples=[{
        "problem": "随机变量X~N(0,1)，求P(|X|>1.96)",
        "solution_steps": [
            {"step": 1, "description": "利用对称性", "formula": "P(|X|>1.96)=2·P(X>1.96)"},
            {"step": 2, "description": "查标准正态表", "formula": "P(X>1.96)=0.025"},
        ],
        "answer": "P(|X|>1.96)=0.05", "method": "正态分布表"
    }],
    verification_strategy="概率归一验证：总概率=1。不等式验证：使用Markov/Chebyshev验证。数值模拟验证。",
    json_output_hint='{"final_answer":"...","reasoning_steps":[...],"methods_used":[...],"educational_hint":"..."}',
)
