# ============================================================
# graph/nodes/rag_node.py — RAG 知识检索节点
# ============================================================

from typing import Dict, Any, List
from loguru import logger


def rag_retrieval_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    RAG 知识检索节点

    根据分类领域和问题内容，检索相关定理、公式和例题。
    """
    logger.info(f"[RAG] 开始知识检索: {state['question_id']}")

    # 检查是否启用 RAG
    try:
        from configs.settings import get_config
        config = get_config()
        if not config.rag.enabled:
            logger.info("[RAG] RAG 已禁用，跳过检索")
            return {
                "retrieved_theorems": [],
                "retrieved_formulas": [],
                "retrieved_examples": [],
            }
    except Exception:
        pass

    domain = state.get("classified_domain", "")
    question_text = state.get("question_text", "")
    keywords = state.get("parsed_problem", {}).get("keywords", [])

    theorems, formulas, examples = [], [], []

    try:
        from rag.retriever import RAGRetriever
        retriever = RAGRetriever()

        theorems = retriever.search_theorems(domain, keywords, top_k=5)
        formulas = retriever.search_formulas(domain, keywords, top_k=5)
        examples = retriever.search_examples(domain, keywords, top_k=3)

        logger.info(f"[RAG] 检索完成: theorems={len(theorems)}, formulas={len(formulas)}, examples={len(examples)}")
    except ImportError:
        logger.info("[RAG] RAG 模块未安装，跳过知识检索")
    except Exception as e:
        logger.warning(f"[RAG] 检索异常: {e}")

    return {
        "retrieved_theorems": theorems,
        "retrieved_formulas": formulas,
        "retrieved_examples": examples,
    }
