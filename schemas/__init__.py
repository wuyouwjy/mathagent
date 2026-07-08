# schemas/__init__.py
# 数据模型 & Schema 定义模块
# 包含：Workflow State、输出 JSON Schema、数学领域分类枚举
# 同时作为业务实体模型的统一入口（替代原 models/）

from schemas.math_domains import (
    MathDomain, DOMAIN_TO_SOLVER, DOMAIN_CN_NAME,
    get_solver_for_domain, list_all_domains, SOLVER_PRIORITY
)
from schemas.output_schema import (
    MathSolutionOutput, ReasoningStep, VerificationResult,
    BatchEvaluationSummary
)
from schemas.workflow_state import (
    WorkflowState, create_initial_state, get_state_summary
)
