# ============================================================
# api/schemas.py — FastAPI 接口 Pydantic Schema 定义
# ============================================================
from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


# ============================================================
# 问题相关
# ============================================================
class ProblemCreate(BaseModel):
    """创建问题请求"""
    question_text: str = Field(..., description="数学问题文本")
    domain: Optional[str] = Field(default="", description="数学领域 (可选)")
    difficulty: Optional[str] = Field(default="medium", description="难度: easy/medium/hard")
    tags: Optional[List[str]] = Field(default_factory=list, description="标签列表")


class ProblemUpdate(BaseModel):
    """更新问题请求"""
    question_text: Optional[str] = None
    domain: Optional[str] = None
    difficulty: Optional[str] = None
    status: Optional[str] = None
    tags: Optional[List[str]] = None


class ProblemItem(BaseModel):
    """问题列表项"""
    id: str
    question_text: str
    domain: str
    difficulty: str
    status: str  # pending / solved / failed
    created_at: str
    updated_at: Optional[str] = None


class ProblemDetail(ProblemItem):
    """问题详情"""
    final_answer: Optional[str] = None
    reasoning_steps: List[Dict[str, Any]] = Field(default_factory=list)
    methods_used: List[str] = Field(default_factory=list)
    verification: Optional[Dict[str, Any]] = None
    educational_hint: Optional[str] = None
    computation_time_ms: Optional[float] = None
    raw_output: Optional[Dict[str, Any]] = None


class ProblemListResponse(BaseModel):
    """问题列表响应"""
    total: int
    page: int
    page_size: int
    items: List[ProblemItem]


# ============================================================
# 求解相关
# ============================================================
class SolveRequest(BaseModel):
    """单题求解请求"""
    question: str = Field(..., min_length=1, description="数学问题文本")
    question_id: Optional[str] = Field(default=None, description="题目ID (可选)")
    max_retries: int = Field(default=3, ge=0, le=10, description="最大重试次数")
    enable_rag: bool = Field(default=True, description="启用RAG检索")


class SolveResponse(BaseModel):
    """求解响应（兼容比赛格式 + 前端详情）"""
    # 比赛标准字段
    idx: int = Field(default=0, description="题目编号")
    status: str = Field(default="success", description="状态: success/error")
    final_response: str = Field(default="", description="最终答案（比赛格式）")
    trace: List[Dict[str, Any]] = Field(default_factory=list, description="推理追踪（比赛格式）")
    error: Optional[Dict[str, str]] = Field(default=None, description="错误信息（失败时）")
    # 前端详情字段
    question_id: str = ""
    domain: str = ""
    final_answer: str = ""
    reasoning_steps: List[Dict[str, Any]] = Field(default_factory=list)
    methods_used: List[str] = Field(default_factory=list)
    verification: Dict[str, Any] = Field(default_factory=dict)
    educational_hint: str = ""
    computation_time_ms: float = 0.0
    retry_count: int = 0
    model_version: Optional[str] = None
    node_trace: List[str] = Field(default_factory=list)


class BatchSolveRequest(BaseModel):
    """批量求解请求"""
    questions: List[SolveRequest] = Field(..., min_length=1, max_length=200)
    parallel: bool = Field(default=False, description="是否并发求解")


# ============================================================
# 任务记录
# ============================================================
class TaskItem(BaseModel):
    """任务记录项"""
    task_id: str
    question_count: int
    status: str  # running / completed / failed
    solved_count: int
    failed_count: int
    avg_confidence: float
    total_time_ms: float
    model_name: str
    created_at: str
    completed_at: Optional[str] = None
    domain_distribution: Optional[Dict[str, int]] = None


class TaskListResponse(BaseModel):
    """任务列表响应"""
    total: int
    items: List[TaskItem]


class TaskDetail(BaseModel):
    """任务详情"""
    task_id: str
    question_count: int
    status: str
    solved_count: int
    failed_count: int
    avg_confidence: float
    total_time_ms: float
    model_name: str
    created_at: str
    completed_at: Optional[str] = None
    results: List[Dict[str, Any]] = Field(default_factory=list)
    logs: List[str] = Field(default_factory=list)


# ============================================================
# Benchmark
# ============================================================
class BenchmarkStartRequest(BaseModel):
    """启动Benchmark请求"""
    dataset_path: str = Field(default="./database/datasets/dev.jsonl", description="数据集路径")
    max_retries: int = Field(default=3)
    enable_rag: bool = Field(default=True)
    use_answer_db: bool = Field(default=True, description="是否使用正确答案库（命中则跳过LLM）")
    max_reflection_count: int = Field(default=1, ge=0, le=5, description="最大反思重试次数（0=快速模式，1-5=反思次数）")


class BenchmarkStatus(BaseModel):
    """Benchmark状态"""
    running: bool
    progress: int = 0
    total: int = 112
    solved: int = 0
    failed: int = 0
    elapsed_seconds: float = 0.0
    estimated_remaining_seconds: Optional[float] = None
    domain_accuracy: Dict[str, float] = Field(default_factory=dict)
    current_question: Optional[str] = None
    current_trace: List[str] = Field(default_factory=list)


class BenchmarkResult(BaseModel):
    """Benchmark结果"""
    total: int
    solved: int
    failed: int
    accuracy: float
    avg_confidence: float
    total_time_ms: float
    avg_time_per_question_ms: float
    domain_accuracy: Dict[str, float]
    results: List[Dict[str, Any]]
    charts: Optional[Dict[str, Any]] = None


# ============================================================
# Benchmark 历史记录
# ============================================================
class WrongQuestion(BaseModel):
    """错题记录"""
    question_id: str
    domain: str = ""
    predicted: str = ""
    ground_truth: str = ""
    time_ms: float = 0.0


class DomainStat(BaseModel):
    """单领域统计"""
    total: int = 0
    solved: int = 0
    accuracy: float = 0.0


class BenchmarkRunRecord(BaseModel):
    """单次评测完整记录"""
    run_id: str
    status: str  # "completed" | "interrupted" | "running"
    started_at: str
    completed_at: Optional[str] = None
    dataset: str = ""
    total: int = 0
    solved: int = 0
    failed: int = 0
    accuracy: float = 0.0
    avg_time_per_question_ms: float = 0.0
    total_time_ms: float = 0.0
    domain_stats: Dict[str, DomainStat] = Field(default_factory=dict)
    wrong_questions: List[WrongQuestion] = Field(default_factory=list)
    results: Optional[List[Dict[str, Any]]] = None


class BenchmarkRunSummary(BaseModel):
    """评测记录摘要（列表用，不含完整 results）"""
    run_id: str
    status: str
    started_at: str
    completed_at: Optional[str] = None
    total: int = 0
    solved: int = 0
    accuracy: float = 0.0
    total_time_ms: float = 0.0


# ============================================================
# 日志
# ============================================================
class LogEntry(BaseModel):
    """日志条目"""
    timestamp: str
    level: str  # DEBUG / INFO / WARNING / ERROR
    message: str
    source: Optional[str] = None


class LogsResponse(BaseModel):
    """日志响应"""
    total_lines: int
    lines: List[LogEntry]


# ============================================================
# 系统配置
# ============================================================
class SystemConfigModel(BaseModel):
    """系统配置模型"""
    api_base_url: str = Field(description="API基础地址")
    api_key: str = Field(description="API 密钥")
    model_name: str = Field(description="模型名称")
    temperature: float = Field(default=0.1, ge=0.0, le=2.0)
    max_tokens: int = Field(default=16384, ge=100, le=65536)
    max_reflection_count: int = Field(default=3, ge=0, le=10)
    enable_rag: bool = Field(default=True)
    solver_timeout: int = Field(default=300, ge=10, le=3600)
    top_p: float = Field(default=0.95, ge=0.0, le=1.0)


class ConfigUpdateRequest(BaseModel):
    """配置更新请求 (部分更新)"""
    api_base_url: Optional[str] = None
    api_key: Optional[str] = None
    model_name: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    max_reflection_count: Optional[int] = None
    enable_rag: Optional[bool] = None
    solver_timeout: Optional[int] = None
    top_p: Optional[float] = None


# ============================================================
# Dashboard 统计
# ============================================================
class DashboardStats(BaseModel):
    """首页统计"""
    total_problems: int
    solved_count: int
    failed_count: int
    avg_time_ms: float
    avg_accuracy: float
    current_model: str
    api_calls_today: int = 0
    tokens_used_today: int = 0
