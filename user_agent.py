"""user_agent.py — ReasoningAgent for 2026 Challenge Cup (T2).

Multi-route math reasoning agent using the svragent package.
Adapted from the InternS-main competition-winning architecture.

Key improvements over v6:
- **Multi-route parallel solving**: 4 independent LLM routes (A/D/L/X stances)
  with different temperatures, solving simultaneously via ThreadPoolExecutor.
- **Consensus-based answer selection**: Answers clustered by symbolic equivalence;
  ≥2 routes agree → submit immediately; otherwise wall-gated review.
- **max_tokens=131072**: Eliminates the 85% truncation problem (was 8192 in v6).
- **FINAL: marker**: Structured output format for reliable answer extraction.
- **Answer normalization**: LaTeX canonicalization, fraction simplification,
  decimal normalization, set sorting, multipart handling.
- **Symbolic answer equivalence**: Fraction/decimal/percentage aliases,
  set unordered comparison, multipart field matching.
- **Review phase**: When routes disagree and wall clock permits, a review call
  independently checks candidate answers.
- **Proof mode**: 4 parallel proof routes (direct/contradiction/induction/extremal)
  with QED detection.

Architecture:
    solve(problem, metadata)
      ├── Problem text normalization (full-width → half-width)
      ├── Response kind detection (answer vs proof)
      ├── WidePipeline.run(session)
      │    ├── 4 routes parallel LLM calls
      │    ├── Answer extraction + clustering
      │    ├── Consensus ≥2 → submit best
      │    ├── No consensus + wall clock OK → review
      │    └── Fallback: preregistered order
      └── Finalizer.finalize(session)
           ├── Non-empty guarantee
           ├── Leak audit
           ├── Language consistency check
           ├── Length budget protection
           └── Return {"final_response": ..., "trace": [...], "stats": {...}}

Platform interface (fixed by competition rules):
    from user_agent import ReasoningAgent
    agent = ReasoningAgent(client=official_client)
    result = agent.solve(problem="...", metadata={"idx": 0})
    # → {"final_response": "解答全文...", "trace": [...], "stats": {...}}
"""

from __future__ import annotations

from typing import Any, Dict, Optional

# Try to use svragent; fall back to v6 single-prompt mode if unavailable.
try:
    from svragent.agent import ReasoningAgent as _SVRReasoningAgent
    from svragent.config import SVRConfig
    _HAS_SVRAGENT = True
except ImportError:
    _HAS_SVRAGENT = False


class ReasoningAgent:
    """Math reasoning agent — T2 multi-route pipeline.

    Uses the svragent WidePipeline: 4 parallel blind routes → consensus voting →
    conditional review → deterministic fallback.

    The competition platform instantiates this class as::

        agent = ReasoningAgent(client=official_client)

    then calls::

        agent.solve(problem="...", metadata={"idx": 0})

    The *client* object is provided by the platform and exposes::

        client.chat(messages, temperature, max_tokens) -> str | dict | object
    """

    def __init__(self, client: Any, *args: Any, **kwargs: Any) -> None:
        self.client = client

        if _HAS_SVRAGENT:
            config = SVRConfig()
            self._agent = _SVRReasoningAgent(client=client, config=config)
        else:
            self._agent = None

    def solve(self, problem: str, metadata: Optional[Dict] = None) -> Dict:
        """Solve a math problem and return the competition-format result.

        Returns a dict with keys:
            ``final_response`` — the full solution text for the Judger
            ``trace`` — list of trace entries for diagnostics
            ``stats`` — summary statistics (llm_calls, elapsed_s, etc.)
        """
        if metadata is None:
            metadata = {}

        if self._agent is not None:
            try:
                return self._agent.solve(problem, metadata)
            except Exception:
                pass

        # Fallback: single-prompt mode (same as v6, kept for compatibility)
        return self._fallback_solve(problem, metadata)

    # ---- fallback (when svragent is unavailable) ------------------------

    def _fallback_solve(self, problem: str, metadata: Dict) -> Dict:
        """Simple single-prompt fallback matching the v6 contract."""
        import re

        try:
            resp = self.client.chat(
                messages=[{
                    "role": "user",
                    "content": (
                        "你是数学研究者。请解答以下数学问题。\n"
                        "在解答最后一行以 ANSWER: <最终答案> 格式给出答案。\n\n"
                        + str(problem)
                    ),
                }],
                temperature=0.1,
                max_tokens=131072,
            )
        except Exception:
            return {"final_response": "0", "trace": [
                {"step": "error", "content": "模型调用失败"}]}

        # Extract content
        if isinstance(resp, str):
            text = resp
        elif isinstance(resp, dict):
            text = ""
            for key in ("content", "message", "text", "response", "output"):
                val = resp.get(key)
                if isinstance(val, str) and val.strip():
                    text = val
                    break
            if not text:
                choices = resp.get("choices", [])
                if choices:
                    msg = choices[0].get("message", {}) if isinstance(
                        choices[0], dict) else {}
                    text = msg.get("content", "")
            if not text:
                text = str(resp)
        else:
            # Object
            for attr in ("content", "message", "text"):
                try:
                    val = getattr(resp, attr, None)
                    if isinstance(val, str) and val.strip():
                        text = val
                        break
                except Exception:
                    pass
            else:
                try:
                    text = resp.choices[0].message.content
                except Exception:
                    text = str(resp)

        # Extract answer from text
        answer = "0"
        if text:
            for marker in ("ANSWER:", "ANSWER：", "FINAL:", "FINAL："):
                m = re.search(
                    marker + r"\s*(.+?)\s*$", text, re.MULTILINE | re.IGNORECASE)
                if m:
                    answer = m.group(1).strip().rstrip("。，,. ")
                    break
            else:
                boxes = re.findall(r"\\boxed\{([^{}]+)\}", text)
                if boxes:
                    answer = boxes[-1].strip()

        return {
            "final_response": text or answer,
            "trace": [
                {"step": "fallback_solve",
                 "content": f"答案: {answer}, 文本长度: {len(text or '')}"},
            ],
        }
