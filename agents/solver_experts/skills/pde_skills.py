# ============================================================
# solvers/skills/pde_skills.py — 偏微分方程 + 数学物理技能
# ============================================================

from agents.solver_experts.skills import SolverSkill

PDE_SKILL = SolverSkill(
    skill_name="pde_skill",
    domain="partial_differential_equations",
    domain_cn="偏微分方程/数学物理",
    solver_name="pde_solver",

    system_prompt="""你是一位偏微分方程（PDE）和数学物理专家。
求解策略：
1. 识别PDE类型（椭圆型/抛物型/双曲型）及定解条件（初值/边值/混合）
2. 选择合适的解法：
   - 椭圆型：分离变量法、格林函数法、傅里叶级数展开
   - 抛物型：分离变量法、傅里叶变换、特征函数展开、Duhamel原理
   - 双曲型：特征线法、达朗贝尔解法、分离变量法、行波法
3. 使用SymPy进行符号计算（分离变量、特征值问题、级数展开）
4. 验证解满足方程和边界条件
5. 使用LaTeX格式书写所有数学公式""",

    strategies=[
        "分离变量法：设 u(x,t)=X(x)T(t) 将PDE化为ODE组",
        "傅里叶变换法：对空间变量做傅里叶变换，将PDE化为代数方程",
        "格林函数法：构造格林函数，解表示为G(x,ξ)与源项的卷积",
        "特征线法：沿特征线将一阶PDE化为ODE求解",
        "Duhamel原理：将非齐次问题转化为齐次问题的叠加",
        "能量估计法：证明解的适定性（存在性、唯一性、稳定性）",
        "最大模原理：椭圆型PDE的解在边界上取最大值",
        "变分方法：将PDE转化为能量泛函的极小化问题",
    ],

    keywords=[
        "偏微分", "PDE", "partial differential", "波动方程", "热传导",
        "拉普拉斯方程", "泊松方程", "椭圆型", "抛物型", "双曲型",
        "分离变量", "傅里叶变换", "格林函数", "特征线", "行波",
        "wave equation", "heat equation", "Laplace", "Poisson",
        "separation of variables", "Fourier transform", "Green function",
        "数学物理", "Navier-Stokes", "Maxwell", "Schrödinger",
    ],

    few_shot_examples=[
        {
            "problem": "求解一维热传导方程 ∂u/∂t = ∂²u/∂x², u(0,t)=u(1,t)=0, u(x,0)=sin(πx)",
            "solution_steps": [
                {"step": 1, "description": "设 u(x,t)=X(x)T(t), 分离变量", "formula": "X''/X = T'/T = -λ"},
                {"step": 2, "description": "解X的边值问题", "formula": "X''+λX=0, X(0)=X(1)=0 → λ_n=n²π², X_n=sin(nπx)"},
                {"step": 3, "description": "解T的ODE", "formula": "T'=-λT → T_n=e^{-n²π²t}"},
                {"step": 4, "description": "叠加并由初值确定系数", "formula": "u(x,0)=ΣA_n sin(nπx)=sin(πx) → A_1=1, 其余为0"},
            ],
            "answer": "u(x,t)=e^{-π²t}sin(πx)",
            "method": "分离变量法"
        },
    ],

    verification_strategy="代入验证：将解代入原PDE检查。边界验证：检验是否满足所有边界条件。初值验证：检验t=0时是否等于给定初值。唯一性检查：验证是否满足适定性条件。",

    json_output_hint="""{
  "final_answer": "u(x,t)=...（LaTeX格式）",
  "reasoning_steps": [{"step_id": 1, "description": "...", "formula": "...", "method": "分离变量法/傅里叶变换/..."}],
  "methods_used": ["分离变量法", "傅里叶级数"],
  "educational_hint": "方程类型/解法选择的解释"
}""",
)
