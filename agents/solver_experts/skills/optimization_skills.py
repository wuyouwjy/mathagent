# ============================================================
# solvers/skills/optimization_skills.py — 最优化/概率/统计/数值分析/组合技能
# ============================================================

from agents.solver_experts.skills import SolverSkill

OPTIMIZATION_SKILL = SolverSkill(
    skill_name="optimization_skill",
    domain="optimization",
    domain_cn="最优化/概率论/统计学/数值分析/组合数学",
    solver_name="optimization_solver",

    system_prompt="""你是一位最优化和应用数学专家，精通运筹学、概率论、统计学、数值分析和组合数学。
求解策略：
1. 识别问题类型：
   - 最优化：线性规划/非线性规划/整数规划/凸优化/组合优化
   - 概率论：分布计算/期望方差/极限定理
   - 统计学：参数估计/假设检验/回归分析
   - 数值分析：方程求根/数值积分/插值逼近
   - 组合数学：计数/图论/设计
2. 选择合适方法：
   - 线性规划：单纯形法/对偶理论
   - 非线性规划：拉格朗日乘子法/KKT条件/梯度下降
   - 概率：Bayes定理/全概率公式/特征函数
   - 数值：Newton法/梯形法则/Runge-Kutta
3. 使用SciPy optimize + SymPy进行计算
4. 使用LaTeX格式书写所有数学公式""",

    strategies=[
        "单纯形法：沿可行域顶点迭代优化线性目标函数",
        "KKT条件：检验非线性规划的局部最优必要条件",
        "拉格朗日乘子法：将约束优化转化为无约束问题",
        "对偶理论：原问题与对偶问题的最优值相等（强对偶）",
        "凸优化：局部最小值即为全局最小值（目标函数凸+可行域凸）",
        "概率方法：Bayes定理、全概率公式、中心极限定理、大数定律",
        "统计方法：最大似然估计MLE、Neyman-Pearson检验、Cramér-Rao下界",
        "数值方法：Newton-Raphson求根、Romberg积分、Runge-Kutta方法",
        "组合方法：鸽巢原理、容斥原理、Burnside引理、生成函数",
    ],

    keywords=[
        "优化", "optimization", "线性规划", "非线性规划", "约束",
        "目标函数", "可行域", "单纯形", "拉格朗日乘子", "KKT",
        "凸优化", "convex optimization", "对偶",
        "概率", "probability", "随机变量", "分布", "期望", "方差",
        "大数定律", "中心极限", "Bayes", "Markov", "Chebyshev",
        "统计", "statistics", "最大似然", "置信区间", "假设检验",
        "数值分析", "numerical analysis", "Newton法", "插值", "逼近",
        "组合", "combinatorics", "鸽巢", "容斥", "图论",
        "线性规划", "整数规划", "动态规划",
    ],

    few_shot_examples=[
        {
            "problem": "求 min f(x,y)=x²+y², s.t. x+y=1",
            "solution_steps": [
                {"step": 1, "description": "构造拉格朗日函数", "formula": "L=x²+y²+λ(x+y-1)"},
                {"step": 2, "description": "求偏导数并令为零", "formula": "∂L/∂x=2x+λ=0, ∂L/∂y=2y+λ=0"},
                {"step": 3, "description": "解得最优解", "formula": "x=y=-λ/2, 代入约束: -λ=1 → λ=-1, x=y=0.5"},
            ],
            "answer": "最小值 f(0.5,0.5)=0.5",
            "method": "拉格朗日乘子法"
        },
    ],

    verification_strategy="KKT条件验证：检查最优解满足所有KKT条件。对偶验证：原问题和对偶问题的最优值一致。数值验证：使用SciPy数值优化对比。统计验证：检查结果是否在合理范围内。",

    json_output_hint="""{
  "final_answer": "最优值/结果（LaTeX格式）",
  "reasoning_steps": [{"step_id": 1, "description": "...", "formula": "...", "method": "拉格朗日乘子法/单纯形法/..."}],
  "methods_used": ["拉格朗日乘子法", "KKT条件"],
  "educational_hint": "问题类型分析和解法选择解释"
}""",
)
