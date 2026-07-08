# ============================================================
# solvers/skills/topology_skills.py — 拓扑学/微分几何/代数几何技能
# ============================================================

from agents.solver_experts.skills import SolverSkill

TOPOLOGY_SKILL = SolverSkill(
    skill_name="topology_skill",
    domain="topology",
    domain_cn="拓扑学/微分几何/代数几何",
    solver_name="topology_solver",

    system_prompt="""你是一位拓扑学和几何学专家，精通点集拓扑、代数拓扑、微分几何和代数几何。
求解策略：
1. 分析空间/流形的拓扑性质（紧致性、连通性、单连通性）
2. 选择合适的拓扑不变量：
   - 基本群 π₁：判断空间的单连通性
   - 同调群 H_n：计算Betti数和Euler示性数
   - Euler示性数 χ：多面体公式 V-E+F，Gauss-Bonnet定理
3. 对于微分几何问题：
   - 计算曲面的第一/第二基本形式
   - 计算Gauss曲率和平均曲率
   - 应用Gauss-Bonnet定理
4. 对于代数几何问题：
   - Hilbert零点定理、Bézout定理
5. 使用LaTeX格式书写所有数学公式""",

    strategies=[
        "基本群计算：利用Van Kampen定理、覆叠空间理论",
        "同调群计算：利用Mayer-Vietoris序列、切除定理",
        "Euler示性数：V-E+F公式，Gauss-Bonnet定理 χ(M)=(1/2π)∫_M K dA",
        "不动点定理：Brouwer不动点定理、Lefschetz不动点定理",
        "分类定理：闭曲面的分类（球面/环面/射影平面等）",
        "微分几何方法：标架法、活动标架法计算曲率",
        "纤维丛与示性类：陈类、Stiefel-Whitney类",
        "代数几何方法：消元法、Gröbner基、交截理论",
    ],

    keywords=[
        "拓扑", "topology", "同胚", "同伦", "基本群", "紧致",
        "同调", "Euler示性数", "Betti数", "流形",
        "微分几何", "differential geometry", "曲率", "Gauss",
        "测地线", "第一基本形式", "第二基本形式",
        "代数几何", "algebraic geometry", "Hilbert零点定理",
        "Bézout", "Riemann-Roch", "除子",
        "homotopy", "homeomorphism", "fundamental group", "manifold",
        "Gauss-Bonnet", "curvature", "geodesic",
    ],

    few_shot_examples=[
        {
            "problem": "证明 R²\\{0} 不是单连通的",
            "solution_steps": [
                {"step": 1, "description": "构造一个不能收缩的闭曲线（绕原点一圈）", "formula": "γ(t)=(cos(2πt), sin(2πt)), t∈[0,1]"},
                {"step": 2, "description": "证明不存在连续收缩映射", "formula": "若可收缩，则绕数为0，但实际绕数为1"},
                {"step": 3, "description": "结论：基本群非平凡", "formula": "π₁(R²\\{0}) ≅ Z ≠ 0"},
            ],
            "answer": "R²\\{0}的基本群为Z，不是单连通的",
            "method": "基本群/同伦论"
        },
    ],

    verification_strategy="拓扑不变性验证：不同计算方法得到的拓扑不变量应一致。几何验证：内蕴量与外蕴量的关系检查。代数验证：利用正合序列验证同调群关系。",

    json_output_hint="""{
  "final_answer": "结论/证明（LaTeX格式）",
  "reasoning_steps": [{"step_id": 1, "description": "...", "formula": "...", "method": "..."}],
  "methods_used": ["Van Kampen定理", "Gauss-Bonnet定理"],
  "educational_hint": "拓扑/几何概念的直观解释"
}""",
)
