"""题库检索（RAG）。

唯一检索路径是 TF-IDF 轻量检索（tfidf_client.TfidfRetriever），检索比赛公开
sample_data 提取的相似竞赛题；纯 scikit-learn 统计检索，零外部模型（比赛约束下
只能使用指定模型，原向量检索所依赖的外部嵌入模型已移除）。检索失败一律降级、
不阻塞求解。

默认入口是 ResilientRetriever（resilient_client.build_resilient_retriever）：
primary 恒为 None，query 直接走 TF-IDF；TF-IDF 也失败则返回空列表，绝不抛异常。
"""

from utils.retrieval.reference_block import build_reference_block
from utils.retrieval.tfidf_client import TfidfRetriever
from utils.retrieval.resilient_client import (
    ResilientRetriever,
    build_resilient_retriever,
)

__all__ = [
    "build_reference_block",
    "build_resilient_retriever",
    "ResilientRetriever",
    "TfidfRetriever",
]
