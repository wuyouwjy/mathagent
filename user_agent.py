"""user_agent.py — ReasoningAgent for 2026 Challenge Cup (T3).

LangGraph-based multi-agent math reasoning system adapted from the ICMAnew-main
architecture (50+ score). Replaces the T2 svragent-based multi-route pipeline
with a full graph-based orchestration: classify → solve (reasoning + Python) →
cross-validate → coordinate, with semantic arbitration and reconciliation when
answers conflict.

Key improvements over T2 (15.18):
- **LangGraph orchestration**: Full multi-node graph with conditional routing
- **18 domain skill documents**: Subject-specific formulas, theorems, and
  Python verification snippets loaded per-problem
- **Parallel reasoning + Python verification**: LLM reasons while SymPy
  independently verifies, both running concurrently in solving subgraph
- **Cross-validation**: Symbolic/numeric answer matching with contract checking
- **Semantic arbiter**: LLM-based judge selects between conflicting candidates
- **Time-budget-aware retry**: Compressed prefill retries when token-exhausted,
  reserve-margin pricing for every optional stage
- **Answer formatting pipeline**: Incomplete-answer detection, proof-body
  attachment, contract field recovery, noise cleanup
- **Objective question fast path**: Choice/true-false/fill-in-blank handled
  with concise two-line contract, avoiding full proof generation

Architecture:
    solve(problem, metadata)
      └── MathAgentGraph.run(initial_state)
           ├── input_node: extract idx
           ├── classifier_node: LLM-prefilled domain classification (18 categories)
           ├── solving_subgraph: parallel fan-out
           │    ├── reasoning_agent: structured 4-section output
           │    ├── python_agent: SymPy verification code generation + execution
           │    └── cross_validator: answer matching + routing decision
           ├── reconciliation_node (conditional): retry with hints
           ├── semantic_arbiter_node (conditional): select best candidate
           └── coordinator_node: format final_response

Platform interface (fixed by competition rules):
    from user_agent import ReasoningAgent
    agent = ReasoningAgent(client=official_client)
    result = agent.solve(problem="...", metadata={"idx": 0})
    # → {"final_response": "...", "trace": [...]}
"""

from __future__ import annotations

import os as _os
import sys as _sys
from typing import Any, Dict

# ── 防线 1：sys.path 自举（任何加载形态不抛异常）──
# 平台用 importlib 按路径加载本文件时可能不把仓库根目录加入 sys.path，
# 导致多模块 import 报 ImportError。此处自举：把本文件所在目录（或 CWD）
# 插入 sys.path，确保 graph / utils 等包在任何加载形态下都能被找到。
_HERE = ""
try:
    _HERE = _os.path.dirname(_os.path.abspath(__file__))
except Exception:  # noqa: BLE001 - exec/沙箱加载器可能不提供 __file__
    _HERE = ""
for _cand in (_HERE, _os.getcwd()):
    try:
        if (_cand and _os.path.isfile(_os.path.join(_cand, "graph", "main_graph.py"))
                and _cand not in _sys.path):
            _sys.path.insert(0, _cand)
    except Exception:  # noqa: BLE001
        pass

from graph import MathAgentGraph
from utils.llm.client_tuning import cap_internal_retries, raise_socket_timeout
from utils.skills_util.loader import SkillsLoader
from utils.executor.client import PythonMCPClient
from utils.budget.token import TokenBudget
from utils.logger import get_logger
from graph.state import create_initial_state

# ==================== PARTICIPANT DESIGN AREA START ====================


class ReasoningAgent:
    """Math reasoning agent — T3 LangGraph multi-agent architecture.

    Uses a LangGraph graph with parallel reasoning + Python verification,
    cross-validation, semantic arbitration, and answer formatting.

    The competition platform instantiates this class as::

        agent = ReasoningAgent(client=official_client)

    then calls::

        agent.solve(problem="...", metadata={"idx": 0})
    """

    def __init__(self, client: Any, *args: Any, **kwargs: Any) -> None:
        self.client = client
        self.logger = get_logger("ReasoningAgent")
        # Best-effort raise socket timeout; the platform keeps ownership of
        # the client, model and rate limiting.
        self.transport_tuning = {
            "socket_timeout": raise_socket_timeout(client, logger=self.logger),
            "internal_retries": cap_internal_retries(client, logger=self.logger),
        }
        self.skills_loader = SkillsLoader()
        self.mcp_client = PythonMCPClient()
        self.graph = MathAgentGraph(
            client=client, skills_loader=self.skills_loader, mcp_client=self.mcp_client)
        self.logger.info("ReasoningAgent (T3) initialized")

    def solve(self, problem: str, metadata: Dict | None = None, *args: Any, **kwargs: Any) -> Dict:
        """Solve a math problem and return the competition-format result.

        Returns a dict with:
            ``final_response`` — the answer string for the Judger
            ``trace`` — list of trace entries for diagnostics
        """
        # 平台 runner 实测可能以位置参数传 metadata（solve(problem, meta)），
        # 或完全不传；此处归一化，任何调用形态都不抛 TypeError。
        if metadata is None and args and isinstance(args[0], dict):
            metadata = args[0]
        meta = metadata if isinstance(metadata, dict) else {}
        idx = meta.get("idx", -1)
        try:
            self.logger.info(f"Solving problem {idx}")
            initial = create_initial_state(str(problem or ""), meta)
            final_state = self.graph.run(initial, token_budget=TokenBudget())
            result = {
                "final_response": final_state.get("final_response", "无法生成答案"),
                "trace": self._build_trace(final_state),
            }
            self._validate_output(result)
            return result
        except Exception as e:
            self.logger.error(f"Error solving problem {idx}: {e}")
            return {
                "final_response": "解题过程中出现错误，无法给出完整答案。",
                "trace": [{"step": "error", "content": str(e), "idx": idx}],
            }

    def __call__(self, problem: str, *args: Any, **kwargs: Any) -> Dict:
        """调用方式防御：部分 runner 以 agent(problem) 形式调用。"""
        return self.solve(problem, *args, **kwargs)

    def run(self, problem: str, *args: Any, **kwargs: Any) -> Dict:
        """调用方式防御：部分 runner 以 agent.run(problem) 形式调用。"""
        return self.solve(problem, *args, **kwargs)

    def _build_trace(self, state: dict) -> list:
        trace = []
        if state.get("category"):
            trace.append({
                "step": "classification",
                "category": state.get("category"),
                "question_mode": state.get("question_mode", "computation"),
                "confidence": state.get("category_confidence", 0.0),
                "candidates": state.get("candidate_categories", []),
                "tools": [{
                    "name": "category_candidates",
                    "stages": state.get("classification_stages_used", []),
                    "selected": state.get("category"),
                }],
            })
        # 题库检索：检索到什么、是否真的写进了两个子代理的提示词，都要留证。
        examples = state.get("retrieved_examples")
        if examples is not None:
            reasoning_chars = int(state.get("reasoning_reference_chars", 0) or 0)
            python_chars = int(state.get("python_reference_chars", 0) or 0)
            trace.append({
                "step": "database_retrieval",
                "count": len(examples),
                "injected_into": [name for name, chars in
                                  (("reasoning_agent", reasoning_chars),
                                   ("python_agent", python_chars)) if chars > 0],
                "thinking": {
                    "purpose": "解题前用原题检索竞赛题库，把最相似的题目与解答作为参考"
                               "示例注入推理与验证两个子代理。",
                    "reference_block_chars": {
                        "reasoning_agent": reasoning_chars,
                        "python_agent": python_chars,
                    },
                },
                "tools": [{
                    "name": "tfidf_database_query",
                    "top_k": len(examples),
                    "results": [
                        {
                            "rank": i,
                            "similarity": ex.get("similarity", 0.0),
                            "source": ex.get("source", ""),
                            "problem_excerpt": self._truncate(ex.get("problem", ""), 600),
                            "solution_excerpt": self._truncate(ex.get("solution", ""), 900),
                            "problem_chars": len(str(ex.get("problem") or "")),
                            "solution_chars": len(str(ex.get("solution") or "")),
                        }
                        for i, ex in enumerate(examples, 1)
                        if isinstance(ex, dict)
                    ],
                }],
            })
        if state.get("reasoning_result"):
            rr = state["reasoning_result"]
            trace.append({
                "step": "reasoning",
                "attempts": state.get("reasoning_attempts", 0),
                "answer": rr.get("answer", ""),
                "steps_count": len(rr.get("steps", [])),
                "thinking": {
                    "analysis": rr.get("analysis", ""),
                    "steps": rr.get("steps", []),
                    "final_answer": rr.get("answer", ""),
                    "validation_points": rr.get("validation_points", []),
                    "answer_source": rr.get("answer_source", "parsed_sections"),
                    "raw_response_excerpt": self._excerpt(
                        state.get("reasoning_raw_response", "")),
                },
                "tools": [{
                    "name": "skill_document",
                    "category": state.get("category", ""),
                    "purpose": "加载对应数学领域 skill 文档作为解题参考。",
                }, {
                    "name": "database_reference_examples",
                    "count": len(state.get("retrieved_examples") or []),
                    "chars_injected": int(state.get("reasoning_reference_chars", 0) or 0),
                    "purpose": "题库相似题与解答，随 skill 文档一并进入推理提示词。",
                }, {
                    "name": "reasoning_llm",
                    "attempts": state.get("reasoning_trace", []),
                    "max_attempts_used": state.get("reasoning_attempts", 0),
                    "output_schema": ["analysis", "steps", "answer", "validation_points"],
                }],
            })
        if state.get("python_output"):
            po = state["python_output"]
            python_code = state.get("python_code", "")
            trace.append({
                "step": "python_verification",
                "attempts": state.get("python_attempts", 0),
                "success": po.get("success", False),
                "answer": po.get("answer", ""),
                "thinking": {
                    "purpose": "用生成的 Python/SymPy 代码独立复核答案。",
                    "code_summary": self._truncate(python_code, 1600),
                    "expected_output_marker": "最终答案:",
                    "extracted_answer": po.get("answer", ""),
                    "evidence_status": po.get("evidence_status",
                                               state.get("python_evidence_status", "")),
                    "evidence_summary": self._truncate(
                        po.get("evidence_summary",
                               state.get("python_evidence_summary", "")), 1000),
                    "contradictions": state.get("python_contradictions",
                                                 po.get("contradictions", [])),
                },
                "tools": [{
                    "name": "database_reference_examples",
                    "count": len(state.get("retrieved_examples") or []),
                    "chars_injected": int(state.get("python_reference_chars", 0) or 0),
                    "purpose": "题库相似题与解答，随验证脚本一并进入 Python 提示词。",
                }, {
                    "name": "python_code_generation",
                    "attempts": state.get("python_trace", []),
                    "code_length": len(python_code),
                }, {
                    "name": "python_executor",
                    "backend": po.get("execution_backend", ""),
                    "success": po.get("success", False),
                    "execution_time": po.get("execution_time", 0.0),
                    "stdout": self._truncate((po.get("stdout") or "").strip(), 1000),
                    "stderr": self._truncate((po.get("stderr") or "").strip(), 1000),
                }],
            })
        if state.get("validation_details"):
            trace.append({
                "step": "validation",
                "status": state.get("validation_status"),
                "validated_answer": state.get("validated_answer", ""),
                "thinking": {
                    "problem_type": state["validation_details"].get("problem_type", ""),
                    "reason": state["validation_details"].get("reason", ""),
                    "confidence": state["validation_details"].get("confidence", 0.0),
                    "python_evidence_status": state["validation_details"].get(
                        "python_evidence_status", state.get("python_evidence_status", "")),
                    "python_evidence_summary": self._truncate(
                        state["validation_details"].get(
                            "python_evidence_summary",
                            state.get("python_evidence_summary", "")), 1000),
                    "python_contradictions": state["validation_details"].get(
                        "python_contradictions", state.get("python_contradictions", [])),
                },
                "tools": [{
                    "name": "answer_matcher",
                    "details": state.get("validation_details", {}),
                }],
            })
        if state.get("validation_history"):
            trace.append({
                "step": "validation_history",
                "count": len(state["validation_history"]),
                "tools": [{
                    "name": "validation_history",
                    "rounds": state["validation_history"],
                }],
            })
        if state.get("semantic_arbiter_trace"):
            trace.append({
                "step": "semantic_arbitration",
                "status": state.get("semantic_arbiter_status", ""),
                "decision": state.get("semantic_arbiter_decision", ""),
                "answer_locked": state.get("answer_locked", False),
                "thinking": {
                    "purpose": "在不依赖题型关键词的情况下，从既有答案候选中选择完整正确答案。",
                    "policy": "select_existing_candidate_or_abstain",
                },
                "tools": [{
                    "name": "semantic_arbiter_llm",
                    "attempts": state.get("semantic_arbiter_attempts", 0),
                    "rounds": state.get("semantic_arbiter_trace", []),
                }],
            })
        if state.get("reconciliation_trace"):
            trace.append({
                "step": "reconciliation",
                "count": len(state["reconciliation_trace"]),
                "thinking": {
                    "purpose": "当推理答案与 Python 验证不一致或不确定时，决定是否重跑子图。",
                },
                "tools": [{
                    "name": "reconciliation_policy",
                    "rounds": state["reconciliation_trace"],
                }],
            })
        if state.get("final_response"):
            trace.append({
                "step": "coordination",
                "content": state.get("coordination_detail", ""),
                "response_length": len(state["final_response"]),
                "thinking": {
                    "purpose": "将推理步骤、验证结果与最终答案整理为面向读者的输出。",
                },
                "tools": [
                    {
                        "name": "coordinator_llm",
                        "content_length": len(state.get("coordination_detail", "")),
                        "skipped_for_locked_answer": bool(state.get("answer_locked")),
                    },
                    {
                        "name": "answer_formatter",
                        "final_response_length": len(state.get("final_response", "")),
                    },
                ],
                "fallback_source": state.get("fallback_source", ""),
            })
        if state.get("node_timings") or state.get("_time_budget"):
            trace.append({
                "step": "timing",
                "thinking": {
                    "purpose": "记录各阶段实测耗时与时间预算消耗，用于定位超时瓶颈。",
                },
                "tools": [{
                    "name": "time_budget",
                    "budget": state.get("_time_budget", {}),
                    "node_elapsed": state.get("node_timings", []),
                    "llm_calls": state.get("_llm_spend_log", []),
                    "transport_tuning": getattr(self, "transport_tuning", {}),
                }],
            })
        return trace

    @staticmethod
    def _truncate(value: str, limit: int) -> str:
        if not isinstance(value, str):
            value = str(value or "")
        if len(value) <= limit:
            return value
        return value[:limit].rstrip() + "...[truncated]"

    @staticmethod
    def _excerpt(value: str, head: int = 600, tail: int = 1400) -> str:
        """头 + 尾节选：截断响应的结论区在尾部，只截头会丢掉最有证据价值的部分。"""
        if not isinstance(value, str):
            value = str(value or "")
        if len(value) <= head + tail + 40:
            return value
        omitted = len(value) - head - tail
        return f"{value[:head]}\n……[中略 {omitted} 字符]……\n{value[-tail:]}"

    def _validate_output(self, result: dict) -> None:
        import json
        assert isinstance(result, dict), "返回值必须是dict"
        assert "final_response" in result, "必须包含final_response"
        assert isinstance(result["final_response"], str), "final_response必须是字符串"
        assert result["final_response"].strip(), "final_response不能为空"
        json.dumps(result, ensure_ascii=False)


# ===================== PARTICIPANT DESIGN AREA END =====================
