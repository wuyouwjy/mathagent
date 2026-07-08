# ============================================================
# solvers/skills/algebra_skills.py — 代数/数论/群论/实分析技能
# ============================================================

from agents.solver_experts.skills import SolverSkill

ALGEBRA_SKILL = SolverSkill(
    skill_name="algebra_skill",
    domain="algebra",
    domain_cn="代数/数论/群论/实分析",
    solver_name="algebra_solver",

    system_prompt="""你是一位代数学/数论/实分析专家，精通抽象代数（群/环/域）、线性代数、数论和实分析。
求解策略：
1. 识别代数结构（群/环/域/向量空间）或分析对象（数列/函数/级数）
2. 应用相关定理（同构定理、Sylow定理、Cayley-Hamilton定理、中值定理、费马小定理等）
3. 进行计算或构造性证明，使用SymPy进行符号计算辅助
4. 验证结果满足所有条件
5. 使用LaTeX格式书写所有数学公式""",

    strategies=[
        "群论分析：确定群的类型和阶，分析子群和正规子群结构，应用群作用、Sylow定理",
        "环论/域论：分析理想结构、商环、扩域、Galois群",
        "线性代数：矩阵对角化、特征值计算、Jordan标准形、二次型",
        "方程求解：因式分解、求根公式、配方法、换元法",
        "多项式理论：因式分解、不可约性判定、Galois群",
        "数论方法：模运算、同余理论、二次互反律、丢番图方程",
        "实分析方法：ε-δ语言、极限计算、中值定理应用、级数收敛判定",
        "对称性分析：利用对称性化简、降维或构造不变量",
    ],

    keywords=[
        "代数", "群", "环", "域", "多项式", "因式分解", "特征值", "对角化",
        "线性变换", "向量空间", "子空间", "数论", "素数", "同余", "整除",
        "费马", "欧拉", "丢番图", "模运算", "极限", "连续", "导数",
        "积分", "级数", "收敛", "中值定理", "黎曼", "实分析",
        "algebra", "group", "ring", "field", "polynomial", "eigenvalue",
        "number theory", "prime", "congruence", "limit", "convergence",
        "derivative", "integral", "series", "real analysis",
    ],

    few_shot_examples=[
        {
            "problem": "求解 x^2 - 5x + 6 = 0",
            "solution_steps": [
                {"step": 1, "description": "因式分解", "formula": "x^2-5x+6=(x-2)(x-3)"},
                {"step": 2, "description": "令各因式为零求解", "formula": "x-2=0 或 x-3=0"},
            ],
            "answer": "x=2 或 x=3",
            "method": "因式分解法"
        },
        {
            "problem": "求矩阵 A=[[1,2],[3,4]] 的特征值",
            "solution_steps": [
                {"step": 1, "description": "构造特征方程", "formula": "|A-λI|=0"},
                {"step": 2, "description": "计算行列式并求解", "formula": "(1-λ)(4-λ)-6=0 → λ²-5λ-2=0 → λ=(5±√33)/2"},
            ],
            "answer": "λ=(5±√33)/2",
            "method": "特征方程法"
        },
    ],

    verification_strategy="代入验证：将答案代入原方程检验。结构验证：检查代数结构的封闭性、结合律等公理。数值验证：使用数值近似验证。",

    json_output_hint="""{
  "final_answer": "最终答案（LaTeX格式）",
  "reasoning_steps": [{"step_id": 1, "description": "...", "formula": "...", "method": "..."}],
  "methods_used": ["方法1", "方法2"],
  "educational_hint": "解题思路解释"
}""",
)
