# ============================================================
# schemas/workflow_state.py — LangGraph Workflow State 定义
# 定义整个工作流中共享的状态对象，所有节点通过此对象通信
# ============================================================

from typing import TypedDict, List, Optional, Dict, Any, Annotated, Literal
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage
import operator


# ============================================================
# LangGraph 核心 Workflow State
# 使用 TypedDict + Annotated 定义每个字段的合并策略
# ============================================================

class WorkflowState(TypedDict):
    """
    LangGraph 工作流全局状态

    整个工作流中所有节点共享此状态对象。
    LangGraph 在节点间传递此 dict，并根据 Annotated 类型
    决定如何合并节点返回的部分状态更新。

    字段说明:
        - messages: LLM对话历史（累加合并）
        - question_text: 原始问题文本
        - parsed_problem: 解析后的结构化问题
        - classified_domain: 分类后的数学领域
        - solver_name: 路由选择的Solver名称
        - solver_output: Solver求解结果
        - verification_result: 验证结果
        - reflection_count: 反思重试计数
        - final_output: 最终JSON输出
        - error_info: 错误信息收集
    """

    # --- 对话历史（使用LangGraph内置的add_messages合并策略）---
    messages: Annotated[List[BaseMessage], add_messages]

    # --- 问题输入 ---
    question_id: str                              # 题目ID
    question_text: str                            # 原始问题文本
    question_type: str                            # 问题类型（proof / calculation / application）

    # --- 解析结果 ---
    parsed_problem: Dict[str, Any]                # 解析后的结构化问题（含提取的公式、条件等）

    # --- 分类结果 ---
    classified_domain: str                        # 分类得到的数学领域（18类之一）
    classification_confidence: float              # 分类置信度 (0.0 ~ 1.0)
    classification_reason: str                    # 分类理由

    # --- 路由信息 ---
    solver_name: str                              # 路由目标Solver名称
    solver_agent: str                             # Solver Agent 标识

    # --- RAG 检索结果 ---
    retrieved_theorems: List[str]                 # 检索到的相关定理
    retrieved_formulas: List[str]                 # 检索到的相关公式
    retrieved_examples: List[str]                 # 检索到的相似例题

    # --- Solver 求解结果 ---
    solver_output: Dict[str, Any]                 # Solver 输出（含推理步骤、答案等）
    solver_status: str                            # Solver 执行状态（success / failed / timeout）

    # --- 验证结果 ---
    verification_result: Dict[str, Any]           # 验证结果（is_correct, confidence, ...）
    verification_passed: bool                     # 是否通过验证

    # --- Reflection 重试机制 ---
    reflection_count: int                         # 当前重试次数
    max_reflection_count: int                     # 最大重试次数
    reflection_needed: bool                       # 是否需要反思重试
    reflection_feedback: str                      # 反思反馈信息

    # --- 最终输出 ---
    final_output: Dict[str, Any]                  # 最终JSON输出（符合MathSolutionOutput格式）
    computation_time_ms: float                    # 总计算耗时（毫秒）

    # --- 错误与日志 ---
    error_info: List[str]                         # 错误信息列表
    node_trace: List[str]                         # 节点执行轨迹（调试用）

    # --- 缓存相关 ---
    skip_cache: bool                              # 是否跳过缓存（benchmark模式）
    skip_cache_save: bool                         # 是否跳过缓存保存（benchmark模式由外部统一保存）
    cache_hit: bool                               # 是否命中缓存
    cache_similarity: float                       # 缓存命中相似度
    cache_matched_question: str                   # 缓存匹配到的问题


# ============================================================
# 初始状态工厂函数
# ============================================================

def create_initial_state(
    question_id: str,
    question_text: str,
    max_reflection_count: int = 3,
    skip_cache: bool = False,
    skip_cache_save: bool = False,
) -> WorkflowState:
    """
    创建初始工作流状态

    参数:
        question_id: 题目唯一ID
        question_text: 原始问题文本
        max_reflection_count: 最大反思重试次数，默认3次
        skip_cache: 是否跳过缓存检查（benchmark不使用答案库时设为True）
        skip_cache_save: 是否跳过缓存保存（benchmark使用答案库时设为True，由外部ground truth验证后保存）

    返回:
        WorkflowState: 初始化的状态字典
    """
    return WorkflowState(
        # 对话历史（空列表）
        messages=[],

        # 问题输入
        question_id=question_id,
        question_text=question_text,
        question_type="",

        # 解析结果
        parsed_problem={},

        # 分类结果
        classified_domain="",
        classification_confidence=0.0,
        classification_reason="",

        # 路由信息
        solver_name="",
        solver_agent="",

        # RAG
        retrieved_theorems=[],
        retrieved_formulas=[],
        retrieved_examples=[],

        # Solver 结果
        solver_output={},
        solver_status="pending",

        # 验证
        verification_result={},
        verification_passed=False,

        # Reflection
        reflection_count=0,
        max_reflection_count=max_reflection_count,
        reflection_needed=False,
        reflection_feedback="",

        # 最终输出
        final_output={},
        computation_time_ms=0.0,

        # 缓存
        skip_cache=skip_cache,
        skip_cache_save=skip_cache_save,
        cache_hit=False,
        cache_similarity=0.0,
        cache_matched_question="",

        # 错误与日志
        error_info=[],
        node_trace=[],
    )


# ============================================================
# 状态访问辅助函数
# ============================================================

def get_state_summary(state: WorkflowState) -> Dict[str, Any]:
    """
    获取状态摘要（用于日志和调试）
    不包含长文本/大字典的完整内容

    参数:
        state: 工作流状态

    返回:
        Dict: 状态摘要
    """
    return {
        "question_id": state.get("question_id", ""),
        "classified_domain": state.get("classified_domain", ""),
        "classification_confidence": state.get("classification_confidence", 0.0),
        "solver_name": state.get("solver_name", ""),
        "solver_status": state.get("solver_status", ""),
        "verification_passed": state.get("verification_passed", False),
        "reflection_count": state.get("reflection_count", 0),
        "computation_time_ms": state.get("computation_time_ms", 0.0),
        "error_count": len(state.get("error_info", [])),
        "node_trace": state.get("node_trace", []),
    }
