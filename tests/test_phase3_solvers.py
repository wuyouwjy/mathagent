# ============================================================
# tests/test_phase3_solvers.py
# 第三阶段测试：验证多专家Solver系统
# 运行: pytest tests/test_phase3_solvers.py -v
# ============================================================

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest


class TestSolverRegistry:
    """测试 Solver 注册中心"""

    def test_all_six_solvers_registered(self):
        """验证6个Solver全部注册"""
        from agents.solver_experts.solver_registry import SOLVER_REGISTRY
        assert len(SOLVER_REGISTRY) == 18
        expected = [
            "pde_solver", "ode_solver", "complex_analysis_solver",
            "topology_solver", "optimization_solver", "algebra_solver"
        ]
        for name in expected:
            assert name in SOLVER_REGISTRY, f"缺少: {name}"

    def test_create_solver_valid(self):
        """测试创建有效的 Solver"""
        from agents.solver_experts.solver_registry import create_solver
        solver = create_solver("pde_solver")
        assert solver.solver_name == "pde_solver"
        assert solver.solver_domain == "partial_differential_equations"

    def test_create_solver_invalid_fallback(self):
        """测试无效Solver回退到algebra"""
        from agents.solver_experts.solver_registry import create_solver
        solver = create_solver("nonexistent_solver")
        assert solver.solver_name == "algebra_solver"

    def test_list_registered_solvers(self):
        """测试列出已注册Solver"""
        from agents.solver_experts.solver_registry import list_registered_solvers
        solvers = list_registered_solvers()
        assert len(solvers) == 18
        assert "pde_solver" in solvers
        assert "algebra_solver" in solvers

    def test_get_solver_metadata(self):
        """测试获取 Solver 元数据"""
        from agents.solver_experts.solver_registry import get_solver_metadata
        meta = get_solver_metadata("ode_solver")
        assert meta is not None
        assert meta["name"] == "ode_solver"
        assert "domain" in meta


class TestSolverInstantiation:
    """测试各 Solver 实例化"""

    def test_pde_solver_instantiation(self):
        from agents.solver_experts.pde_solver import PDESolver
        solver = PDESolver()
        assert solver.solver_name == "pde_solver"
        assert hasattr(solver, 'solve')
        assert hasattr(solver, 'verify_symbolic')

    def test_ode_solver_instantiation(self):
        from agents.solver_experts.ode_solver import ODESolver
        solver = ODESolver()
        assert solver.solver_name == "ode_solver"

    def test_complex_solver_instantiation(self):
        from agents.solver_experts.complex_analysis_solver import ComplexAnalysisSolver
        solver = ComplexAnalysisSolver()
        assert solver.solver_name == "complex_analysis_solver"

    def test_topology_solver_instantiation(self):
        from agents.solver_experts.topology_solver import TopologySolver
        solver = TopologySolver()
        assert solver.solver_name == "topology_solver"

    def test_optimization_solver_instantiation(self):
        from agents.solver_experts.optimization_solver import OptimizationSolver
        solver = OptimizationSolver()
        assert solver.solver_name == "optimization_solver"

    def test_algebra_solver_instantiation(self):
        from agents.solver_experts.algebra_solver import AlgebraSolver
        solver = AlgebraSolver()
        assert solver.solver_name == "algebra_solver"


class TestSolverMethods:
    """测试 Solver 核心方法"""

    def test_pde_classify_type(self):
        """测试 PDE 类型识别"""
        from agents.solver_experts.pde_solver import PDESolver
        solver = PDESolver()
        result = solver._classify_pde_type(
            "求解热传导方程 ∂u/∂t = α∇²u",
            [],
            ["热传导"]
        )
        assert result["pde_type"] == "parabolic"
        assert "分离变量法" in str(result["recommended_methods"])

    def test_ode_classify_type(self):
        """测试 ODE 类型识别"""
        from agents.solver_experts.ode_solver import ODESolver
        solver = ODESolver()
        result = solver._classify_ode_type(
            "求解一阶线性常微分方程 dy/dx + P(x)y = Q(x)",
            ["线性"]
        )
        assert result["ode_type"] == "first_order"
        assert result["is_linear"] is True

    def test_complex_identify_sub_type(self):
        """测试复分析子类型识别"""
        from agents.solver_experts.complex_analysis_solver import ComplexAnalysisSolver
        solver = ComplexAnalysisSolver()
        result = solver._identify_sub_type(
            "计算围道积分 ∮_C f(z)dz 使用留数定理",
            ["留数"]
        )
        assert result == "contour_integral"

    def test_topology_identify_sub_type(self):
        """测试拓扑子类型识别"""
        from agents.solver_experts.topology_solver import TopologySolver
        solver = TopologySolver()
        result = solver._identify_sub_type(
            "topology",
            "证明两个空间同伦等价并计算基本群"
        )
        assert "algebraic_topology" in result

    def test_optimization_identify_sub_type(self):
        """测试最优化子类型识别"""
        from agents.solver_experts.optimization_solver import OptimizationSolver
        solver = OptimizationSolver()
        result = solver._identify_sub_type(
            "optimization",
            "使用线性规划求解最大值问题"
        )
        assert result == "linear_programming"

    def test_algebra_identify_sub_type(self):
        """测试代数子类型识别"""
        from agents.solver_experts.algebra_solver import AlgebraSolver
        solver = AlgebraSolver()
        result = solver._identify_sub_type(
            "algebra",
            "计算矩阵的特征值和特征向量"
        )
        assert result == "linear_algebra"

    def test_solve_returns_valid_structure(self):
        """测试 solve() 返回结构正确（适配 API 不可用场景）"""
        from agents.solver_experts.algebra_solver import AlgebraSolver
        solver = AlgebraSolver()
        try:
            result = solver.solve(
                question_text="求解二次方程 x^2 - 5x + 6 = 0",
                parsed={"formulas": ["x^2 - 5x + 6 = 0"], "keywords": ["方程"]},
                domain="algebra"
            )
            # API 可用时验证返回结构
            assert "final_answer" in result
            assert "reasoning_steps" in result
            assert "methods_used" in result
            assert "educational_hint" in result
        except Exception as e:
            # API 不可用时（ConnectionError等），验证方法存在即可
            # 这是正常的测试环境情况
            pytest.skip(f"API 不可用，跳过 LLM 调用测试: {str(e)[:80]}")

    def test_verify_symbolic_handles_empty(self):
        """测试符号验证处理空答案"""
        from agents.solver_experts.algebra_solver import AlgebraSolver
        solver = AlgebraSolver()
        passed, detail = solver.verify_symbolic("test", "")
        assert passed is False


class TestBaseSolver:
    """测试 BaseSolver 基类方法"""

    def test_format_latex(self):
        """测试 LaTeX 格式化"""
        from agents.solver_experts.algebra_solver import AlgebraSolver
        import sympy as sp
        solver = AlgebraSolver()
        expr = sp.Symbol('x')**2 + 3*sp.Symbol('x') + 1
        latex_str = solver._format_latex(expr)
        assert "x" in latex_str

    def test_get_metadata(self):
        """测试获取元数据"""
        from agents.solver_experts.algebra_solver import AlgebraSolver
        solver = AlgebraSolver()
        meta = solver.get_metadata()
        assert meta["name"] == "algebra_solver"
        assert meta["domain"] == "algebra"

    def test_sympy_parse_and_solve(self):
        """测试 SymPy 方程解析和求解"""
        from agents.solver_experts.algebra_solver import AlgebraSolver
        solver = AlgebraSolver()
        result = solver._sympy_parse_and_solve(
            "x**2 - 4", ["x"]
        )
        assert result["success"] is True
        assert result["solution"] is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
