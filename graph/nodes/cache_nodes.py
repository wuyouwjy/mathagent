# ============================================================
# graph/nodes/cache_nodes.py — 缓存检查 & 缓存保存节点
# ============================================================

from typing import Dict, Any
from loguru import logger


def cache_check_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    缓存检查节点 — 工作流第一步

    检查是否有相同或相似问题已求解过。
    命中 → 直接跳到 formatter
    未命中 → 继续完整流程

    benchmark 模式（skip_cache=True）下跳过缓存检查。
    """
    # benchmark 模式：跳过缓存，强制重新求解
    if state.get("skip_cache", False):
        logger.info(f"[Cache] skip_cache=True，跳过缓存检查")
        return {"cache_hit": False}

    question_text = state.get("question_text", "")
    question_id = state.get("question_id", "")

    logger.info(f"[Cache] 检查缓存: {question_id}")

    try:
        from rag.cache.problem_cache import get_cache
        cache = get_cache()
        hit = cache.search(question_text)

        if hit.is_hit and hit.cached_solution:
            cached = hit.cached_solution

            # 只有经过 ground_truth 验证正确的答案才能从数据库读取
            cached_verification = cached.get("verification", {})
            is_verified_correct = (
                cached_verification.get("check_method") == "ground_truth_match"
                and cached_verification.get("is_correct") is True
            )
            if not is_verified_correct:
                logger.info(
                    f"[Cache] 缓存条目未经过 ground_truth 验证，跳过 "
                    f"(check_method={cached_verification.get('check_method')}, "
                    f"is_correct={cached_verification.get('is_correct')})"
                )
                return {"cache_hit": False}

            logger.info(
                f"[Cache] 命中! similarity={hit.similarity:.4f}, "
                f"matched='{hit.matched_question[:60]}...'"
            )
            if "question_id" not in cached:
                cached["question_id"] = question_id
            cached["from_cache"] = True
            cached["cache_similarity"] = hit.similarity
            cached["cache_matched_question"] = hit.matched_question

            return {
                "final_output": cached,
                "classified_domain": cached.get("domain", ""),
                "verification_passed": cached.get("verification", {}).get("is_correct", True),
                "node_trace": state.get("node_trace", []) + [f"cache_hit(sim={hit.similarity:.3f})"],
                "cache_hit": True,
            }
        else:
            stats = cache.get_stats()
            logger.info(f"[Cache] 未命中 (已有{stats['vector_cache_size']}条缓存, 命中率{stats['hit_rate']:.1%})")
            return {"cache_hit": False}

    except ImportError:
        logger.debug("[Cache] 缓存模块未加载，跳过")
        return {"cache_hit": False}
    except Exception as e:
        logger.warning(f"[Cache] 缓存检查异常: {e}")
        return {"cache_hit": False}


def cache_save_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    缓存保存节点 — 求解完成后自动入库

    将验证通过的求解结果存入缓存，供后续相似问题快速命中。
    benchmark 模式（skip_cache=True）下跳过保存。
    """
    # benchmark 模式：不保存到缓存
    if state.get("skip_cache", False):
        logger.debug("[Cache] skip_cache=True，跳过缓存保存")
        return {}

    question_text = state.get("question_text", "")
    final_output = state.get("final_output", {})
    verification_passed = state.get("verification_passed", False)

    if not verification_passed:
        logger.debug("[Cache] 验证未通过，跳过缓存")
        return {}

    if not final_output or not question_text:
        return {}

    try:
        from rag.cache.problem_cache import get_cache
        cache = get_cache()

        hit = cache.search(question_text)
        if hit.is_hit and hit.similarity >= 0.99:
            logger.debug("[Cache] 已存在相同条目，跳过保存")
            return {}

        cache.save(question_text, final_output)
        logger.info(f"[Cache] 结果已自动入库: domain={final_output.get('domain')}")

    except ImportError:
        logger.debug("[Cache] 缓存模块未加载，跳过保存")
    except Exception as e:
        logger.warning(f"[Cache] 缓存保存异常: {e}")

    return {}
