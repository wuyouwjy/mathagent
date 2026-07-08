# ============================================================
# solvers/skills/functional_analysis_skills.py — 泛函分析技能
# ============================================================
from agents.solver_experts.skills import SolverSkill

FUNCTIONAL_ANALYSIS_SKILL = SolverSkill(
    skill_name="functional_analysis_skill", domain="functional_analysis", domain_cn="泛函分析",
    solver_name="functional_analysis_solver",
    system_prompt="""你是一位泛函分析专家，精通Banach空间、Hilbert空间和算子理论。
求解策略：
1. 识别空间类型（Banach/Hilbert/赋范空间）和算子类型（有界/紧/自伴）
2. 应用四大基本定理：Hahn-Banach、Banach-Steinhaus、开映射定理、闭图像定理
3. 对Hilbert空间问题使用Riesz表示定理和正交投影
4. 使用LaTeX格式书写所有数学公式""",
    strategies=[
        "Hahn-Banach延拓：子空间上的线性泛函延拓到全空间",
        "一致有界原理（Banach-Steinhaus）：逐点有界蕴含一致有界",
        "开映射定理：满射有界线性算子为开映射",
        "闭图像定理：闭线性算子必连续",
        "Riesz表示定理：Hilbert空间上连续线性泛函由内积表示",
        "谱理论：紧自伴算子的谱分解",
        "弱收敛与弱*收敛分析",
    ],
    keywords=[
        "泛函分析", "functional analysis", "Banach", "Hilbert", "赋范空间",
        "有界算子", "紧算子", "谱理论", "Hahn-Banach", "Riesz表示",
        "开映射", "闭图像", "弱收敛", "对偶空间", "自伴算子",
    ],
    few_shot_examples=[{
        "problem": "证明 Hilbert 空间中的闭凸集上存在唯一的最小范数元素",
        "solution_steps": [
            {"step": 1, "description": "利用平行四边形法则证明极小化序列为Cauchy列"},
            {"step": 2, "description": "由完备性得极限存在，闭性保证极限在集合内"},
        ],
        "answer": "投影定理成立", "method": "平行四边形法则+完备性"
    }],
    verification_strategy="定理验证：检查是否满足定理前提条件。反例验证：尝试构造反例。算子范数验证。",
    json_output_hint='{"final_answer":"...","reasoning_steps":[...],"methods_used":[...],"educational_hint":"..."}',
)
