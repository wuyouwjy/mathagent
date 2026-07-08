# ============================================================
# solvers/skills/combinatorics_skills.py — 组合数学技能
# ============================================================
from agents.solver_experts.skills import SolverSkill

COMBINATORICS_SKILL = SolverSkill(
    skill_name="combinatorics_skill", domain="combinatorics", domain_cn="组合数学/离散数学",
    solver_name="combinatorics_solver",
    system_prompt="""你是一位组合数学专家，精通计数理论、图论和组合设计。
求解策略：
1. 识别组合结构（集合/图/排列/组合/整数分拆）
2. 选择合适的计数方法（生成函数/递推关系/容斥原理/Burnside引理）
3. 对于图论问题使用树、平面图、匹配、着色等理论
4. 使用LaTeX格式书写所有数学公式""",
    strategies=[
        "鸽巢原理：n+1个物体放入n个盒子",
        "容斥原理：|∪A_i|=Σ|A_i|-Σ|A_i∩A_j|+...",
        "Burnside引理：群作用下的轨道计数",
        "生成函数：普通型/指数型生成函数",
        "递推关系：常系数线性递推的特征方程法",
        "图论基础：欧拉公式、树的性质、平面图判定",
        "Ramsey理论：R(s,t)的界和构造",
    ],
    keywords=[
        "组合", "combinatorics", "离散", "图论", "鸽巢", "容斥",
        "Burnside", "生成函数", "递推", "Ramsey", "欧拉公式",
        "平面图", "树", "匹配", "着色", "二项式系数",
        "graph", "pigeonhole", "generating function", "recurrence",
    ],
    few_shot_examples=[{
        "problem": "求包含5个0和5个1且任意前缀中0≥1的二进制序列数",
        "solution_steps": [
            {"step": 1, "description": "转化为Catalan数问题"},
            {"step": 2, "description": "C_5 = (1/6)·C(10,5) = 42"},
        ],
        "answer": "42", "method": "Catalan数"
    }],
    verification_strategy="计数验证：使用递推或生成函数双重计数验证。小型实例手工枚举验证。",
    json_output_hint='{"final_answer":"...","reasoning_steps":[...],"methods_used":[...],"educational_hint":"..."}',
)
