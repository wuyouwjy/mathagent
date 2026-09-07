"""题库检索（RAG）。

主路径照 ICMAnew 用 ChromaDB 向量库（database_client.DatabaseClient），检索
27,984 条 AI-MO 竞赛题；向量库（chroma.sqlite3）与嵌入模型权重
（Qwen3-Embedding-0.6B）按 ICMAnew 的做法直接进项目目录、由 Git LFS 托管，
模型另有 ModelScope 在线下载兜底，检索失败一律降级为空、不阻塞求解。

TfidfRetriever 保留为无 LFS 环境的轻量替代（840KB 语料，任何环境可跑），
默认不再启用。
"""

from utils.retrieval.reference_block import build_reference_block
from utils.retrieval.tfidf_client import TfidfRetriever
from utils.retrieval.database_client import DatabaseClient

__all__ = ["build_reference_block", "DatabaseClient", "TfidfRetriever"]
