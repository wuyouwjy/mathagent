"""题库检索（RAG）。

主路径照 ICMAnew 用 ChromaDB 向量库（database_client.DatabaseClient），检索
27,984 条 AI-MO 竞赛题；向量库（chroma.sqlite3）与嵌入模型权重
（Qwen3-Embedding-0.6B）按 ICMAnew 的做法直接进项目目录、由 Git LFS 托管。
检索失败一律降级、不阻塞求解。

默认入口是 ResilientRetriever（resilient_client.build_resilient_retriever）：
向量库可用时走向量库；一旦确认不可用（2026-09-09：评测环境不执行
`git lfs pull`，chroma.sqlite3 是 LFS 指针）就永久降级到 TfidfRetriever
（856KB 语料，不在 LFS，任何环境可跑），不再每题重试加载。
"""

from utils.retrieval.reference_block import build_reference_block
from utils.retrieval.tfidf_client import TfidfRetriever
from utils.retrieval.database_client import DatabaseClient, RetrievalUnavailable
from utils.retrieval.resilient_client import (
    ResilientRetriever,
    build_resilient_retriever,
)

__all__ = [
    "build_reference_block",
    "build_resilient_retriever",
    "DatabaseClient",
    "ResilientRetriever",
    "RetrievalUnavailable",
    "TfidfRetriever",
]
