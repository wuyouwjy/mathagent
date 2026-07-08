# ============================================================
# mcp/tools.py — MCP 工具定义
# 将系统核心能力封装为 MCP 工具函数
# ============================================================

import sys
import os
import json
from typing import Dict, Any, List, Optional

# 确保项目根目录在 sys.path 中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loguru import logger


# ============================================================
# MCP 工具实现
# ============================================================

def solve_math_problem(
    question: str,
    enable_rag: bool = True,
    max_retries: int = 3,
) -> Dict[str, Any]:
    """
    求解数学问题

    参数:
        question: 数学问题文本
        enable_rag: 是否启用 RAG 检索
        max_retries: 最大反思重试次数

    返回:
        Dict: 完整求解结果（MathSolutionOutput 格式）
    """
    from graph.workflow import MathAgentWorkflow

    workflow = MathAgentWorkflow(
        enable_rag=enable_rag,
        max_reflection_count=max_retries,
    )
    result = workflow.solve(question_text=question, verbose=False)
    return result


def classify_problem(question: str) -> Dict[str, Any]:
    """
    分类数学问题领域

    参数:
        question: 数学问题文本

    返回:
        Dict: 分类结果 {domain, domain_cn, solver_name, confidence, reason}
    """
    from agents.classifier_agent import get_classifier

    agent = get_classifier()
    result = agent.classify(question)
    return {
        "domain": result.domain,
        "domain_cn": result.domain_cn,
        "solver_name": result.solver_name,
        "confidence": result.confidence,
        "reason": result.reason,
        "used_llm": result.used_llm,
    }


def search_theorems(query: str, domain: str = "", top_k: int = 5) -> List[str]:
    """
    检索相关数学定理

    参数:
        query: 搜索查询
        domain: 数学领域（可选）
        top_k: 返回数量

    返回:
        List[str]: 定理文本列表
    """
    from rag.retriever import RAGRetriever

    retriever = RAGRetriever()
    keywords = query.split()
    if domain:
        return retriever.search_theorems(domain, keywords, top_k)
    else:
        # 尝试所有领域
        results = []
        for d in ["algebra", "partial_differential_equations", "ordinary_differential_equations",
                   "complex_analysis", "topology", "optimization"]:
            results.extend(retriever.search_theorems(d, keywords, top_k=2))
        return results[:top_k]


def search_formulas(query: str, domain: str = "", top_k: int = 5) -> List[str]:
    """
    检索相关数学公式

    参数:
        query: 搜索查询
        domain: 数学领域（可选）
        top_k: 返回数量

    返回:
        List[str]: 公式文本列表（LaTeX 格式）
    """
    from rag.retriever import RAGRetriever

    retriever = RAGRetriever()
    keywords = query.split()
    if domain:
        return retriever.search_formulas(domain, keywords, top_k)
    else:
        results = []
        for d in ["algebra", "partial_differential_equations", "ordinary_differential_equations",
                   "complex_analysis", "topology", "optimization"]:
            results.extend(retriever.search_formulas(d, keywords, top_k=2))
        return results[:top_k]


def get_solver_info(solver_name: str = "") -> Dict[str, Any]:
    """
    获取 Solver 信息

    参数:
        solver_name: Solver 名称（为空时返回所有 Solver 列表）

    返回:
        Dict: Solver 元数据
    """
    from agents.solver_experts.solver_registry import list_registered_solvers, get_solver_metadata
    from agents.solver_experts.skills import get_skill

    if solver_name:
        meta = get_solver_metadata(solver_name)
        skill = get_skill(solver_name)
        if skill:
            meta["skill"] = {
                "domain_cn": skill.domain_cn,
                "strategies": skill.strategies,
                "keywords": skill.keywords[:10],
            }
        return meta or {}
    else:
        return {name: get_solver_metadata(name) for name in list_registered_solvers()}


def list_domains() -> List[Dict[str, str]]:
    """
    列出所有支持的数学领域

    返回:
        List[Dict]: 领域列表
    """
    from schemas.math_domains import list_all_domains
    return list_all_domains()


def evaluate_solution(
    question: str,
    answer: str,
    reasoning_steps: List[Dict] = None,
) -> Dict[str, Any]:
    """
    评估求解结果

    参数:
        question: 原始问题
        answer: 待验证答案
        reasoning_steps: 推理步骤（可选）

    返回:
        Dict: 验证结果 {is_correct, confidence, check_method, error_details}
    """
    from tools.intern_client import get_intern_client

    if reasoning_steps is None:
        reasoning_steps = []

    client = get_intern_client()

    steps_summary = "\n".join([
        f"  Step {s.get('step_id', i+1)}: {s.get('description', '')[:100]}"
        for i, s in enumerate(reasoning_steps[:10])
    ])

    system_prompt = (
        "你是一位数学验证专家。请严格验证以下数学问题的求解结果。\n"
        "以 JSON 格式返回：\n"
        '{"is_correct": true/false, "confidence": 0.0-1.0, '
        '"check_method": "验证方法", "error_details": "错误描述", '
        '"correction_suggestion": "修改建议"}'
    )

    response = client.chat_with_json_output(
        messages=[{"role": "user", "content": (
            f"【原始问题】\n{question}\n\n"
            f"【推理步骤】\n{steps_summary}\n\n"
            f"【最终答案】\n{answer}"
        )}],
        system_prompt=system_prompt,
        temperature=0.0,
    )

    parsed = response.get("parsed_json", {})
    return {
        "is_correct": parsed.get("is_correct", False),
        "confidence": float(parsed.get("confidence", 0.5)),
        "check_method": parsed.get("check_method", "LLM验证"),
        "error_details": parsed.get("error_details", ""),
    }


def get_cache_stats() -> Dict[str, Any]:
    """
    获取缓存统计

    返回:
        Dict: 缓存统计信息
    """
    try:
        from rag.cache.problem_cache import get_cache
        cache = get_cache()
        return cache.get_stats()
    except Exception as e:
        return {"error": str(e)}


def get_problem_database_stats() -> Dict[str, Any]:
    """
    获取问题数据库统计

    返回:
        Dict: 数据库统计
    """
    from agents.evaluation_agent import get_evaluation_agent
    agent = get_evaluation_agent()
    return agent.get_stats()


def search_similar_problems(question: str, top_k: int = 3) -> List[Dict[str, Any]]:
    """
    搜索相似问题（类比求解）

    参数:
        question: 问题文本
        top_k: 返回数量

    返回:
        List[Dict]: 相似问题列表
    """
    from agents.evaluation_agent import get_evaluation_agent
    agent = get_evaluation_agent()
    similar = agent.find_similar(question, top_k)
    return [
        {
            "question_id": s["record"].get("question_id", ""),
            "question_text": s["record"].get("question_text", "")[:100],
            "domain": s["record"].get("domain", ""),
            "similarity": s["similarity"],
            "match_type": s["match_type"],
            "best_method": s["record"].get("best_method", ""),
            "solutions": s["record"].get("solutions", [])[-1:] if s["record"].get("solutions") else [],
        }
        for s in similar
    ]


# ============================================================
# 工具注册表
# ============================================================

TOOL_REGISTRY = {
    "solve_math_problem": solve_math_problem,
    "classify_problem": classify_problem,
    "search_theorems": search_theorems,
    "search_formulas": search_formulas,
    "get_solver_info": get_solver_info,
    "list_domains": list_domains,
    "evaluate_solution": evaluate_solution,
    "get_cache_stats": get_cache_stats,
    "get_problem_database_stats": get_problem_database_stats,
    "search_similar_problems": search_similar_problems,
}


def register_all_tools(mcp_instance) -> None:
    """
    将所有工具注册到 MCP 实例

    参数:
        mcp_instance: FastMCP 实例
    """
    for name, func in TOOL_REGISTRY.items():
        mcp_instance.tool()(func)
    logger.info(f"[MCP] 已注册 {len(TOOL_REGISTRY)} 个工具")
