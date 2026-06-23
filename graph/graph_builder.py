# ============================================================
# graph/graph_builder.py — LangGraph 图构建器
# 构建完整的 StateGraph，包括：
#   - 节点定义
#   - 顺序边 (add_edge)
#   - 条件边 (add_conditional_edges)  ← 核心：Router!
#   - 反思循环 (Reflection Loop)
#   - 编译图 (compile)
#
# 图拓扑结构：
#
#   START
#     ↓
#   problem_parser ──────────────────────────┐
#     ↓                                       │
#   classifier ───(条件边)──→ error_handler   │
#     ↓                                       │
#   rag_retrieval (可选)                      │
#     ↓                                       │
#   solver_dispatcher                         │
#     ↓                                       │
#   verifier                                  │
#     ↓                                       │
#   reflection ──(条件边)──┐                  │
#     │                    │                  │
#     │ (need_retry=True)  │ (need_retry=False)
#     ↓                    ↓                  │
#   solver_dispatcher   formatter             │
#     (loop)              ↓                   │
#                       END                   │
# ============================================================

from typing import Literal, Dict, Any
from loguru import logger

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from schemas.workflow_state import WorkflowState
from graph.nodes import (
    cache_check_node,
    cache_save_node,
    problem_parser_node,
    classifier_node,
    rag_retrieval_node,
    solver_dispatcher_node,
    verifier_node,
    reflection_node,
    formatter_node,
    error_handler_node,
)


# ============================================================
# 条件路由函数
# ============================================================

def router_after_classifier(state: WorkflowState) -> Literal["rag_retrieval", "error_handler"]:
    """
    分类器后的条件路由

    逻辑：
    - 分类成功（classified_domain 非空）→ 进入 RAG 检索
    - 分类失败 → 进入错误处理

    参数:
        state: 工作流状态

    返回:
        str: 下一个节点名称
    """
    domain = state.get("classified_domain", "")
    confidence = state.get("classification_confidence", 0.0)

    if domain and confidence > 0.0:
        logger.info(f"[Router] 分类成功 ({domain}), 进入 RAG 检索")
        return "rag_retrieval"
    else:
        logger.warning(f"[Router] 分类失败 (domain='{domain}', conf={confidence}), 进入错误处理")
        state["error_info"] = state.get("error_info", []) + [
            f"Classifier failed: domain={domain}, confidence={confidence}"
        ]
        return "error_handler"


def router_after_reflection(state: WorkflowState) -> Literal["solver_dispatcher", "formatter"]:
    """
    反思后的条件路由（Reflection Loop）

    逻辑：
    - reflection_needed=True → 回到 solver_dispatcher 重试
    - reflection_needed=False → 进入 formatter 结束

    参数:
        state: 工作流状态

    返回:
        str: 下一个节点名称
    """
    need_retry = state.get("reflection_needed", False)
    count = state.get("reflection_count", 0)
    max_count = state.get("max_reflection_count", 3)

    if need_retry:
        logger.info(
            f"[Router] 反思触发重试: "
            f"attempt {count}/{max_count} → 回到 solver_dispatcher"
        )
        return "solver_dispatcher"
    else:
        verification_passed = state.get("verification_passed", False)
        logger.info(
            f"[Router] 反思完成: "
            f"verification_passed={verification_passed} → 进入 formatter"
        )
        return "formatter"


# ============================================================
# 图构建函数
# ============================================================

def build_math_agent_graph(
    enable_rag: bool = True,
    enable_checkpoint: bool = True,
) -> StateGraph:
    """
    构建数学 Agent 工作流图

    参数:
        enable_rag: 是否启用 RAG 检索节点
        enable_checkpoint: 是否启用检查点（支持中断/恢复）

    返回:
        StateGraph: 编译后的 LangGraph 图
    """
    logger.info("[GraphBuilder] 开始构建 LangGraph 工作流图...")

    # ============================================================
    # 1. 创建 StateGraph
    # ============================================================
    workflow = StateGraph(WorkflowState)

    # ============================================================
    # 2. 添加节点（含缓存节点）
    # ============================================================
    workflow.add_node("cache_check", cache_check_node)
    workflow.add_node("cache_save", cache_save_node)
    workflow.add_node("problem_parser", problem_parser_node)
    workflow.add_node("classifier", classifier_node)
    workflow.add_node("solver_dispatcher", solver_dispatcher_node)
    workflow.add_node("verifier", verifier_node)
    workflow.add_node("reflection", reflection_node)
    workflow.add_node("formatter", formatter_node)
    workflow.add_node("error_handler", error_handler_node)

    if enable_rag:
        workflow.add_node("rag_retrieval", rag_retrieval_node)

    # ============================================================
    # 3. 设置入口点 → 先查缓存
    # ============================================================
    workflow.set_entry_point("cache_check")

    # ============================================================
    # 4. 缓存路由 — 命中直出，未命中走完整流程
    # ============================================================
    def router_after_cache(state: WorkflowState) -> Literal["formatter", "problem_parser"]:
        if state.get("cache_hit", False):
            logger.info("[Router] 缓存命中 → 跳过求解，直接输出")
            return "formatter"
        else:
            logger.info("[Router] 缓存未命中 → 进入完整求解流程")
            return "problem_parser"

    workflow.add_conditional_edges(
        "cache_check",
        router_after_cache,
        {
            "formatter": "formatter",
            "problem_parser": "problem_parser",
        }
    )

    # ============================================================
    # 5. 顺序边 (常规流程)
    # ============================================================
    workflow.add_edge("problem_parser", "classifier")
    workflow.add_edge("solver_dispatcher", "verifier")
    workflow.add_edge("verifier", "reflection")

    # ============================================================
    # 6. 条件边 (Router)
    # ============================================================

    # 6a. 分类器后的路由
    if enable_rag:
        workflow.add_conditional_edges(
            "classifier", router_after_classifier,
            {"rag_retrieval": "rag_retrieval", "error_handler": "error_handler"}
        )
        workflow.add_edge("rag_retrieval", "solver_dispatcher")
    else:
        workflow.add_conditional_edges(
            "classifier", router_after_classifier,
            {"rag_retrieval": "solver_dispatcher", "error_handler": "error_handler"}
        )

    # 6b. 反思后的路由（Reflection Loop）
    workflow.add_conditional_edges(
        "reflection", router_after_reflection,
        {"solver_dispatcher": "solver_dispatcher", "formatter": "formatter"}
    )

    # ============================================================
    # 7. 终止边 — formatter 后先保存缓存再结束
    # ============================================================
    workflow.add_edge("formatter", "cache_save")
    workflow.add_edge("cache_save", END)
    workflow.add_edge("error_handler", END)

    # ============================================================
    # 7. 编译图
    # ============================================================
    if enable_checkpoint:
        # 使用内存检查点（支持中断/恢复）
        checkpointer = MemorySaver()
        compiled_graph = workflow.compile(checkpointer=checkpointer)
        logger.info("[GraphBuilder] 图编译完成 (with checkpoint support)")
    else:
        compiled_graph = workflow.compile()
        logger.info("[GraphBuilder] 图编译完成 (无 checkpoint)")

    return compiled_graph


# ============================================================
# 图可视化（用于调试和论文）
# ============================================================

def visualize_graph(graph: StateGraph, output_path: str = "./outputs/graph.png") -> None:
    """
    将 LangGraph 图可视化输出为 PNG

    需要安装: pip install grandalf (或 pygraphviz)

    参数:
        graph: 编译后的 StateGraph
        output_path: 输出图片路径
    """
    try:
        from langgraph.graph.graph import GraphVisualizer
        from IPython.display import Image as IPyImage

        # 尝试生成 Mermaid 格式
        mermaid_str = graph.get_graph().draw_mermaid()
        logger.info(f"[GraphViz] Mermaid 格式:\n{mermaid_str}")

        # 保存 PNG（需要 pygraphviz）
        try:
            graph.get_graph().draw_png(output_path)
            logger.info(f"[GraphViz] 图已保存到 {output_path}")
        except ImportError:
            logger.warning("[GraphViz] 需要安装 pygraphviz 才能导出 PNG")
    except Exception as e:
        logger.warning(f"[GraphViz] 可视化失败: {e}")


# ============================================================
# 图信息摘要
# ============================================================

def get_graph_info(graph: StateGraph) -> Dict[str, Any]:
    """
    获取图的元信息

    参数:
        graph: 编译后的 StateGraph

    返回:
        Dict: 包含节点数、边数、入口等信息
    """
    nodes = list(graph.get_graph().nodes.keys())
    edges = list(graph.get_graph().edges)

    return {
        "total_nodes": len(nodes),
        "node_names": nodes,
        "total_edges": len(edges),
        "edges": [(e.source, e.target) for e in edges],
        "entry_point": "problem_parser",
        "exit_points": ["formatter", "error_handler"],
    }
