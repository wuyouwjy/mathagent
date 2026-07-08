# ============================================================
# solvers/skills/ode_skills.py — 常微分方程 + 变分法 + 泛函分析技能
# ============================================================

from agents.solver_experts.skills import SolverSkill

ODE_SKILL = SolverSkill(
    skill_name="ode_skill",
    domain="ordinary_differential_equations",
    domain_cn="常微分方程/变分法/泛函分析",
    solver_name="ode_solver",

    system_prompt="""你是一位常微分方程（ODE）、变分法和泛函分析专家。
求解策略：
1. 识别ODE的阶数、类型（线性/非线性、齐次/非齐次、自治/非自治）
2. 选择合适的解法：
   - 一阶线性：积分因子法
   - 常系数线性：特征方程法、待定系数法、常数变易法
   - 变系数：级数解法（Frobenius方法）、降阶法
   - 非线性：分离变量法、恰当方程、积分因子
3. 使用SymPy dsolve进行符号求解
4. 对于泛函分析问题：应用Hahn-Banach定理、Banach-Steinhaus定理、Riesz表示定理等
5. 对于变分法问题：使用Euler-Lagrange方程
6. 使用LaTeX格式书写所有数学公式""",

    strategies=[
        "特征方程法：对常系数线性ODE，设解为指数函数形式，求解特征方程",
        "常数变易法：先求齐次通解，再构造满足非齐次项的特解",
        "积分因子法：一阶线性ODE乘以积分因子化为全微分",
        "Laplace变换法：将ODE化为代数方程求解后逆变换",
        "级数解法：在正则奇点附近用Frobenius方法求级数解",
        "相平面分析：自治系统的平衡点分类与稳定性分析",
        "Euler-Lagrange方法：建立泛函，利用变分原理导出ODE",
        "适定性分析：Picard-Lindelöf定理判断解的存在唯一性",
    ],

    keywords=[
        "常微分", "ODE", "ordinary differential", "初值问题", "边值问题",
        "特征方程", "相图", "稳定性", "Lyapunov", "极限环",
        "变分法", "Euler-Lagrange", "Hamilton",
        "泛函分析", "Hahn-Banach", "Banach空间", "Hilbert空间",
        "Riesz表示", "紧算子", "谱理论",
        "积分因子", "Wronskian", "Frobenius", "级数解",
        "calculus of variations", "functional analysis",
    ],

    few_shot_examples=[
        {
            "problem": "求解 y'' + 4y' + 4y = 0, y(0)=1, y'(0)=0",
            "solution_steps": [
                {"step": 1, "description": "建立特征方程", "formula": "r²+4r+4=0"},
                {"step": 2, "description": "求解特征方程（重根）", "formula": "r=-2（重根）"},
                {"step": 3, "description": "写出通解", "formula": "y=(C₁+C₂x)e^{-2x}"},
                {"step": 4, "description": "代入初始条件确定常数", "formula": "y(0)=C₁=1, y'(0)=C₂-2C₁=0 → C₂=2"},
            ],
            "answer": "y=(1+2x)e^{-2x}",
            "method": "特征方程法"
        },
    ],

    verification_strategy="代入验证：将解代入原ODE检验。初始/边界条件验证：检验是否满足定解条件。Wronskian检验：验证线性无关解。数值验证：使用数值方法（RK4等）对比。",

    json_output_hint="""{
  "final_answer": "y(x)=...（LaTeX格式）",
  "reasoning_steps": [{"step_id": 1, "description": "...", "formula": "...", "method": "特征方程法/积分因子/..."}],
  "methods_used": ["特征方程法", "常数变易法"],
  "educational_hint": "解法选择理由/方程类型分析"
}""",
)
