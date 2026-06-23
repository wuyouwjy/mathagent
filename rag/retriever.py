# ============================================================
# rag/retriever.py — RAG 检索器
# 统一的定理/公式/例题向量检索接口
# 使用 ChromaDB 作为轻量级向量数据库
# ============================================================

import os
from typing import List, Dict, Optional
from loguru import logger

from configs.settings import get_config


class RAGRetriever:
    """
    RAG 知识检索器

    管理三个知识库的检索：
    1. 定理库 (theorem_db) — 数学定理
    2. 公式库 (formula_db) — 数学公式
    3. 示例题库 (example_db) — 相似例题

    用法:
        retriever = RAGRetriever()
        theorems = retriever.search_theorems("algebra", ["群", "正规子群"])
        formulas = retriever.search_formulas("algebra", ["群", "正规子群"])
        examples = retriever.search_examples("algebra", ["群", "正规子群"])
    """

    def __init__(self):
        """初始化检索器"""
        self.config = get_config()
        self.enabled = self.config.rag.enabled

        if not self.enabled:
            logger.info("[RAG] 检索器已禁用")
            self._collections_available = False
            return

        # 尝试初始化 ChromaDB
        self._collections_available = False
        try:
            import chromadb
            self._client = chromadb.PersistentClient(
                path=os.path.join(self.config.paths.project_root, "rag", "chroma_db")
            )
            self._init_collections()
            logger.info("[RAG] ChromaDB 检索器已初始化")
        except ImportError:
            logger.warning("[RAG] chromadb 未安装，使用基于关键词的简单检索")
        except Exception as e:
            logger.warning(f"[RAG] ChromaDB 初始化失败: {e}，使用简单检索")

    def _init_collections(self):
        """初始化向量集合"""
        try:
            self._theorem_collection = self._client.get_or_create_collection("theorems")
            self._formula_collection = self._client.get_or_create_collection("formulas")
            self._example_collection = self._client.get_or_create_collection("examples")
            self._collections_available = True
        except Exception as e:
            logger.warning(f"[RAG] 集合初始化失败: {e}")

    # ============================================================
    # 检索接口
    # ============================================================

    def search_theorems(
        self,
        domain: str,
        keywords: List[str],
        top_k: int = 5,
    ) -> List[str]:
        """
        检索相关定理

        参数:
            domain: 数学领域
            keywords: 关键词列表
            top_k: 返回数量

        返回:
            List[str]: 定理文本列表
        """
        if not self.enabled:
            return []

        query = f"{domain} {' '.join(keywords)}"

        if self._collections_available:
            try:
                results = self._theorem_collection.query(
                    query_texts=[query],
                    n_results=top_k,
                )
                return results.get("documents", [[]])[0] if results.get("documents") else []
            except Exception:
                pass

        # 回退：基于内置定理库的简单关键词匹配
        return self._keyword_search_theorems(domain, keywords, top_k)

    def search_formulas(
        self,
        domain: str,
        keywords: List[str],
        top_k: int = 5,
    ) -> List[str]:
        """
        检索相关公式

        参数:
            domain: 数学领域
            keywords: 关键词列表
            top_k: 返回数量

        返回:
            List[str]: 公式文本列表（LaTeX格式）
        """
        if not self.enabled:
            return []

        query = f"{domain} {' '.join(keywords)}"

        if self._collections_available:
            try:
                results = self._formula_collection.query(
                    query_texts=[query],
                    n_results=top_k,
                )
                return results.get("documents", [[]])[0] if results.get("documents") else []
            except Exception:
                pass

        return self._keyword_search_formulas(domain, keywords, top_k)

    def search_examples(
        self,
        domain: str,
        keywords: List[str],
        top_k: int = 3,
    ) -> List[str]:
        """
        检索相似例题

        参数:
            domain: 数学领域
            keywords: 关键词列表
            top_k: 返回数量

        返回:
            List[str]: 例题文本列表
        """
        if not self.enabled:
            return []

        query = f"{domain} {' '.join(keywords)}"

        if self._collections_available:
            try:
                results = self._example_collection.query(
                    query_texts=[query],
                    n_results=top_k,
                )
                return results.get("documents", [[]])[0] if results.get("documents") else []
            except Exception:
                pass

        return self._keyword_search_examples(domain, keywords, top_k)

    # ============================================================
    # 内置关键词检索（无需向量数据库的回退方案）
    # ============================================================

    def _keyword_search_theorems(
        self, domain: str, keywords: List[str], top_k: int
    ) -> List[str]:
        """基于关键词的定理检索"""
        from rag.theorem_db import THEOREM_DB
        return self._simple_match(THEOREM_DB.get(domain, []), keywords, top_k)

    def _keyword_search_formulas(
        self, domain: str, keywords: List[str], top_k: int
    ) -> List[str]:
        """基于关键词的公式检索"""
        from rag.formula_db import FORMULA_DB
        return self._simple_match(FORMULA_DB.get(domain, []), keywords, top_k)

    def _keyword_search_examples(
        self, domain: str, keywords: List[str], top_k: int
    ) -> List[str]:
        """基于关键词的例题检索"""
        from rag.example_db import EXAMPLE_DB
        return self._simple_match(EXAMPLE_DB.get(domain, []), keywords, top_k)

    def _simple_match(
        self, items: List[str], keywords: List[str], top_k: int
    ) -> List[str]:
        """简单关键词匹配"""
        if not keywords or not items:
            return items[:top_k]

        scored = []
        for item in items:
            item_lower = item.lower()
            score = sum(1 for kw in keywords if kw.lower() in item_lower)
            if score > 0:
                scored.append((score, item))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [item for _, item in scored[:top_k]]

    # ============================================================
    # 知识库管理
    # ============================================================

    def add_theorem(self, domain: str, theorem_text: str) -> None:
        """添加定理到知识库"""
        if self._collections_available:
            try:
                self._theorem_collection.add(
                    documents=[theorem_text],
                    metadatas=[{"domain": domain}],
                    ids=[f"thm_{domain}_{self._theorem_collection.count()}"],
                )
            except Exception as e:
                logger.warning(f"[RAG] 添加定理失败: {e}")

    def add_formula(self, domain: str, formula_text: str) -> None:
        """添加公式到知识库"""
        if self._collections_available:
            try:
                self._formula_collection.add(
                    documents=[formula_text],
                    metadatas=[{"domain": domain}],
                    ids=[f"fml_{domain}_{self._formula_collection.count()}"],
                )
            except Exception as e:
                logger.warning(f"[RAG] 添加公式失败: {e}")

    def get_stats(self) -> Dict[str, int]:
        """获取知识库统计"""
        if self._collections_available:
            try:
                return {
                    "theorems": self._theorem_collection.count(),
                    "formulas": self._formula_collection.count(),
                    "examples": self._example_collection.count(),
                }
            except Exception:
                pass
        return {"theorems": 0, "formulas": 0, "examples": 0}
