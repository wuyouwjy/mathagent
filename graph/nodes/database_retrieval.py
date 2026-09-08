"""Database retrieval node: fetch the top-k similar problems+solutions.

Runs before reasoning_agent and python_agent to provide reference examples.
ChromaDB 向量检索（utils.retrieval.database_client.DatabaseClient），照 ICMAnew 的 chroma 路径复现。
"""

from typing import Any, Dict

from config import CONFIG
from utils.deps import get_deps
from utils.logger import get_logger
from utils.retrieval.reference_block import partition_reference_examples


def _empty_retrieval_result() -> Dict[str, Any]:
    """检索不可用时返回完整的分支契约（空分区）。"""
    partition = partition_reference_examples([])
    return {
        "retrieved_examples": [],
        "reasoning_references": partition["reasoning"],
        "python_references": partition["python"],
        "reference_partition": partition,
    }


def database_retrieval_node(state: Dict[str, Any], config: Dict) -> Dict[str, Any]:
    """查询题库，取 top-k 相似题+解答作为参考示例。

    k 来自 ``CONFIG["db_retrieval_top_k"]``（2）。每条检索结果按秩奇偶分流注入
    推理（带解答）与 Python（解答抑制）两个子代理，防两分支锚定同一份带答案的
    示例。

    Returns:
        Dict with 'retrieved_examples' / 'reasoning_references' /
        'python_references' / 'reference_partition'。
    """
    # 检索是纯增益节点：任何失败都必须降级为"无参考示例"，绝不能打断求解子图。
    # get_deps 曾在 try 之外——缺 deps 的配置会让整条子图记下 KeyError。
    try:
        deps = get_deps(config)
        logger = deps.logger or get_logger()
    except Exception:  # noqa: BLE001 - 配置形状是调用方的事，检索不为此失败。
        get_logger().warning("[db_retrieval] deps unavailable, skip")
        return _empty_retrieval_result()

    problem = (state.get("problem") or "").strip()
    if not problem:
        logger.warning("[db_retrieval] empty problem, skip")
        return _empty_retrieval_result()

    try:
        retriever = deps.retriever
        if retriever is None:
            logger.warning("[db_retrieval] retriever not initialized, skip")
            return _empty_retrieval_result()

        top_k = int(CONFIG.get("db_retrieval_top_k", 2) or 2)
        results = retriever.query(problem, top_k=top_k)
        # 相似度门控（ICMAnew 评委意见改进点 1）：低于阈值的近邻与本题结构相差
        # 过大（实测 sim≈0.44 的"路径计数"近邻把两分支同时带偏），注入的误导风险
        # 高于方法参考价值——不足即弃，宁缺毋滥。
        min_sim = float(CONFIG.get("db_reference_min_similarity", 0.55) or 0.0)
        dropped = []
        examples = []
        for i, r in enumerate(results):
            sim = float(r.get("similarity", 0.0) or 0.0)
            if sim < min_sim:
                dropped.append((i + 1, round(sim, 3), str(r.get("source", ""))[:60]))
                continue
            examples.append({
                "problem": r.get("problem", ""),
                "solution": r.get("solution", ""),
                "similarity": sim,
                "source": r.get("source", ""),
            })
            logger.info(
                f"[db_retrieval] #{i+1} sim={sim:.3f} "
                f"src={r.get('source', '')[:80]}"
            )
        for rank, sim, src in dropped:
            logger.info(f"[db_retrieval] dropped #{rank} sim={sim:.3f} below {min_sim} src={src}")

        partition = partition_reference_examples(examples)
        logger.info(
            f"[db_retrieval] retrieved {len(examples)}/{top_k} examples; "
            f"reasoning={len(partition['reasoning'])}, "
            f"python={len(partition['python'])} (solution text suppressed)"
        )
        return {
            "retrieved_examples": examples,
            "reasoning_references": partition["reasoning"],
            "python_references": partition["python"],
            "reference_partition": partition,
        }

    except Exception as exc:  # noqa: BLE001 - 检索失败降级为空，绝不打断求解
        logger.error(f"[db_retrieval] error: {exc!r}")
        return _empty_retrieval_result()
