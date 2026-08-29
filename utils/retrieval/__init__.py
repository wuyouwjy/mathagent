"""题库检索（RAG）轻量实现。

ICMAnew 的差异化能力是"解题前检索相似竞赛题，把题面+解答作为 few-shot 参考
注入推理与验证两个子代理"。其 chroma + Qwen3-Embedding-0.6B 的实现依赖 Git LFS
模型权重与外部语料目录（E:/test/AI-MO），在评测环境不可复现。

本包用纯 sklearn 的 TF-IDF（char n-gram）替代向量检索，语料从比赛公开的
sample_data 离线提取为紧凑 JSON（data/retrieval_corpus.json），零新增依赖、
任何环境可跑，并完整保留 ICMAnew 的"反锚定"参考区块（防止近似题结论被误抄）。
"""

from utils.retrieval.reference_block import build_reference_block
from utils.retrieval.tfidf_client import TfidfRetriever

__all__ = ["build_reference_block", "TfidfRetriever"]
