# ============================================================
# solvers/skills/group_theory_skills.py — 群论技能
# ============================================================
from agents.solver_experts.skills import SolverSkill

GROUP_THEORY_SKILL = SolverSkill(
    skill_name="group_theory_skill", domain="group_theory", domain_cn="群论",
    solver_name="group_theory_solver",
    system_prompt="""你是一位群论专家，精通有限群论、表示论和群作用理论。
求解策略：
1. 确定群的类型和阶，分析群的结构
2. 应用Sylow定理分析p-子群
3. 使用群作用和轨道-稳定子定理
4. 应用同构定理和Jordan-Hölder定理
5. 使用LaTeX格式书写所有数学公式""",
    strategies=[
        "Sylow定理：Sylow p-子群的存在性、共轭性和数量",
        "群作用：轨道-稳定子定理、Burnside引理",
        "同构定理：第一/第二/第三同构定理",
        "Jordan-Hölder定理：合成列因子在同构意义下唯一",
        "有限生成Abel群分类定理",
        "Cayley定理与置换群表示",
        "半直积与群扩张",
    ],
    keywords=[
        "群论", "group theory", "子群", "正规子群", "Sylow", "同构",
        "群作用", "轨道", "稳定子", "Burnside", "Jordan-Hölder",
        "Abel群", "半直积", "表示论", "特征标",
        "subgroup", "normal", "homomorphism", "automorphism",
    ],
    few_shot_examples=[{
        "problem": "证明60阶单群同构于A_5",
        "solution_steps": [
            {"step": 1, "description": "利用Sylow定理分析Sylow子群数量"},
            {"step": 2, "description": "构造群在Sylow子群集合上的作用"},
            {"step": 3, "description": "证明同构于A_5"},
        ],
        "answer": "G ≅ A_5", "method": "Sylow定理+群作用"
    }],
    verification_strategy="结构验证：检查子群的阶和指数。Lagrange定理验证：子群阶整除群阶。同态验证。",
    json_output_hint='{"final_answer":"...","reasoning_steps":[...],"methods_used":[...],"educational_hint":"..."}',
)
