"""检索器降级链：向量库不可用时切到 TF-IDF，并记住这个决定。

为什么需要它（2026-09-09 实测）：评测环境只 clone 仓库、不执行 `git lfs pull`，
chroma.sqlite3（625MB）与 Qwen3-Embedding-0.6B 权重（1.2GB）在磁盘上都是 LFS
指针文本，向量检索必然不可用。而 DatabaseClient 在加载失败时不留下任何状态，
每次查询都会重试同一条注定失败的路径——本地实测成功加载约 10-12s/题，评测
环境则是把这笔开销白花 112 遍，且检索结果永远为空。

这里做两件事：
  1. 判定一次、永久降级（进程级熔断见 database_client._SHARED_FAILURE）；
  2. 降级后仍有产出：TF-IDF 检索器用 856KB 语料（不在 LFS，任何环境可跑）。

降级只换检索器，不换契约：两者都返回 problem/solution/similarity/source，
上层（database_retrieval 节点、reference_block、db_fallback）无需感知。

注意降级的能力边界：TF-IDF 的相似度尺度与 embedding 不同（本地实测留一
top-1 中位数 0.37，仅 18% 能越过 0.55 门控），所以多数题在降级后仍会得到
空参考——这是刻意的。宁可无参考，也不放松门控引入低相似度近邻：既有注释
已记录 sim≈0.44 的"路径计数"近邻把两分支同时带偏。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


class ResilientRetriever:
    """先用向量检索，首次失败即永久切到轻量检索器；两者都失败则返回空。"""

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
    """构造默认检索链：ChromaDB 向量检索 → TF-IDF 轻量检索。

    两个检索器都是惰性加载，构造本身不读磁盘，所以这里可以放心地一次性建好。
    """
    from utils.retrieval.database_client import DatabaseClient
    from utils.retrieval.tfidf_client import TfidfRetriever

    return ResilientRetriever(primary=DatabaseClient(), fallback=TfidfRetriever())
