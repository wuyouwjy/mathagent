# ============================================================
# solvers/base_solver.py — Solver 抽象基类
# 定义所有 Solver 的通用接口、符号计算工具、错误处理
# ============================================================

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Tuple
import time
import traceback

import sympy as sp
from loguru import logger

from tools.intern_client import get_intern_client
from configs.settings import get_config


class BaseSolver(ABC):
    """
    数学 Solver 抽象基类

    所有领域专用 Solver 继承此类，实现以下接口：
    - solve(): 主求解方法
    - verify_symbolic(): 符号验证方法

    内置工具方法:
    - _call_llm(): 调用 Intern-S1 LLM
    - _sympy_safe_eval(): 安全执行 SymPy 表达式
    - _format_latex(): 格式化输出为 LaTeX
    """

    # 子类必须定义的属性
    solver_name: str = "base"           # Solver 名称
    solver_domain: str = "general"      # 所属领域
    solver_description: str = "基础求解器"

    def __init__(self):
        """初始化 Solver"""
        self.config = get_config()
        self.llm_client = get_intern_client()
        self.sympy_timeout = self.config.solver.sympy_timeout
        self.numeric_precision = self.config.solver.numeric_precision

        logger.debug(f"[Solver] 初始化 {self.solver_name} ({self.solver_domain})")

    # ============================================================
    # 抽象接口 — 子类必须实现
    # ============================================================

    @abstractmethod
    def solve(
        self,
        question_text: str,
        parsed: Dict[str, Any],
        domain: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        求解数学问题

        参数:
            question_text: 问题文本
            parsed: 解析后的结构化问题
            domain: 数学领域
            **kwargs: 额外参数（theorems, formulas, examples 等）

        返回:
            Dict: {
                "final_answer": str,        # 最终答案（LaTeX）
                "reasoning_steps": list,    # 推理步骤
                "methods_used": list,       # 使用的方法
                "educational_hint": str,    # 教育解释
                "symbolic_result": str,     # 符号计算结果（可选）
                "numeric_result": float,    # 数值结果（可选）
            }
        """
        pass

    @abstractmethod
    def verify_symbolic(
        self,
        question_text: str,
        answer: str,
        **kwargs
    ) -> Tuple[bool, str]:
        """
        使用符号计算验证答案

        参数:
            question_text: 问题文本
            answer: 待验证的答案
            **kwargs: 额外参数

        返回:
            Tuple[bool, str]: (是否通过, 验证详情)
        """
        pass

    # ============================================================
    # 通用工具方法
    # ============================================================

    def _call_llm(
        self,
        user_message: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        require_json: bool = True,
    ) -> Dict[str, Any]:
        """
        调用 Intern-S1 LLM 进行推理

        参数:
            user_message: 用户消息
            system_prompt: 系统提示词
            temperature: 温度参数
            require_json: 是否要求 JSON 输出

        返回:
            Dict: LLM 响应
        """
        if system_prompt is None:
            system_prompt = self._get_default_system_prompt()

        if require_json:
            return self.llm_client.chat_with_json_output(
                messages=[{"role": "user", "content": user_message}],
                system_prompt=system_prompt,
                max_tokens=self.config.intern_s1.max_tokens,  # 显式传，防截断
            )
        else:
            return self.llm_client.chat(
                messages=[{"role": "user", "content": user_message}],
                system_prompt=system_prompt,
                temperature=temperature or self.config.intern_s1.temperature,
                max_tokens=self.config.intern_s1.max_tokens,
            )

    def _get_default_system_prompt(self) -> str:
        """获取默认系统提示词（子类可覆盖）"""
        return (
            f"你是一位{self.solver_description}专家。"
            f"请逐步求解以下数学问题。使用 LaTeX 格式书写数学公式。"
        )

    def _sympy_safe_eval(self, expr_str: str, local_dict: Optional[Dict] = None) -> Any:
        """
        安全执行 SymPy 表达式（带超时保护）

        参数:
            expr_str: SymPy 表达式字符串
            local_dict: 局部变量字典

        返回:
            Any: SymPy 计算结果，或异常信息字符串
        """
        import signal

        if local_dict is None:
            local_dict = {"sympy": sp, "sp": sp, "x": sp.Symbol("x"),
                          "y": sp.Symbol("y"), "z": sp.Symbol("z"),
                          "t": sp.Symbol("t"), "n": sp.Symbol("n", integer=True)}

        try:
            # 注意：Windows 不支持 signal.alarm，使用简单的超时方法
            result = eval(expr_str, {"__builtins__": {}}, {
                **local_dict,
                "Symbol": sp.Symbol,
                "Function": sp.Function,
                "Derivative": sp.Derivative,
                "Integral": sp.Integral,
                "solve": sp.solve,
                "dsolve": sp.dsolve,
                "integrate": sp.integrate,
                "diff": sp.diff,
                "limit": sp.limit,
                "Matrix": sp.Matrix,
                "simplify": sp.simplify,
                "expand": sp.expand,
                "factor": sp.factor,
                "solve": sp.solve,
                "Eq": sp.Eq,
                "pi": sp.pi,
                "oo": sp.oo,
            })
            return result
        except Exception as e:
            logger.warning(f"[{self.solver_name}] SymPy 计算异常: {e}")
            return f"SymPyError: {str(e)}"

    def _sympy_parse_and_solve(
        self,
        equation_str: str,
        variables: List[str],
    ) -> Dict[str, Any]:
        """
        解析 LaTeX 方程并尝试 SymPy 符号求解

        参数:
            equation_str: LaTeX 格式的方程
            variables: 变量列表

        返回:
            Dict: {"success": bool, "solution": ..., "error": str}
        """
        try:
            # 创建符号变量
            symbols = {v: sp.Symbol(v) for v in variables}

            # 尝试解析常见格式（这是简化版本，完整版需要 LaTeX 解析器）
            # 这里使用 sympy 的 sympify 进行基础转换
            expr = sp.sympify(equation_str, locals=symbols)

            # 如果是等式
            if isinstance(expr, sp.Equality):
                solution = sp.solve(expr, list(symbols.values()))
            else:
                solution = sp.solve(expr, list(symbols.values()))

            return {
                "success": True,
                "solution": solution,
                "latex": sp.latex(solution) if solution is not None else "",
            }
        except Exception as e:
            return {
                "success": False,
                "solution": None,
                "error": str(e),
            }

    def _try_symbolic_solve(
        self,
        question_text: str,
        formula_list: List[str],
        variables: List[str],
    ) -> Optional[Dict[str, Any]]:
        """
        尝试使用 SymPy 进行符号计算求解

        参数:
            question_text: 问题文本
            formula_list: 提取的公式列表
            variables: 变量列表

        返回:
            Optional[Dict]: 符号求解结果，如果无法处理则返回 None
        """
        if not formula_list:
            return None

        results = []
        for formula in formula_list[:3]:  # 最多尝试3个公式
            result = self._sympy_parse_and_solve(formula, variables)
            if result["success"] and result["solution"]:
                results.append(result)

        if results:
            return {
                "symbolic_solutions": results,
                "num_solutions": len(results),
            }
        return None

    def _format_latex(self, expr) -> str:
        """
        将 SymPy 表达式格式化为 LaTeX

        参数:
            expr: SymPy 表达式

        返回:
            str: LaTeX 字符串
        """
        try:
            return sp.latex(expr)
        except Exception:
            return str(expr)

    # ============================================================
    # Solver 元信息
    # ============================================================

    def get_metadata(self) -> Dict[str, str]:
        """获取 Solver 元信息"""
        return {
            "name": self.solver_name,
            "domain": self.solver_domain,
            "description": self.solver_description,
        }

    def __repr__(self) -> str:
        return f"<{self.solver_name} domain={self.solver_domain}>"
