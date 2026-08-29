"""Database retrieval node: fetch the top-k similar problems+solutions.

Runs before reasoning_agent and python_agent to provide reference examples.
轻量 TF-IDF 实现（utils.retrieval.TfidfRetriever），替代 ICMAnew 的 chroma 路径。
"""

from typing import Any, Dict

from config import CONFIG
from utils.deps import get_deps
from utils.logger import get_logger


def database_retrieval_node(state: Dict[str, Any], config: Dict) -> Dict[str, Any]:
    """查询题库，取 top-k 相似题+解答作为参考示例。

    k 来自 ``CONFIG["db_retrieval_top_k"]``（2）。每条检索结果注入推理与 Python
    两个子代理。

    Returns:
        Dict with 'retrieved_examples': List[Dict]，每项含 problem / solution /
        similarity / source / subject。
    """
    # 检索是纯增益节点：任何失败都必须降级为"无参考示例"，绝不能打断求解子图。
    # get_deps 曾在 try 之外——缺 deps 的配置会让整条子图记下 KeyError。
    try:
        deps = get_deps(config)
        logger = deps.logger or get_logger()
    except Exception:  # noqa: BLE001 - 配置形状是调用方的事，检索不为此失败。
        get_logger().warning("[db_retrieval] deps unavailable, skip")
        return {"retrieved_examples": []}

    problem = (state.get("problem") or "").strip()
    if not problem:
        logger.warning("[db_retrieval] empty problem, skip")
        return {"retrieved_examples": []}

    try:
        retriever = deps.retriever
        if retriever is None or not retriever.is_available():
            logger.warning("[db_retrieval] retriever not initialized, skip")
            return {"retrieved_examples": []}

        top_k = int(CONFIG.get("db_retrieval_top_k", 2) or 2)
        results = retriever.query(problem, top_k=top_k)
        examples = []
        for i, r in enumerate(results):
            examples.append({
                "problem": r.get("problem", ""),
                "solution": r.get("solution", ""),
                "similarity": r.get("similarity", 0.0),
                "source": r.get("source", ""),
                "subject": r.get("subject", ""),
            })
            logger.info(
                f"[db_retrieval] #{i + 1} sim={r.get('similarity', 0.0):.3f} "
                f"src={r.get('source', '')[:80]}"
            )

        logger.info(
            f"[db_retrieval] retrieved {len(examples)}/{top_k} examples, "
            f"injecting all into reasoning_agent and python_agent"
        )
        return {"retrieved_examples": examples}

    except Exception as exc:  # noqa: BLE001 - 检索失败降级为空，绝不打断求解
        logger.error(f"[db_retrieval] error: {exc!r}")
        return {"retrieved_examples": []}
