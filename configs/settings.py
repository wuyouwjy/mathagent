# ============================================================
# configs/settings.py — 全局配置管理
# 使用 dataclass 统一管理系统所有配置项
# 支持从环境变量 / .env 文件 / YAML 文件加载配置
# ============================================================

import os
from dataclasses import dataclass, field
from typing import Optional, Dict, Any


@dataclass
class InternS1Config:
    """
    Intern-S1 API 配置
    Intern-S1 兼容 OpenAI API 协议，可使用 openai 库调用
    """
    # --- API 连接 ---
    api_base_url: str = os.environ.get("INTERN_API_BASE", "https://chat.intern-ai.org.cn/api/v1/")
    api_key: str = os.environ.get("INTERN_API_KEY", "sk-OoOCMIh0NeMMY0h2kZvbHtokvdBEucb4VFgawNRUK0AJZrrv")
    model_name: str = os.environ.get("INTERN_MODEL", "intern-s2-preview")

    # --- 请求参数 ---
    temperature: float = 0.1                            # 温度（数学推理建议低温度 0.0-0.3）
    max_tokens: int = 16384                             # 最大输出 token 数（复杂推理需大上下文）
    top_p: float = 0.95                                 # nucleus sampling
    timeout: int = 120                                  # 请求超时（秒）
    max_retries: int = 3                                # 最大重试次数

    # --- 速率限制 ---
    requests_per_minute: int = 60                       # 每分钟最大请求数
    concurrent_requests: int = 10                       # 最大并发请求数


@dataclass
class SolverConfig:
    """Solver Agent 配置"""
    sympy_timeout: int = 30                             # SymPy 计算超时（秒）
    scipy_timeout: int = 60                             # SciPy 计算超时（秒）
    max_iterations: int = 1000                          # 数值计算最大迭代次数
    numeric_precision: int = 15                         # 数值计算精度（小数位数）
    use_numeric_fallback: bool = True                   # 符号计算失败时是否回退数值计算


@dataclass
class RAGConfig:
    """RAG 知识库配置"""
    enabled: bool = True                                # 是否启用 RAG
    theorem_db_path: str = "./rag/theorem_db"           # 定理库路径
    formula_db_path: str = "./rag/formula_db"           # 公式库路径
    example_db_path: str = "./rag/example_db"           # 示例题库路径
    embedding_model: str = "all-MiniLM-L6-v2"           # 嵌入模型名称
    top_k_retrieval: int = 5                            # 检索返回数
    similarity_threshold: float = 0.7                   # 相似度阈值


@dataclass
class WorkflowConfig:
    """LangGraph 工作流配置"""
    max_reflection_count: int = 3                       # 最大反思重试次数
    reflection_confidence_threshold: float = 0.7        # 触发反思的置信度阈值
    node_timeout_seconds: int = 300                     # 单个节点超时（秒）
    enable_parallel_solvers: bool = False               # 是否并行调用多个 Solver（实验性）


@dataclass
class PathsConfig:
    """路径配置"""
    project_root: str = field(default_factory=lambda: os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    datasets_dir: str = "./database/datasets"            # 数据集目录
    outputs_dir: str = "./outputs"                      # 输出结果目录
    logs_dir: str = "./outputs/logs"                    # 日志目录
    checkpoints_dir: str = "./outputs/checkpoints"      # LangGraph 检查点目录
    problem_db_path: str = "./database/problem_db.json" # 问题数据库路径


@dataclass
class MCPConfig:
    """MCP 服务器配置"""
    enabled: bool = True                                # 是否启用 MCP
    server_name: str = "Math-Agent-System"              # MCP 服务器名称
    server_version: str = "1.0.0"                       # 服务器版本
    mode: str = "stdio"                                 # 运行模式: stdio / interactive


@dataclass
class AgentConfig:
    """Agent 智能体配置"""
    classifier_rule_threshold: float = 0.9              # 规则分类置信度阈值（高于此值跳过LLM）
    max_similar_problems: int = 3                       # 相似问题最大检索数
    similarity_threshold: float = 0.7                   # 相似度阈值
    enable_alternative_solver: bool = True              # 是否启用备选Solver推荐


@dataclass
class SystemConfig:
    """
    系统总配置 — 聚合所有子配置
    用法:
        from configs.settings import get_config
        config = get_config()
        print(config.intern_s1.model_name)
    """
    intern_s1: InternS1Config = field(default_factory=InternS1Config)
    solver: SolverConfig = field(default_factory=SolverConfig)
    rag: RAGConfig = field(default_factory=RAGConfig)
    workflow: WorkflowConfig = field(default_factory=WorkflowConfig)
    paths: PathsConfig = field(default_factory=PathsConfig)
    mcp: MCPConfig = field(default_factory=MCPConfig)
    agent: AgentConfig = field(default_factory=AgentConfig)

    # --- 实验元数据 ---
    experiment_name: str = "math-agent-baseline"        # 实验名称
    experiment_version: str = "1.0.0"                   # 实验版本
    random_seed: int = 42                               # 随机种子（保证可复现）


# ============================================================
# 单例模式 — 全局配置访问
# ============================================================

_config_singleton: Optional[SystemConfig] = None


def get_config() -> SystemConfig:
    """
    获取全局配置单例

    首次调用时创建 SystemConfig 实例，后续调用返回同一实例。
    可通过环境变量覆盖部分配置。

    返回:
        SystemConfig: 系统配置对象
    """
    global _config_singleton
    if _config_singleton is None:
        _config_singleton = SystemConfig()
        _apply_env_overrides(_config_singleton)
    return _config_singleton


def _apply_env_overrides(config: SystemConfig) -> None:
    """
    应用环境变量覆盖配置

    支持的环境变量:
        INTERN_S1_API_KEY: API 密钥
        INTERN_S1_BASE_URL: API 基础地址
        INTERN_S1_MODEL: 模型名称
    """
    # API 配置覆盖
    if api_key := os.getenv("INTERN_S1_API_KEY"):
        config.intern_s1.api_key = api_key
    if base_url := os.getenv("INTERN_S1_BASE_URL"):
        config.intern_s1.api_base_url = base_url
    if model := os.getenv("INTERN_S1_MODEL"):
        config.intern_s1.model_name = model


def reset_config() -> None:
    """重置配置单例（测试用）"""
    global _config_singleton
    _config_singleton = None
