# ============================================================
# solvers/skills/__init__.py — Solver Skill 注册表
# 每个 Solver 通过 skill 获取领域专属的：
#   - 系统提示词 (system_prompt)
#   - 求解策略 (strategies)
#   - 领域关键词 (keywords)
#   - Few-shot 示例 (few_shot_examples)
#   - 验证策略 (verification_strategy)
# ============================================================

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class SolverSkill:
    """Solver 领域技能定义"""
    skill_name: str                                    # 技能名称
    domain: str                                        # 所属领域
    domain_cn: str                                     # 领域中文名
    solver_name: str                                   # 对应的 Solver 名称
    system_prompt: str                                 # 系统提示词模板
    strategies: List[str] = field(default_factory=list)  # 求解策略列表
    keywords: List[str] = field(default_factory=list)    # 领域关键词（快速匹配）
    few_shot_examples: List[Dict] = field(default_factory=list)  # Few-shot 示例
    verification_strategy: str = ""                    # 验证策略描述
    json_output_hint: str = ""                         # JSON 输出格式提示


# ============================================================
# Skill 注册表
# ============================================================

SKILL_REGISTRY: Dict[str, SolverSkill] = {}


def register_skill(skill: SolverSkill) -> None:
    """注册一个 Solver Skill"""
    SKILL_REGISTRY[skill.solver_name] = skill


def get_skill(solver_name: str) -> Optional[SolverSkill]:
    """根据 solver_name 获取对应 Skill"""
    return SKILL_REGISTRY.get(solver_name)


def list_all_skills() -> Dict[str, str]:
    """列出所有已注册的 Skill"""
    return {name: skill.domain_cn for name, skill in SKILL_REGISTRY.items()}


# ============================================================
# 导入并自动注册所有 Skill
# ============================================================

from agents.solver_experts.skills.algebra_skills import ALGEBRA_SKILL
from agents.solver_experts.skills.pde_skills import PDE_SKILL
from agents.solver_experts.skills.ode_skills import ODE_SKILL
from agents.solver_experts.skills.complex_analysis_skills import COMPLEX_ANALYSIS_SKILL
from agents.solver_experts.skills.topology_skills import TOPOLOGY_SKILL
from agents.solver_experts.skills.optimization_skills import OPTIMIZATION_SKILL
from agents.solver_experts.skills.real_analysis_skills import REAL_ANALYSIS_SKILL
from agents.solver_experts.skills.functional_analysis_skills import FUNCTIONAL_ANALYSIS_SKILL
from agents.solver_experts.skills.calculus_of_variations_skills import CALCULUS_OF_VARIATIONS_SKILL
from agents.solver_experts.skills.number_theory_skills import NUMBER_THEORY_SKILL
from agents.solver_experts.skills.group_theory_skills import GROUP_THEORY_SKILL
from agents.solver_experts.skills.differential_geometry_skills import DIFFERENTIAL_GEOMETRY_SKILL
from agents.solver_experts.skills.algebraic_geometry_skills import ALGEBRAIC_GEOMETRY_SKILL
from agents.solver_experts.skills.probability_skills import PROBABILITY_SKILL
from agents.solver_experts.skills.statistics_skills import STATISTICS_SKILL
from agents.solver_experts.skills.numerical_analysis_skills import NUMERICAL_ANALYSIS_SKILL
from agents.solver_experts.skills.combinatorics_skills import COMBINATORICS_SKILL
from agents.solver_experts.skills.mathematical_physics_skills import MATHEMATICAL_PHYSICS_SKILL

_all_skills = [
    ALGEBRA_SKILL, PDE_SKILL, ODE_SKILL, COMPLEX_ANALYSIS_SKILL,
    TOPOLOGY_SKILL, OPTIMIZATION_SKILL, REAL_ANALYSIS_SKILL,
    FUNCTIONAL_ANALYSIS_SKILL, CALCULUS_OF_VARIATIONS_SKILL,
    NUMBER_THEORY_SKILL, GROUP_THEORY_SKILL, DIFFERENTIAL_GEOMETRY_SKILL,
    ALGEBRAIC_GEOMETRY_SKILL, PROBABILITY_SKILL, STATISTICS_SKILL,
    NUMERICAL_ANALYSIS_SKILL, COMBINATORICS_SKILL, MATHEMATICAL_PHYSICS_SKILL,
]
for skill in _all_skills:
    register_skill(skill)
