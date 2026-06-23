# ============================================================
# schemas/output_schema.py — 输出 JSON Schema 定义
# 定义系统最终输出的标准 JSON 结构（用于评分系统）
# ============================================================

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator, ConfigDict
from datetime import datetime
import uuid


# ============================================================
# 推理步骤子模型
# ============================================================

class ReasoningStep(BaseModel):
    """单个推理步骤"""
    step_id: int = Field(..., description="推理步骤序号（从1开始）")
    description: str = Field(..., description="该步骤的自然语言描述")
    formula: Optional[str] = Field(default=None, description="该步骤涉及的数学公式（LaTeX格式）")
    result: Optional[str] = Field(default=None, description="该步骤的中间结果")
    method: Optional[str] = Field(default=None, description="该步骤使用的方法/定理")


# ============================================================
# 验证结果子模型
# ============================================================

class VerificationResult(BaseModel):
    """验证结果"""
    is_correct: bool = Field(..., description="答案是否通过验证")
    confidence: float = Field(
        ...,
        ge=0.0,   # greater than or equal to 0.0
        le=1.0,   # less than or equal to 1.0
        description="置信度评分（0.0 ~ 1.0）"
    )
    check_method: Optional[str] = Field(default=None, description="验证方法（如代入检验、数值验证、符号验证）")
    error_details: Optional[str] = Field(default=None, description="若验证失败，记录错误详情")

    @field_validator("confidence")
    @classmethod
    def round_confidence(cls, v: float) -> float:
        """保留4位小数"""
        return round(v, 4)


# ============================================================
# 完整输出模型（竞赛评分用）
# ============================================================

class MathSolutionOutput(BaseModel):
    """
    标准数学求解输出 JSON Schema
    这是系统最终输出格式，直接用于竞赛评分
    """
    # --- 问题标识 ---
    question_id: str = Field(
        default_factory=lambda: str(uuid.uuid4())[:8],
        description="题目唯一ID"
    )
    timestamp: str = Field(
        default_factory=lambda: datetime.now().isoformat(),
        description="求解时间戳（ISO 8601）"
    )

    # --- 领域分类 ---
    domain: str = Field(..., description="所属数学领域（18类之一）")

    # --- 答案 ---
    final_answer: str = Field(..., description="最终答案（LaTeX格式）")

    # --- 推理过程 ---
    reasoning_steps: List[ReasoningStep] = Field(
        default_factory=list,
        description="逐步推理过程"
    )

    # --- 使用的方法 ---
    methods_used: List[str] = Field(
        default_factory=list,
        description="求解过程中使用的方法/定理列表"
    )

    # --- 验证 ---
    verification: VerificationResult = Field(
        ...,
        description="答案验证结果与置信度"
    )

    # --- 教育解释 ---
    educational_hint: str = Field(
        default="",
        description="教育性解释，帮助理解解题思路与相关知识"
    )

    # --- 元数据 ---
    computation_time_ms: Optional[float] = Field(
        default=None,
        description="总计算耗时（毫秒）"
    )
    retry_count: int = Field(
        default=0,
        description="重试次数（来自Reflection循环）"
    )
    model_version: Optional[str] = Field(
        default=None,
        description="使用的LLM模型版本"
    )

    # --- 缓存 & 评分扩展字段 ---
    from_cache: bool = Field(default=False, description="是否来自缓存")
    cache_similarity: Optional[float] = Field(default=None, description="缓存命中相似度")
    cache_matched_question: Optional[str] = Field(default=None, description="缓存匹配到的问题")
    true_domain: Optional[str] = Field(default=None, description="真实领域标签")
    ground_truth: Optional[str] = Field(default=None, description="标准答案")
    answer_match: Optional[bool] = Field(default=None, description="与标准答案是否匹配")

    model_config = ConfigDict(
        extra="allow",  # 允许额外字段透传（评估结果、来源等）
        json_schema_extra={
            "example": {
                "question_id": "abc12345",
                "domain": "partial_differential_equations",
                "final_answer": "u(x,t) = e^{-\\pi^2 t} \\sin(\\pi x)",
                "reasoning_steps": [
                    {
                        "step_id": 1,
                        "description": "使用分离变量法，设 u(x,t) = X(x)T(t)",
                        "formula": "u(x,t) = X(x)T(t)",
                        "method": "分离变量法"
                    }
                ],
                "methods_used": ["分离变量法", "傅里叶级数"],
                "verification": {
                    "is_correct": True,
                    "confidence": 0.95,
                    "check_method": "代入原方程验证"
                },
                "educational_hint": "本问题使用分离变量法..."
            }
        }
    )


# ============================================================
# 批量评估结果汇总
# ============================================================

class BatchEvaluationSummary(BaseModel):
    """112道题批量评估结果汇总"""
    total_questions: int = Field(..., description="总题目数")
    solved_count: int = Field(..., description="成功求解数")
    failed_count: int = Field(..., description="失败数")
    avg_confidence: float = Field(..., description="平均置信度")
    domain_accuracy: Dict[str, float] = Field(
        default_factory=dict,
        description="各领域准确率分布"
    )
    total_time_ms: float = Field(..., description="总耗时（毫秒）")
    avg_time_per_question_ms: float = Field(..., description="每题平均耗时（毫秒）")
    results: List[MathSolutionOutput] = Field(
        default_factory=list,
        description="所有题目求解结果"
    )
