"""Three-stage Plan->Solve->Verify reasoning agent for Challenge Cup 2026."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


PLAN_SYSTEM_PROMPT = (
    "You are a math contest strategy agent. Read the problem and produce a "
    "concise solution plan. Do not compute the final answer yet."
)

SOLVE_SYSTEM_PROMPT = (
    "You are a math contest solving agent. Use the problem and the plan to solve "
    "the problem carefully. Show the key derivation and propose a final answer."
)

VERIFY_SYSTEM_PROMPT = (
    "You are a math contest verification agent. Check the proposed solution for "
    "mistakes, then return only one JSON object with keys: answer, explanation. "
    "The answer should be the final answer to the problem."
)


def _extract_last_json_dict(text: str) -> Optional[Dict[str, Any]]:
    decoder = json.JSONDecoder()
    parsed_objects: List[Dict[str, Any]] = []
    for match in re.finditer(r"\{", text):
        try:
            parsed, _ = decoder.raw_decode(text[match.start():])
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            parsed_objects.append(parsed)
    return parsed_objects[-1] if parsed_objects else None


def extract_json_object(text: str) -> Optional[Dict[str, Any]]:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped, flags=re.IGNORECASE)
        stripped = re.sub(r"\s*```$", "", stripped)
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        parsed = _extract_last_json_dict(text)
        if parsed is None:
            return None
    return parsed if isinstance(parsed, dict) else None


def extract_answer_value(text: str) -> Optional[str]:
    answer_matches = re.findall(
        r'"answer"\s*:\s*"?([-+]?\d+(?:\.\d+)?)"?',
        text,
        flags=re.IGNORECASE,
    )
    if answer_matches:
        return answer_matches[-1]

    phrase_patterns = [
        r"(?:answer|sum|remainder|result|value)\s+(?:is|=)\s*([-+]?\d+(?:\.\d+)?)",
        r"(?:final answer)\s*[:=]?\s*([-+]?\d+(?:\.\d+)?)",
    ]
    for pattern in phrase_patterns:
        matches = re.findall(pattern, text, flags=re.IGNORECASE)
        if matches:
            return matches[-1]
    return None


@dataclass
class AgentConfig:
    plan_temperature: float = 0.2
    solve_temperature: float = 0.2
    verify_temperature: float = 0.2
    plan_max_tokens: int = 12288
    solve_max_tokens: int = 12288
    verify_max_tokens: int = 12288


class ReasoningAgent:
    """Three-stage Plan->Solve->Verify reasoning agent."""

    def __init__(self, client, config: Optional[AgentConfig] = None, *args, **kwargs) -> None:
        self.client = client
        self.config = config or AgentConfig()

    def solve(self, problem: str, metadata: Dict) -> Dict:
        idx = metadata.get("idx", 0)
        trace: List[Dict] = []

        plan, plan_trace = self._plan(problem, idx)
        trace.extend(plan_trace)

        solution, solve_trace = self._do_solve(problem, plan, idx)
        trace.extend(solve_trace)

        final_response, verify_trace = self._verify(problem, plan, solution, idx)
        trace.extend(verify_trace)

        return {
            "final_response": final_response,
            "trace": trace,
        }

    def _plan(self, problem: str, idx: int) -> Tuple[str, List[Dict]]:
        messages = [
            {"role": "system", "content": PLAN_SYSTEM_PROMPT},
            {"role": "user", "content": f"Problem ID: {idx}\n\nProblem:\n{problem}"},
        ]
        plan = self.client.chat(
            messages=messages,
            temperature=self.config.plan_temperature,
            max_tokens=self.config.plan_max_tokens,
        )
        return plan, [{"step": "plan", "content": plan}]

    def _do_solve(self, problem: str, plan: str, idx: int) -> Tuple[str, List[Dict]]:
        messages = [
            {"role": "system", "content": SOLVE_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Problem ID: {idx}\n\nProblem:\n{problem}\n\n"
                    f"Solution plan:\n{plan}\n\nSolve the problem and propose the final answer."
                ),
            },
        ]
        solution = self.client.chat(
            messages=messages,
            temperature=self.config.solve_temperature,
            max_tokens=self.config.solve_max_tokens,
        )
        return solution, [{"step": "model_call", "content": solution}]

    def _verify(
        self, problem: str, plan: str, solution: str, idx: int
    ) -> Tuple[str, List[Dict]]:
        messages = [
            {"role": "system", "content": VERIFY_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Problem ID: {idx}\n\nProblem:\n{problem}\n\n"
                    f"Plan:\n{plan}\n\nProposed solution:\n{solution}\n\n"
                    'Return only JSON like {"answer": "your answer here", "explanation": "short reason"}.'
                ),
            },
        ]
        raw_response = self.client.chat(
            messages=messages,
            temperature=self.config.verify_temperature,
            max_tokens=self.config.verify_max_tokens,
        )
        trace = [{"step": "verify", "content": raw_response}]

        final_response = self._extract_final_answer(raw_response, solution)
        trace.append({"step": "finalize", "content": final_response})
        return final_response, trace

    def _extract_final_answer(self, raw_response: str, solution_fallback: str) -> str:
        # 1) JSON from verify response
        parsed = extract_json_object(raw_response)
        if parsed and "answer" in parsed and parsed["answer"] is not None:
            answer_str = str(parsed["answer"]).strip()
            if answer_str:
                return answer_str

        # 2) Regex fallback for JSON answer when LaTeX backslashes break json.loads
        m = re.search(r'"answer"\s*:\s*"((?:[^"\\]|\\.)*)"', raw_response, re.DOTALL)
        if m:
            candidate = m.group(1).strip()
            if candidate:
                return candidate

        # 3) Numeric regex from verify text
        fallback = extract_answer_value(raw_response)
        if fallback:
            return fallback

        # 4) Numeric regex from solve text
        fallback = extract_answer_value(solution_fallback)
        if fallback:
            return fallback

        # 5) "Final answer:" line from solve
        m = re.search(r"\*{0,2}Final answer:\*{0,2}\s*(.+)", solution_fallback, re.IGNORECASE)
        if m:
            candidate = m.group(1).strip().rstrip(".,;")
            if candidate:
                return candidate

        # 6) Last resort: return entire solve response
        return solution_fallback.strip()
