# ============================================================
# tests/test_phase1_models_and_client.py
# 第一阶段测试：验证 data models + Intern-S1 API 客户端
# 运行方式: pytest tests/test_phase1_models_and_client.py -v
# ============================================================

import sys
import os
import json

# 确保项目根目录在 sys.path 中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest


# ============================================================
# 测试1: 数学领域分类枚举
# ============================================================

class TestMathDomains:
    """测试 math_domains.py"""

    def test_all_18_domains_defined(self):
        """验证18个数学领域全部定义完毕"""
        from schemas.math_domains import MathDomain
        domains = list(MathDomain)
        assert len(domains) == 18, f"期望18个领域，实际{len(domains)}个"

    def test_domain_to_solver_mapping(self):
        """验证每个领域都有对应的 Solver 映射"""
        from schemas.math_domains import MathDomain, DOMAIN_TO_SOLVER
        for domain in MathDomain:
            assert domain in DOMAIN_TO_SOLVER, f"{domain.value} 缺少 Solver 映射"
            solver = DOMAIN_TO_SOLVER[domain]
            assert solver in [
                "pde_solver", "ode_solver", "complex_analysis_solver",
                "topology_solver", "optimization_solver", "algebra_solver"
            ], f"未知的 Solver: {solver}"

    def test_get_solver_for_domain(self):
        """测试领域→Solver路由函数"""
        from schemas.math_domains import get_solver_for_domain
        # 精确匹配
        assert get_solver_for_domain("partial_differential_equations") == "pde_solver"
        assert get_solver_for_domain("topology") == "topology_solver"
        assert get_solver_for_domain("algebra") == "algebra_solver"

        # 中文匹配
        assert get_solver_for_domain("偏微分方程") == "pde_solver"
        assert get_solver_for_domain("拓扑学") == "topology_solver"

        # 未知领域回退
        assert get_solver_for_domain("unknown_domain") == "algebra_solver"

    def test_list_all_domains(self):
        """测试列出所有领域"""
        from schemas.math_domains import list_all_domains
        domains = list_all_domains()
        assert len(domains) == 18
        for d in domains:
            assert "domain_key" in d
            assert "domain_cn" in d
            assert "solver" in d

    def test_domain_cn_name_has_all(self):
        """验证每个领域都有中文名"""
        from schemas.math_domains import MathDomain, DOMAIN_CN_NAME
        for domain in MathDomain:
            assert domain in DOMAIN_CN_NAME, f"{domain.value} 缺少中文名"


# ============================================================
# 测试2: 输出 Schema
# ============================================================

class TestOutputSchema:
    """测试 output_schema.py"""

    def test_math_solution_output_minimal(self):
        """测试最小字段构建 MathSolutionOutput"""
        from schemas.output_schema import MathSolutionOutput, VerificationResult

        output = MathSolutionOutput(
            question_id="test_001",
            domain="algebra",
            final_answer="x = 2",
            reasoning_steps=[],
            methods_used=["因式分解"],
            verification=VerificationResult(
                is_correct=True,
                confidence=0.95,
                check_method="代入验证"
            ),
            educational_hint="使用因式分解法求解二次方程"
        )

        assert output.question_id == "test_001"
        assert output.domain == "algebra"
        assert output.verification.confidence == 0.95

        # 测试JSON序列化
        json_str = output.model_dump_json(indent=2)
        parsed = json.loads(json_str)
        assert parsed["question_id"] == "test_001"

    def test_reasoning_step_creation(self):
        """测试推理步骤构建"""
        from schemas.output_schema import ReasoningStep

        step = ReasoningStep(
            step_id=1,
            description="将方程标准化",
            formula="ax^2 + bx + c = 0",
            result="a=1, b=-5, c=6",
            method="标准化"
        )
        assert step.step_id == 1
        assert "ax^2" in step.formula

    def test_confidence_range_validation(self):
        """测试置信度范围验证"""
        from schemas.output_schema import VerificationResult
        import pytest

        # 正常范围
        v = VerificationResult(is_correct=True, confidence=0.85)
        assert v.confidence == 0.85

        # 超出范围应抛出验证错误
        with pytest.raises(Exception):  # Pydantic ValidationError
            VerificationResult(is_correct=True, confidence=1.5)

        with pytest.raises(Exception):
            VerificationResult(is_correct=True, confidence=-0.1)

    def test_confidence_rounding(self):
        """测试置信度四舍五入到4位小数"""
        from schemas.output_schema import VerificationResult

        v = VerificationResult(is_correct=True, confidence=0.123456789)
        assert v.confidence == 0.1235  # 四舍五入到4位

    def test_batch_evaluation_summary(self):
        """测试批量评估汇总"""
        from schemas.output_schema import BatchEvaluationSummary

        summary = BatchEvaluationSummary(
            total_questions=112,
            solved_count=100,
            failed_count=12,
            avg_confidence=0.87,
            domain_accuracy={"algebra": 0.92},
            total_time_ms=3600000.0,
            avg_time_per_question_ms=32142.0,
        )
        assert summary.total_questions == 112
        assert summary.failed_count == 12


# ============================================================
# 测试3: Workflow State
# ============================================================

class TestWorkflowState:
    """测试 workflow_state.py"""

    def test_create_initial_state(self):
        """测试初始状态创建"""
        from schemas.workflow_state import create_initial_state

        state = create_initial_state(
            question_id="q_001",
            question_text="求解方程 x^2 + 3x - 4 = 0",
            max_reflection_count=3
        )

        assert state["question_id"] == "q_001"
        assert state["question_text"] == "求解方程 x^2 + 3x - 4 = 0"
        assert state["classified_domain"] == ""
        assert state["reflection_count"] == 0
        assert state["max_reflection_count"] == 3
        assert state["messages"] == []
        assert state["error_info"] == []
        assert state["node_trace"] == []

    def test_state_mutable_update(self):
        """测试状态可变更新"""
        from schemas.workflow_state import create_initial_state

        state = create_initial_state("q_001", "test")
        state["classified_domain"] = "algebra"
        state["classification_confidence"] = 0.95

        assert state["classified_domain"] == "algebra"
        assert state["classification_confidence"] == 0.95

    def test_get_state_summary(self):
        """测试状态摘要函数"""
        from schemas.workflow_state import create_initial_state, get_state_summary

        state = create_initial_state("q_001", "test")
        summary = get_state_summary(state)

        assert summary["question_id"] == "q_001"
        assert summary["classified_domain"] == ""
        assert summary["error_count"] == 0
        assert isinstance(summary["node_trace"], list)


# ============================================================
# 测试4: 配置系统
# ============================================================

class TestConfig:
    """测试 settings.py"""

    def test_get_config_singleton(self):
        """测试配置单例模式"""
        from configs.settings import get_config, reset_config

        reset_config()
        config1 = get_config()
        config2 = get_config()

        assert config1 is config2, "get_config() 应返回同一实例"

    def test_config_defaults(self):
        """测试配置默认值"""
        from configs.settings import get_config, reset_config

        reset_config()
        config = get_config()

        assert config.intern_s1.temperature == 0.1
        assert config.intern_s1.max_tokens == 16384  # 复杂推理需大上下文
        assert config.workflow.max_reflection_count == 3
        assert config.solver.numeric_precision == 15
        assert config.rag.top_k_retrieval == 5

    def test_environment_override(self, monkeypatch):
        """测试环境变量覆盖配置"""
        from configs.settings import get_config, reset_config

        reset_config()
        monkeypatch.setenv("INTERN_S1_API_KEY", "test-key-123")
        monkeypatch.setenv("INTERN_S1_MODEL", "test-model")

        config = get_config()
        assert config.intern_s1.api_key == "test-key-123"
        assert config.intern_s1.model_name == "test-model"

        reset_config()


# ============================================================
# 测试5: Intern-S1 API 客户端（Mock 测试）
# ============================================================

class TestInternS1Client:
    """测试 intern_client.py (不实际调用API)"""

    def test_client_initialization(self):
        """测试客户端初始化"""
        from tools.intern_client import InternS1Client, reset_intern_client
        from configs.settings import reset_config, get_config

        reset_config()
        reset_intern_client()

        client = InternS1Client()
        expected_model = get_config().intern_s1.model_name
        assert client.model_name == expected_model
        assert client.temperature == 0.1
        assert client.total_calls == 0

    def test_rate_limiter_init(self):
        """测试速率限制器初始化"""
        from tools.intern_client import RateLimiter

        limiter = RateLimiter(max_calls=60, period=60.0)
        assert limiter.max_calls == 60
        assert limiter.period == 60.0

    def test_usage_stats_initial(self):
        """测试初始用量统计"""
        from tools.intern_client import InternS1Client, reset_intern_client
        from configs.settings import reset_config

        reset_config()
        reset_intern_client()

        client = InternS1Client()
        stats = client.get_usage_stats()

        assert stats["total_calls"] == 0
        assert stats["total_prompt_tokens"] == 0
        assert stats["total_completion_tokens"] == 0

    def test_global_client_singleton(self):
        """测试全局客户端单例"""
        from tools.intern_client import get_intern_client, reset_intern_client
        from configs.settings import reset_config

        reset_config()
        reset_intern_client()

        c1 = get_intern_client()
        c2 = get_intern_client()
        assert c1 is c2

        reset_intern_client()

    def test_chat_message_format(self):
        """
        测试 chat 方法的消息格式构建
        此测试不实际调用 API，仅验证消息格式化逻辑
        """
        # 这里仅验证客户端存在且方法签名正确
        from tools.intern_client import InternS1Client
        import inspect

        # 验证方法签名
        sig = inspect.signature(InternS1Client.chat)
        params = list(sig.parameters.keys())
        assert "messages" in params
        assert "system_prompt" in params
        assert "temperature" in params


# ============================================================
# 测试运行入口
# ============================================================

if __name__ == "__main__":
    # 允许直接运行 python tests/test_phase1_models_and_client.py 来执行测试
    pytest.main([__file__, "-v", "--tb=short"])
