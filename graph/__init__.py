# graph/__init__.py
# LangGraph 工作流模块
# 核心编排层：状态定义 → 节点函数 → 图构建 → 运行器
#
# 节点已拆分为 graph/nodes/ 下的独立文件：
#   - cache_nodes: 缓存检查 & 保存
#   - parser_node: 问题解析
#   - classifier_node: 领域分类（委托给 ClassifierAgent）
#   - rag_node: RAG 知识检索
#   - solver_node: Solver 调度（委托给 SolverDispatcher）
#   - verifier_node: 结果验证
#   - reflection_node: 反思重试（委托给 GraphManagerAgent）
#   - formatter_node: JSON 格式化
#   - error_handler_node: 异常兜底

from graph.nodes import (
    cache_check_node, cache_save_node,
    problem_parser_node, classifier_node,
    rag_retrieval_node, solver_dispatcher_node,
    verifier_node, reflection_node,
    formatter_node, error_handler_node,
)
from graph.graph_builder import build_math_agent_graph, visualize_graph, get_graph_info
from graph.workflow import MathAgentWorkflow, create_default_workflow
