# ============================================================
# solvers/skills/complex_analysis_skills.py — 复分析技能
# ============================================================

from agents.solver_experts.skills import SolverSkill

COMPLEX_ANALYSIS_SKILL = SolverSkill(
    skill_name="complex_analysis_skill",
    domain="complex_analysis",
    domain_cn="复分析",
    solver_name="complex_analysis_solver",

    system_prompt="""你是一位复分析专家，精通解析函数理论、围道积分和共形映射。
求解策略：
1. 分析函数的解析性和奇点类型（极点/本性奇点/支点）
2. 选择合适的积分方法：
   - 直接参数化路径积分
   - Cauchy积分公式及其导数形式
   - 留数定理（计算围道内奇点的留数之和）
   - 若尔当引理（处理无穷积分）
3. 使用SymPy计算留数、级数展开
4. 验证解析函数的Cauchy-Riemann方程
5. 使用LaTeX格式书写所有数学公式""",

    strategies=[
        "留数计算：确定奇点类型和阶数，按公式计算留数",
        "围道选择：根据积分区间选择合适围道（上半圆/矩形/扇形/钥匙孔围道）",
        "Cauchy积分公式：解析函数在区域内点的值由边界上的积分表示",
        "级数展开：Laurent级数展开，确定收敛半径和奇点性质",
        "共形映射：使用Möbius变换等将复杂区域映射为简单区域",
        "最大模原理：非常数解析函数在区域内取不到最大模",
        "辐角原理：计算零点与极点的个数差",
        "Riemann映射定理：单连通区域共形等价于单位圆盘",
    ],

    keywords=[
        "复分析", "complex analysis", "解析函数", "留数", "柯西",
        "Cauchy", "residue", "holomorphic", "亚纯函数", "辐角",
        "围道积分", "contour integral", "共形映射", "Laurent级数",
        "Riemann", "Liouville", "Schwarz", "Weierstrass",
        "柯西-黎曼", "Cauchy-Riemann", "最大模", "辐角原理",
    ],

    few_shot_examples=[
        {
            "problem": "计算围道积分 ∮_{|z|=2} z/(z²+1) dz",
            "solution_steps": [
                {"step": 1, "description": "确定奇点：z²+1=0 → z=±i，均在|z|=2内", "formula": "奇点: z=i, z=-i"},
                {"step": 2, "description": "计算留数 Res(f,i)", "formula": "Res(f,i)=lim_{z→i}(z-i)·z/(z²+1)=i/(2i)=1/2"},
                {"step": 3, "description": "计算留数 Res(f,-i)", "formula": "Res(f,-i)=lim_{z→-i}(z+i)·z/(z²+1)=-i/(-2i)=1/2"},
                {"step": 4, "description": "应用留数定理", "formula": "∮=2πi·(1/2+1/2)=2πi"},
            ],
            "answer": "2πi",
            "method": "留数定理"
        },
    ],

    verification_strategy="留数验证：由留数定理，结果应为2πi乘以留数之和。数值验证：参数化围道做数值积分对比。Cauchy-Riemann验证：检查实部和虚部满足C-R方程。",

    json_output_hint="""{
  "final_answer": "积分结果（LaTeX格式）",
  "reasoning_steps": [{"step_id": 1, "description": "...", "formula": "...", "method": "留数定理/Cauchy积分/..."}],
  "methods_used": ["留数定理", "Cauchy积分公式"],
  "educational_hint": "奇点分析和围道选择的解释"
}""",
)
