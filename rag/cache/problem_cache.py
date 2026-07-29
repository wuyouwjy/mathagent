# ============================================================
# cache/problem_cache.py — 问题缓存与知识积累系统
#
# 核心逻辑：
#   输入问题 → 计算向量 → 搜索缓存
#     ├─ 命中(相似度 ≥ 阈值) → 直接返回缓存结果（秒出）
#     └─ 未命中 → 走完整求解流程 → 结果自动入库
#
# 使用 ChromaDB + sentence-transformers 做语义相似度匹配
# ============================================================

import os
import json
import time
import hashlib
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from loguru import logger

from configs.settings import get_config


@dataclass
class CacheHitResult:
    """缓存命中结果"""
    is_hit: bool
    similarity: float           # 相似度 (0.0 ~ 1.0)
    matched_question: str        # 匹配到的缓存问题
    cached_solution: Optional[Dict[str, Any]] = None
    cache_age_seconds: float = 0  # 缓存年龄


class ProblemCache:
    """
    问题缓存系统

    用法:
        cache = ProblemCache()
        hit = cache.search("求解方程 x^2 - 5x + 6 = 0")
        if hit.is_hit:
            return hit.cached_solution   # 秒出
        else:
            result = solve(...)
            cache.save(question, result)  # 自动入库
    """

    def __init__(self, similarity_threshold: float = 0.92):
        """
        初始化缓存

        参数:
            similarity_threshold: 相似度阈值，≥此值视为命中
        """
        self.config = get_config()
        self.threshold = similarity_threshold
        self._collection = None
        self._embedder = None
        self._embedder_loaded = False  # 延迟加载标记
        self._stats = {"hits": 0, "misses": 0, "total_saved": 0}

        # 内存级精确缓存（用于完全相同的题目）— 无需嵌入模型，毫秒级
        self._exact_cache: Dict[str, Dict[str, Any]] = {}

        # ChromaDB 延迟初始化
        self._client = None
        self._db_ready = False

        logger.info(
            f"[Cache] 缓存就绪: threshold={self.threshold}, "
            f"exact_cache=内存级(毫秒), vector=延迟加载"
        )

    # ============================================================
    # 延迟初始化
    # ============================================================

    def _ensure_db(self) -> None:
        """延迟初始化 ChromaDB（首次使用时才加载）"""
        if self._db_ready:
            return
        try:
            import chromadb
            db_path = os.path.join(
                self.config.paths.project_root, "cache", "chroma_db"
            )
            self._client = chromadb.PersistentClient(path=db_path)
            self._collection = self._client.get_or_create_collection(
                "solved_problems",
                metadata={"hnsw:space": "cosine"}
            )
            self._db_ready = True
            logger.info(f"[Cache] ChromaDB 就绪, 已有 {self._collection.count()} 条")
        except ImportError:
            logger.warning("[Cache] chromadb 未安装，仅精确匹配")
        except Exception as e:
            logger.warning(f"[Cache] ChromaDB 失败: {e}")

    def _ensure_embedder(self) -> None:
        """延迟加载嵌入模型（首次向量搜索时才加载）"""
        if self._embedder_loaded:
            return
        try:
            import os as _os
            # 优先使用国内 HuggingFace 镜像
            if "HF_ENDPOINT" not in _os.environ:
                _os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
            from sentence_transformers import SentenceTransformer
            self._embedder = SentenceTransformer(self.config.rag.embedding_model)
            self._embedder_loaded = True
            logger.info(f"[Cache] 嵌入模型就绪: {self.config.rag.embedding_model}")
        except ImportError:
            logger.warning("[Cache] sentence-transformers 未安装")
        except Exception as e:
            logger.warning(f"[Cache] 嵌入模型加载失败: {e}")

    # ============================================================
    # 搜索缓存
    # ============================================================

    def search(self, question_text: str) -> CacheHitResult:
        """
        搜索缓存中是否有相似问题

        参数:
            question_text: 问题文本

        返回:
            CacheHitResult: 命中结果
        """
        # 第1层: 精确匹配（哈希）— 最快
        exact_key = self._hash_question(question_text)
        if exact_key in self._exact_cache:
            entry = self._exact_cache[exact_key]
            age = time.time() - entry["timestamp"]
            self._stats["hits"] += 1
            logger.info(f"[Cache] 精确命中! 缓存年龄: {age:.0f}s")
            return CacheHitResult(
                is_hit=True,
                similarity=1.0,
                matched_question=question_text,
                cached_solution=entry["solution"],
                cache_age_seconds=age,
            )

        # 第2层: 向量语义匹配（延迟加载）
        self._ensure_db()
        if self._collection is not None and self._collection.count() > 0:
            self._ensure_embedder()
            if self._embedder is not None:
                result = self._vector_search(question_text)
                if result and result.is_hit:
                    self._stats["hits"] += 1
                    return result

        self._stats["misses"] += 1
        return CacheHitResult(is_hit=False, similarity=0.0, matched_question="")

    def _vector_search(self, question_text: str) -> Optional[CacheHitResult]:
        """向量语义搜索"""
        try:
            query_embedding = self._embed_question(question_text)
            if query_embedding is None:
                return None

            results = self._collection.query(
                query_embeddings=[query_embedding],
                n_results=3,
                include=["documents", "metadatas", "distances"],
            )

            if not results["ids"] or not results["ids"][0]:
                return None

            # ChromaDB 返回的是距离(cosine distance)，转为相似度
            for i, doc_id in enumerate(results["ids"][0]):
                distance = results["distances"][0][i] if results["distances"] else 0
                similarity = 1.0 - distance  # cosine distance → similarity

                if similarity >= self.threshold:
                    matched_question = results["documents"][0][i]
                    metadata = results["metadatas"][0][i] if results["metadatas"] else {}
                    age = time.time() - metadata.get("timestamp", time.time())

                    # 从 metadata 重建 solution
                    cached_solution = {
                        "final_answer": metadata.get("final_answer", ""),
                        "domain": metadata.get("domain", ""),
                        "reasoning_steps": json.loads(metadata.get("reasoning_steps_json", "[]")),
                        "methods_used": json.loads(metadata.get("methods_used_json", "[]")),
                        "verification": json.loads(metadata.get("verification_json", "{}")),
                        "educational_hint": metadata.get("educational_hint", ""),
                        "from_cache": True,
                    }

                    logger.info(
                        f"[Cache] 语义命中! similarity={similarity:.4f}, "
                        f"matched='{matched_question[:50]}...', age={age:.0f}s"
                    )
                    return CacheHitResult(
                        is_hit=True,
                        similarity=similarity,
                        matched_question=matched_question,
                        cached_solution=cached_solution,
                        cache_age_seconds=age,
                    )

            # 记录最佳相似度（调试用）
            best_sim = 1.0 - results["distances"][0][0] if results["distances"] else 0
            logger.debug(f"[Cache] 未命中, 最佳相似度={best_sim:.4f} < threshold={self.threshold}")

        except Exception as e:
            logger.warning(f"[Cache] 向量搜索异常: {e}")

        return None

    # ============================================================
    # 保存到缓存
    # ============================================================

    def save(self, question_text: str, solution: Dict[str, Any]) -> None:
        """
        将求解结果保存到缓存

        参数:
            question_text: 问题文本
            solution: 完整的求解结果 (MathSolutionOutput dict)
        """
        now = time.time()

        # 精确缓存
        exact_key = self._hash_question(question_text)
        self._exact_cache[exact_key] = {
            "question": question_text,
            "solution": solution,
            "timestamp": now,
        }

        # 向量缓存（延迟加载）
        self._ensure_db()
        self._ensure_embedder()
        if self._collection is not None and self._embedder is not None:
            try:
                embedding = self._embed_question(question_text)
                if embedding is None:
                    return

                # 将复杂字段序列化
                reasoning_steps_json = json.dumps(
                    solution.get("reasoning_steps", []), ensure_ascii=False
                )
                methods_used_json = json.dumps(
                    solution.get("methods_used", []), ensure_ascii=False
                )
                verification_json = json.dumps(
                    solution.get("verification", {}), ensure_ascii=False
                )

                doc_id = hashlib.md5(question_text.encode()).hexdigest()[:16]

                # 如果已存在则更新
                existing = self._collection.get(ids=[doc_id])
                if existing and existing["ids"]:
                    self._collection.update(
                        ids=[doc_id],
                        embeddings=[embedding],
                        documents=[question_text],
                        metadatas=[{
                            "domain": solution.get("domain", ""),
                            "final_answer": solution.get("final_answer", ""),
                            "reasoning_steps_json": reasoning_steps_json,
                            "methods_used_json": methods_used_json,
                            "verification_json": verification_json,
                            "educational_hint": solution.get("educational_hint", ""),
                            "timestamp": now,
                        }],
                    )
                else:
                    self._collection.add(
                        ids=[doc_id],
                        embeddings=[embedding],
                        documents=[question_text],
                        metadatas=[{
                            "domain": solution.get("domain", ""),
                            "final_answer": solution.get("final_answer", ""),
                            "reasoning_steps_json": reasoning_steps_json,
                            "methods_used_json": methods_used_json,
                            "verification_json": verification_json,
                            "educational_hint": solution.get("educational_hint", ""),
                            "timestamp": now,
                        }],
                    )

                self._stats["total_saved"] += 1
                logger.info(
                    f"[Cache] 结果已入库: '{question_text[:50]}...' "
                    f"(domain={solution.get('domain')}, "
                    f"total={self._collection.count()})"
                )

            except Exception as e:
                logger.warning(f"[Cache] 向量缓存保存失败: {e}")

    # ============================================================
    # 嵌入计算
    # ============================================================

    def _embed_question(self, text: str) -> Optional[List[float]]:
        """计算问题文本的向量嵌入"""
        if self._embedder is None:
            return None
        try:
            embedding = self._embedder.encode(text, normalize_embeddings=True)
            return embedding.tolist()
        except Exception as e:
            logger.warning(f"[Cache] 嵌入计算失败: {e}")
            return None

    def _hash_question(self, text: str) -> str:
        """计算问题的精确哈希（归一化后）"""
        # 归一化：去空格、去标点差异
        normalized = "".join(text.split()).lower()
        return hashlib.md5(normalized.encode()).hexdigest()

    # ============================================================
    # 统计 & 管理
    # ============================================================

    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        stats = dict(self._stats)
        stats["exact_cache_size"] = len(self._exact_cache)
        self._ensure_db()
        if self._collection:
            stats["vector_cache_size"] = self._collection.count()
        else:
            stats["vector_cache_size"] = 0
        hit_total = stats["hits"] + stats["misses"]
        stats["hit_rate"] = stats["hits"] / max(hit_total, 1)
        return stats

    def clear(self) -> None:
        """清空所有缓存"""
        self._exact_cache.clear()
        self._ensure_db()
        if self._collection:
            try:
                all_ids = self._collection.get()["ids"]
                if all_ids:
                    self._collection.delete(ids=all_ids)
            except Exception:
                pass
        self._stats = {"hits": 0, "misses": 0, "total_saved": 0}
        logger.info("[Cache] 缓存已清空")

    def list_recent(self, n: int = 10) -> List[Dict[str, Any]]:
        """列出最近缓存的问题"""
        self._ensure_db()
        if not self._collection:
            return []
        try:
            results = self._collection.get(
                limit=n,
                include=["documents", "metadatas"],
            )
            entries = []
            for i, doc_id in enumerate(results.get("ids", [])):
                entries.append({
                    "id": doc_id,
                    "question": results["documents"][i][:80] if results.get("documents") else "",
                    "domain": results["metadatas"][i].get("domain", "") if results.get("metadatas") else "",
                })
            return entries
        except Exception:
            return []


# ============================================================
# 全局单例
# ============================================================

_global_cache: Optional[ProblemCache] = None


def get_cache() -> ProblemCache:
    """获取全局缓存单例"""
    global _global_cache
    if _global_cache is None:
        _global_cache = ProblemCache()
    return _global_cache


def reset_cache() -> None:
    """重置全局缓存"""
    global _global_cache
    _global_cache = None
