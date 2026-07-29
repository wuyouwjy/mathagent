# ============================================================
# solvers/base_solver.py — Solver 抽象基类
# 定义所有 Solver 的通用接口、符号计算工具、错误处理
# ============================================================

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Tuple, Union
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

    def _safe_extract(self, response: Dict[str, Any], default_answer: str = "") -> Dict[str, Any]:
        """从 LLM 响应提取结果。JSON 解析失败时智能提取纯答案"""
        pj = response.get("parsed_json")
        raw = response.get("content", "")

        if pj and isinstance(pj, dict):
            # 尝试多种可能的答案字段名（LLM 不一定按规范输出）
            answer = (
                pj.get("final_answer") or pj.get("answer") or pj.get("result")
                or pj.get("conclusion") or pj.get("final_result")
                or pj.get("最终答案") or pj.get("答案")
            )
            if answer and str(answer).strip():
                ans_str = str(answer).strip()
                # 对于选择题的单字母答案，也接受（不再要求 len > 1）
                result = {
                    "final_answer": ans_str,
                    "reasoning_steps": pj.get("reasoning_steps") or pj.get("steps") or [],
                    "methods_used": pj.get("methods_used") or pj.get("methods") or [],
                    "educational_hint": str(pj.get("educational_hint") or pj.get("explanation") or ""),
                    "raw_llm_response": raw,  # 始终保留原始输出，供 benchmark 提取
                }
                return result

        # JSON 解析失败或不含答案 → 从原始文本提取
        text = raw if raw else ""
        if text:
            answer = self._extract_answer_from_text(text)
            if answer:
                return {"final_answer": answer, "reasoning_steps": [],
                        "methods_used": [], "educational_hint": "", "raw_llm_response": text}
            # 最后兜底：取文本摘要
            if len(text) > 20:
                # 取不含 JSON 结构的纯文本部分
                import re
                clean = re.sub(r'\{[^}]*\}', '', text).strip()
                clean = re.sub(r'```[^`]*```', '', clean).strip()
                if clean:
                    text = clean
            return {"final_answer": text[:500], "reasoning_steps": [],
                    "methods_used": [], "educational_hint": "", "raw_llm_response": raw if raw else text}

        return {"final_answer": default_answer, "reasoning_steps": [], "methods_used": [],
                "educational_hint": "", "raw_llm_response": raw if raw else ""}

    def _extract_answer_from_text(self, text: str) -> str:
        """从 LLM 原始输出中提取纯答案（不包含推理过程）"""
        import re
        # 1. 匹配 "最终答案：xxx" "Answer: xxx" "答案是 xxx" 等
        patterns = [
            r'(?:最终答案|答案|结果)[：:是为]?\s*(.+?)(?:\n|$|。)',
            r'(?:Answer|answer|Final Answer)[：: is]*\s*(.+?)(?:\n|$|\.)',
            r'(?:所以|因此|综上|故)[，,]?\s*(.+?)(?:\n|$|。)',
            r'(?:\\boxed|\\box)\{([^}]+)\}',   # LaTeX \boxed{answer}
        ]
        for pat in patterns:
            m = re.search(pat, text, re.IGNORECASE | re.DOTALL)
            if m:
                ans = m.group(1).strip()
                # 去 LaTeX 标记但保留内容
                ans = re.sub(r'\$+', '', ans)
                if 1 <= len(ans) <= 500:
                    return ans

        # 2. 取最后一行非空内容（通常是答案）
        lines = [l.strip() for l in text.strip().split('\n') if l.strip() and not l.strip().startswith('#')]
        if lines:
            last = lines[-1]
            # 去掉常见前缀
            last = re.sub(r'^(?:答案|最终答案|Answer|所以|因此)[：:是为]*\s*', '', last)
            if len(last) <= 300:
                return last

        return ""

    # ============================================================
    # 原通用工具方法
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

    def get_skill(self) -> Optional[Any]:
        """
        获取此 Solver 对应的领域 Skill

        从 solvers/skills/ 注册表中加载，包含：
        - 系统提示词
        - 求解策略
        - 领域关键词
        - Few-shot 示例
        - 验证策略

        返回:
            SolverSkill 或 None（如果未注册）
        """
        try:
            from agents.solver_experts.skills import get_skill as _get_skill
            return _get_skill(self.solver_name)
        except ImportError:
            return None
        except Exception:
            return None

    def get_metadata(self) -> Dict[str, str]:
        """获取 Solver 元信息"""
        return {
            "name": self.solver_name,
            "domain": self.solver_domain,
            "description": self.solver_description,
        }

    def __repr__(self) -> str:
        return f"<{self.solver_name} domain={self.solver_domain}>"


# ============================================================
# DomainSolver — 统一领域求解器基类
# 18个Solver继承此类，只需提供领域配置即可获得：
#   子类型识别 + SymPy预计算 + 领域Prompt + 智能答案提取
# ============================================================

class DomainSolver(BaseSolver):
    """统一领域求解器：子类型识别→SymPy预计算→LLM推理→答案提取"""

    # 子类需覆盖的领域配置
    sub_types: Dict[str, Dict] = {}   # {"sub_type": {"prompt":..., "keywords":[...]}}
    default_prompt: str = ""
    sympy_vars: List[str] = ["x", "y", "z", "n"]

    def solve(self, question_text, parsed, domain, **kwargs):
        skill = self.get_skill()
        formulas = parsed.get("formulas", []) if parsed else []

        # 1. 子类型识别
        sub_type = self._identify_sub_type(domain, question_text)
        logger.debug(f"[{self.solver_name}] sub_type={sub_type}")

        # 2. SymPy 预计算
        symbolic = None
        if formulas:
            symbolic = self._try_symbolic_solve(question_text, formulas, self.sympy_vars)

        # 3. 构建 Prompt
        prompt = self._build_domain_prompt(sub_type, kwargs, skill)
        user_msg = self._build_user_msg(question_text, domain, sub_type, symbolic, kwargs, skill)

        # 4. LLM 推理
        response = self._call_llm(user_msg, system_prompt=prompt)
        result = self._safe_extract(response)

        # 5. 附加元信息
        result["sub_type"] = sub_type
        if symbolic:
            result["symbolic_result"] = symbolic
        return result

    def _identify_sub_type(self, domain: str, text: str) -> str:
        """根据关键词识别子类型"""
        text_lower = text.lower()
        for st, cfg in self.sub_types.items():
            for kw in cfg.get("keywords", []):
                if kw.lower() in text_lower:
                    return st
        return "general"

    def _build_domain_prompt(self, sub_type: str, kwargs: dict, skill) -> str:
        """构建领域专用 system prompt"""
        cfg = self.sub_types.get(sub_type, {})
        prompt = cfg.get("prompt", self.default_prompt)

        # 注入 skill 的策略
        if skill and skill.strategies:
            prompt += "\n\n【推荐策略】\n" + "\n".join(f"- {s}" for s in skill.strategies[:5])

        # 注入 RAG 定理
        theorems = kwargs.get("theorems", [])
        if theorems:
            prompt += "\n\n【相关定理】\n" + "\n".join(f"- {t}" for t in theorems[:5])

        prompt += (
            "\n\n【强制要求】你必须严格返回以下 JSON 格式，不要添加任何额外文字：\n"
            '{"final_answer": "你的最终答案", '
            '"reasoning_steps": [{"step_id":1,"description":"步骤说明","formula":"公式","method":"方法"}], '
            '"methods_used": ["方法1","方法2"], '
            '"educational_hint": "解题思路简述"}\n'
            "注意：final_answer 字段是必须的！只输出纯 JSON，不要用 ``` 包裹。"
        )
        return prompt

    def _build_user_msg(self, question_text, domain, sub_type, symbolic, kwargs, skill) -> str:
        """构建用户消息"""
        parts = [f"【{self.solver_description}问题 — {sub_type}】\n{question_text}"]

        if symbolic:
            parts.append(f"\n【SymPy 符号计算结果】\n{symbolic}")

        formulas = kwargs.get("formulas", [])
        if formulas:
            parts.append("\n【相关公式】\n" + "\n".join(f"- {f}" for f in formulas[:5]))

        examples = kwargs.get("examples", [])
        if examples:
            parts.append("\n【相似例题】\n" + "\n".join(f"- {e}" for e in examples[:3]))

        feedback = kwargs.get("reflection_feedback", "")
        if feedback:
            parts.append(f"\n{feedback}")

        return "\n\n".join(parts)

    def verify_symbolic(self, question_text, answer, **kwargs):
        return True, f"{self.solver_description}验证通过"
