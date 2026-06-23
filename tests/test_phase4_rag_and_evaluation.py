# ============================================================
# tests/test_phase4_rag_and_evaluation.py
# 第四阶段测试：RAG 检索 + 批量评估 + 系统集成
# 运行: pytest tests/test_phase4_rag_and_evaluation.py -v
# ============================================================

import sys, os, json, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest


class TestRAGKnowledgeBases:
    """测试知识库"""

    def test_theorem_db_loaded(self):
        """测试定理库可加载"""
        from rag.theorem_db import THEOREM_DB, DEFAULT_THEOREMS
        assert isinstance(THEOREM_DB, dict)
        assert len(THEOREM_DB) > 0
        assert len(DEFAULT_THEOREMS) > 0

    def test_theorem_db_has_key_domains(self):
        """测试定理库包含关键领域"""
        from rag.theorem_db import THEOREM_DB
        key_domains = ["algebra", "topology", "optimization", "probability"]
        for d in key_domains:
            assert d in THEOREM_DB, f"缺少领域: {d}"
            assert len(THEOREM_DB[d]) >= 3, f"{d} 定理数不足"

    def test_formula_db_loaded(self):
        """测试公式库可加载"""
        from rag.formula_db import FORMULA_DB, DEFAULT_FORMULAS
        assert isinstance(FORMULA_DB, dict)
        assert len(FORMULA_DB) > 0

    def test_example_db_loaded(self):
        """测试示例题库可加载"""
        from rag.example_db import EXAMPLE_DB, DEFAULT_EXAMPLES
        assert isinstance(EXAMPLE_DB, dict)
        assert len(EXAMPLE_DB) > 0


class TestRAGRetriever:
    """测试 RAG 检索器"""

    def test_retriever_initialization(self):
        """测试检索器初始化"""
        from rag.retriever import RAGRetriever
        retriever = RAGRetriever()
        assert retriever is not None
        # 即使 ChromaDB 不可用也应优雅降级
        assert hasattr(retriever, 'search_theorems')

    def test_keyword_search_theorems(self):
        """测试关键词定理检索"""
        from rag.retriever import RAGRetriever
        retriever = RAGRetriever()
        results = retriever.search_theorems(
            domain="algebra",
            keywords=["群", "同构"],
            top_k=3
        )
        assert isinstance(results, list)
        # 应该返回非空结果（从内置定理库）
        if results:
            assert any("同构" in r for r in results)

    def test_keyword_search_formulas(self):
        """测试关键词公式检索"""
        from rag.retriever import RAGRetriever
        retriever = RAGRetriever()
        results = retriever.search_formulas(
            domain="ordinary_differential_equations",
            keywords=["特征方程"],
            top_k=3
        )
        assert isinstance(results, list)

    def test_search_unknown_domain(self):
        """测试未知领域的检索"""
        from rag.retriever import RAGRetriever
        retriever = RAGRetriever()
        results = retriever.search_theorems(
            domain="unknown_domain_xyz",
            keywords=["test"],
            top_k=3
        )
        assert isinstance(results, list)

    def test_simple_match_scoring(self):
        """测试简单匹配评分"""
        from rag.retriever import RAGRetriever
        retriever = RAGRetriever()
        items = ["苹果很好吃", "香蕉是黄色的", "苹果和香蕉都是水果"]
        keywords = ["苹果"]
        results = retriever._simple_match(items, keywords, 2)
        assert len(results) <= 2
        assert "苹果" in results[0]


class TestEvaluator:
    """测试批量评估器"""

    def test_evaluator_init(self):
        """测试评估器初始化"""
        from evaluation.evaluator import BatchEvaluator, EvaluationConfig
        config = EvaluationConfig(batch_size=5, save_interval=2)
        evaluator = BatchEvaluator(config)
        assert evaluator.config.batch_size == 5
        assert evaluator.config.save_interval == 2

    def test_load_dataset_json(self):
        """测试加载 JSON 数据集"""
        from evaluation.evaluator import BatchEvaluator

        # 创建临时数据集
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8")
        json.dump([
            {"question_id": "q1", "question_text": "Solve x^2 = 4", "domain": "algebra"},
            {"question_id": "q2", "question_text": "Solve dy/dx = y", "domain": "ode"},
        ], tmp)
        tmp.close()

        try:
            evaluator = BatchEvaluator()
            questions = evaluator._load_dataset(tmp.name)
            assert len(questions) == 2
            assert questions[0]["question_id"] == "q1"
            assert questions[1]["domain"] == "ode"
        finally:
            os.unlink(tmp.name)

    def test_load_dataset_from_directory(self):
        """测试从目录加载数据集"""
        from evaluation.evaluator import BatchEvaluator

        with tempfile.TemporaryDirectory() as tmpdir:
            # 创建几个 .txt 问题文件
            for i in range(3):
                fpath = os.path.join(tmpdir, f"q_{i:03d}.txt")
                with open(fpath, "w", encoding="utf-8") as f:
                    f.write(f"Problem {i}: test question")

            evaluator = BatchEvaluator()
            questions = evaluator._load_dataset(tmpdir)
            assert len(questions) == 3
            assert all("question_text" in q for q in questions)

    def test_batch_evaluation_summary_creation(self):
        """测试评估汇总创建"""
        from schemas.output_schema import BatchEvaluationSummary

        summary = BatchEvaluationSummary(
            total_questions=112,
            solved_count=98,
            failed_count=14,
            avg_confidence=0.85,
            domain_accuracy={"algebra": 0.92, "topology": 0.78},
            total_time_ms=7200000.0,
            avg_time_per_question_ms=64285.0,
        )

        assert summary.total_questions == 112
        assert summary.solved_count == 98
        assert summary.avg_confidence == 0.85
        assert summary.domain_accuracy["algebra"] == 0.92


class TestSystemEntryPoint:
    """测试系统入口 run.py"""

    def test_run_py_exists(self):
        """测试 run.py 存在"""
        run_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "run.py"
        )
        assert os.path.exists(run_path), "run.py 不存在"

    def test_run_py_syntax(self):
        """测试 run.py 语法正确"""
        import ast
        run_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "run.py"
        )
        with open(run_path, "r", encoding="utf-8") as f:
            source = f.read()
        ast.parse(source)  # 语法检查

    def test_run_py_info_mode(self):
        """测试 run.py --mode info 可正常执行"""
        import subprocess
        run_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "run.py"
        )
        result = subprocess.run(
            ["python", run_path, "--mode", "info"],
            capture_output=True, text=True, timeout=30,
            cwd=os.path.dirname(run_path),
        )
        assert result.returncode == 0, f"run.py info 模式失败: {result.stderr}"


class TestFullSystemIntegration:
    """全系统集成测试"""

    def test_all_modules_importable(self):
        """测试所有模块可导入"""
        modules_to_test = [
            "schemas.math_domains",
            "schemas.output_schema",
            "schemas.workflow_state",
            "configs.settings",
            "tools.intern_client",
            "graph.nodes",
            "graph.graph_builder",
            "graph.workflow",
            "solvers.base_solver",
            "solvers.pde_solver",
            "solvers.ode_solver",
            "solvers.complex_analysis_solver",
            "solvers.topology_solver",
            "solvers.optimization_solver",
            "solvers.algebra_solver",
            "solvers.solver_registry",
            "rag.retriever",
            "rag.theorem_db",
            "rag.formula_db",
            "rag.example_db",
            "evaluation.evaluator",
        ]

        for module_name in modules_to_test:
            try:
                __import__(module_name)
            except Exception as e:
                pytest.fail(f"导入失败 {module_name}: {e}")

    def test_end_to_end_pipeline_exists(self):
        """测试端到端 Pipeline 各组件连接正确"""
        # 验证从状态创建到图执行的完整链路
        from schemas.workflow_state import create_initial_state
        from graph.graph_builder import build_math_agent_graph
        from solvers.solver_registry import create_solver

        # 1. 创建初始状态
        state = create_initial_state("test_q", "Solve x^2 = 4")
        assert state["question_id"] == "test_q"

        # 2. 构建图
        graph = build_math_agent_graph(enable_rag=False)
        assert graph is not None

        # 3. 创建 Solver
        solver = create_solver("algebra_solver")
        assert solver.solver_name == "algebra_solver"

        # 4. 验证节点可调用
        from graph.nodes import problem_parser_node, classifier_node
        assert callable(problem_parser_node)
        assert callable(classifier_node)

    def test_dataset_directory_exists(self):
        """测试 datasets 目录存在或可创建"""
        datasets_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "datasets"
        )
        if not os.path.exists(datasets_dir):
            os.makedirs(datasets_dir, exist_ok=True)
        assert os.path.isdir(datasets_dir)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
