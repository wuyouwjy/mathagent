"""检索器统一入口：当前唯一检索路径是 TF-IDF（零外部模型）。

比赛约束下只能使用指定模型，原 ChromaDB 向量检索所依赖的外部嵌入模型已按要求
移除，故本系统的检索链只剩 TF-IDF 轻量检索（纯 scikit-learn 统计检索，856KB
语料，不在 LFS，任何环境可跑）。

ResilientRetriever 保留为统一接口：primary 恒为 None，query 直接走 fallback；
fallback 也失败时返回空列表，绝不抛异常。契约不变：返回 problem/solution/
similarity/source，上层（database_retrieval 节点、reference_block）无需感知。

降级能力边界：TF-IDF 相似度尺度与向量 embedding 不同（本地实测留一 top-1
中位数 0.37，仅 18% 能越过 0.55 门控），所以多数题得到空参考——这是刻意的。
宁可无参考，也不放松门控引入低相似度近邻。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


class ResilientRetriever:
    """统一检索接口：primary 恒为 None 时直接走 fallback；失败则返回空。"""

    def __init__(self, primary: Any = None, fallback: Any = None,
                 logger: Any = None) -> None:
        self._primary = primary
        self._fallback = fallback
        self._logger = logger
        self._primary_error: Optional[str] = None
        self._fallback_error: Optional[str] = None

    @property
    def primary_error(self) -> Optional[str]:
        """向量检索不可用的原因；仍可用时为 None。写入 trace 便于复盘。"""
        return self._primary_error

    def active(self) -> str:
        """当前生效的检索器名称，用于日志与 trace。"""
        if self._primary is not None:
            return "vector"
        return "tfidf" if self._fallback is not None else "none"

    def query(self, problem: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """返回 top-k 相似题；任何失败都降级为更轻的检索器，绝不抛异常。"""
        if self._primary is not None:
            try:
                return self._primary.query(problem, top_k=top_k)
            except Exception as exc:  # noqa: BLE001 - 检索是纯增益，失败即降级
                self._primary_error = f"{type(exc).__name__}: {exc}"
                self._primary = None
                self._log("[retrieval] vector retriever unavailable, "
                          f"falling back to TF-IDF: {self._primary_error}")
        if self._fallback is None:
            return []
        try:
            return self._fallback.query(problem, top_k=top_k)
        except Exception as exc:  # noqa: BLE001 - 兜底检索也失败则彻底放弃
            self._fallback_error = f"{type(exc).__name__}: {exc}"
            self._fallback = None
            self._log(f"[retrieval] fallback retriever failed: {self._fallback_error}")
            return []

    def _log(self, message: str) -> None:
        if self._logger is None:
            try:
                from utils.logger import get_logger

                self._logger = get_logger()
            except Exception:  # noqa: BLE001 - 日志不可用不影响检索降级
                return
        try:
            self._logger.warning(message)
        except Exception:  # noqa: BLE001
            pass


def build_resilient_retriever() -> ResilientRetriever:
    """构造默认检索链：当前只用 TF-IDF 轻量检索（零外部模型）。

    检索器惰性加载，构造本身不读磁盘，所以这里可以放心地一次性建好。
    """
    from utils.retrieval.tfidf_client import TfidfRetriever

    return ResilientRetriever(primary=None, fallback=TfidfRetriever())
