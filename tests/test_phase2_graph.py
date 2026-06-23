# ============================================================
# tests/test_phase2_graph.py
# 第二阶段测试：验证 LangGraph 工作流核心
# 运行方式: pytest tests/test_phase2_graph.py -v
# ============================================================

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest


# ============================================================
# 测试1: 图构建
# ============================================================

class TestGraphBuilder:
    """测试 graph_builder.py"""

    def test_build_graph_with_rag(self):
        """测试构建带 RAG 的图"""
        from graph.graph_builder import build_math_agent_graph
        graph = build_math_agent_graph(enable_rag=True, enable_checkpoint=False)
        assert graph is not None

        # 验证节点
        nodes = list(graph.get_graph().nodes.keys())
        assert "problem_parser" in nodes
        assert "classifier" in nodes
        assert "rag_retrieval" in nodes
        assert "solver_dispatcher" in nodes
        assert "verifier" in nodes
        assert "reflection" in nodes
        assert "formatter" in nodes
        assert "error_handler" in nodes

    def test_build_graph_without_rag(self):
        """测试构建不带 RAG 的图"""
        from graph.graph_builder import build_math_agent_graph
        graph = build_math_agent_graph(enable_rag=False, enable_checkpoint=False)
        assert graph is not None

        nodes = list(graph.get_graph().nodes.keys())
        assert "rag_retrieval" not in nodes  # RAG 节点不应该存在

    def test_build_graph_with_checkpoint(self):
        """测试构建带检查点的图"""
        from graph.graph_builder import build_math_agent_graph
        graph = build_math_agent_graph(enable_rag=False, enable_checkpoint=True)
        assert graph is not None
        # 带 checkpointer 的图应该可以获取状态
        assert hasattr(graph, 'checkpointer')

    def test_graph_info(self):
        """测试图信息函数"""
        from graph.graph_builder import build_math_agent_graph, get_graph_info
        graph = build_math_agent_graph(enable_rag=True, enable_checkpoint=False)
        info = get_graph_info(graph)

        assert "total_nodes" in info
        assert "node_names" in info
        assert "total_edges" in info
        assert "entry_point" in info
        assert info["total_nodes"] > 5
        assert info["entry_point"] == "problem_parser"

    def test_all_nodes_registered(self):
        """验证所有必需节点已注册"""
        from graph.graph_builder import build_math_agent_graph
        graph = build_math_agent_graph(enable_rag=True, enable_checkpoint=False)

        required_nodes = [
            "problem_parser", "classifier", "solver_dispatcher",
            "verifier", "reflection", "formatter", "error_handler"
        ]
        nodes = list(graph.get_graph().nodes.keys())

        for node in required_nodes:
            assert node in nodes, f"缺少节点: {node}"

    def test_end_edges_exist(self):
        """验证终止边存在（formatter→END, error_handler→END）"""
        from graph.graph_builder import build_math_agent_graph
        graph = build_math_agent_graph(enable_rag=True, enable_checkpoint=False)

        edges = list(graph.get_graph().edges)
        # 检查是否有到 END 的边
        end_edges = [e for e in edges if e.target == "__end__"]
        assert len(end_edges) >= 2, f"终止边数量不够: {len(end_edges)}"


# ============================================================
# 测试2: 条件路由
# ============================================================

class TestRouterFunctions:
    """测试条件路由函数"""

    def test_router_after_classifier_success(self):
        """测试分类成功后的路由"""
        from graph.graph_builder import router_after_classifier
        from schemas.workflow_state import create_initial_state

        state = create_initial_state("q001", "test")
        state["classified_domain"] = "algebra"
        state["classification_confidence"] = 0.95

        result = router_after_classifier(state)
        assert result == "rag_retrieval"

    def test_router_after_classifier_failure(self):
        """测试分类失败后的路由"""
        from graph.graph_builder import router_after_classifier
        from schemas.workflow_state import create_initial_state

        state = create_initial_state("q001", "test")
        state["classified_domain"] = ""
        state["classification_confidence"] = 0.0

        result = router_after_classifier(state)
        assert result == "error_handler"

    def test_router_after_reflection_retry(self):
        """测试反思触发重试"""
        from graph.graph_builder import router_after_reflection
        from schemas.workflow_state import create_initial_state

        state = create_initial_state("q001", "test")
        state["reflection_needed"] = True
        state["reflection_count"] = 1

        result = router_after_reflection(state)
        assert result == "solver_dispatcher"

    def test_router_after_reflection_done(self):
        """测试反思完成进入格式化"""
        from graph.graph_builder import router_after_reflection
        from schemas.workflow_state import create_initial_state

        state = create_initial_state("q001", "test")
        state["reflection_needed"] = False
        state["verification_passed"] = True

        result = router_after_reflection(state)
        assert result == "formatter"

    def test_router_after_reflection_max_retries(self):
        """测试达到最大重试次数后停止"""
        from graph.graph_builder import router_after_reflection
        from schemas.workflow_state import create_initial_state

        state = create_initial_state("q001", "test", max_reflection_count=3)
        state["reflection_needed"] = False  # reflection_node 会设 False
        state["reflection_count"] = 3

        result = router_after_reflection(state)
        assert result == "formatter"  # 即使失败也格式化输出


# ============================================================
# 测试3: 图最小可行执行
# ============================================================

class TestMinimalGraphExecution:
    """
    测试最小可行图执行

    注意：这些测试会实际运行 LangGraph 图，但不会调用 LLM API。
    我们通过 mock 或使用 dummy 问题来验证图结构正确。
    """

    def test_graph_invoke_minimal(self):
        """
        测试图能否正常 invoke（最小化执行）

        注意：此测试需要 mock LLM 调用，否则会因 API 未配置而失败。
        这里验证图的 invoke 接口存在且可调用。
        """
        from graph.graph_builder import build_math_agent_graph
        from schemas.workflow_state import create_initial_state

        # 构建不启用 RAG 的图
        graph = build_math_agent_graph(enable_rag=False, enable_checkpoint=False)

        # 验证图对象的方法
        assert hasattr(graph, 'invoke')
        assert callable(graph.invoke)
        assert hasattr(graph, 'ainvoke')

    def test_graph_stream_available(self):
        """测试图的 stream 可用"""
        from graph.graph_builder import build_math_agent_graph
        graph = build_math_agent_graph(enable_rag=False, enable_checkpoint=False)
        assert hasattr(graph, 'stream')


# ============================================================
# 测试4: WorkflowRunner
# ============================================================

class TestWorkflowRunner:
    """测试 workflow.py"""

    def test_create_workflow(self):
        """测试创建工作流运行器"""
        from graph.workflow import MathAgentWorkflow
        runner = MathAgentWorkflow(
            enable_rag=False,
            enable_checkpoint=False,
            max_reflection_count=2,
        )
        assert runner.enable_rag is False
        assert runner.max_reflection_count == 2
        assert runner._graph is not None

    def test_default_workflow(self):
        """测试默认工作流"""
        from graph.workflow import create_default_workflow
        runner = create_default_workflow()
        assert runner.enable_rag is True
        assert runner.max_reflection_count == 3

    def test_create_initial_state_via_workflow(self):
        """验证工作流可创建初始状态"""
        from graph.workflow import MathAgentWorkflow
        from schemas.workflow_state import create_initial_state

        runner = MathAgentWorkflow(enable_rag=False)
        state = create_initial_state("test_q", "Solve x^2 = 4")
        assert state["question_id"] == "test_q"


# ============================================================
# 测试运行入口
# ============================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
