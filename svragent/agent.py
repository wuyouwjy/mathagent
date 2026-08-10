# -*- coding: utf-8 -*-
"""Platform-compatible math reasoning agent with multi-route solving.

Adapted from the InternS-main competition-winning architecture.
"""

from __future__ import annotations

import re
import time
from typing import Any, Dict, List, Optional

from .client_wrap import LLMCaller
from .config import SVRConfig
from .parser import AnswerNormalizer, OutputParser, answers_equal
from .session import SVRSession
from .wide import WidePipeline, production_config_hash, production_profile_manifest


# Leak markers — final output must not contain internal item indices or eval traces
_LEAK_MARKERS = re.compile(
    r"sample[_-]?data|eval[_-]?outputs|regression[_-]?98|answer[_-]?accuracy"
    r"|题号\s*[:：]\s*\d+|idx\s*[:：]\s*\d+", re.IGNORECASE)

_NONEMPTY_FALLBACK = (
    "未能在执行窗口内获得可独立判分的完整解答。\n"
    "FINAL: Insufficient completed evidence."
)

# Response type detection
_PROOF_VERB_RE = re.compile(
    r"证明|求证|试证|请证|证\s*[:：]|论证|严格推导|推导并说明|解释为什么|"
    r"prove\b|show\s+that|justify\b|derive\b|explain\s+why",
    re.IGNORECASE,
)
_JUDGE_RE = re.compile(r"判断|determine\s+whether|decide\s+whether", re.IGNORECASE)
_REASON_RE = re.compile(
    r"说明理由|说明原因|give\s+(a\s+)?(reason|proof)|论证|证明", re.IGNORECASE)
_RESPONSE_META_KEYS = (
    "response_kind", "question_type", "task_type", "answer_type", "kind", "type",
)
_META_PROOF_RE = re.compile(
    r"proof|prove|derivation|explanation|open[-_\s]?ended|证明|论证|推导|解析",
    re.IGNORECASE,
)
_META_ANSWER_RE = re.compile(
    r"choice|multiple[-_\s]?choice|fill|blank|short[-_\s]?answer|numeric|"
    r"选择|填空|短答|数值",
    re.IGNORECASE,
)


# =============================================================================
# Helpers
# =============================================================================
def _normalize_problem_text(text: str) -> str:
    """Normalize problem text: full-width → half-width, unify whitespace."""
    body = str(text or "")
    converted = []
    for ch in body:
        code = ord(ch)
        if 0xFF01 <= code <= 0xFF5E:
            converted.append(chr(code - 0xFEE0))
        elif ch == "　":
            converted.append(" ")
        else:
            converted.append(ch)
    body = "".join(converted)
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in body.split("\n")]
    out = []
    blank_run = 0
    for line in lines:
        if not line:
            blank_run += 1
            if blank_run > 1:
                continue
        else:
            blank_run = 0
        out.append(line)
    return "\n".join(out).strip()


def _format_fingerprint(short: str) -> str:
    """Answer format fingerprint: int/frac/decimal/percent/set/interval/expression/other."""
    text = str(short or "").strip()
    if not text:
        return "empty"
    if re.fullmatch(r"[+-]?\d+", text):
        return "int"
    if re.fullmatch(r"[+-]?\d+/\d+", text):
        return "frac"
    if re.fullmatch(r"[+-]?\d+\.\d+", text):
        return "decimal"
    if re.fullmatch(r"[+-]?\d+%", text):
        return "percent"
    if text.startswith("{") and text.endswith("}"):
        return "set"
    if re.fullmatch(r"[\[(]-?\d+\.?\d*,-?\d+\.?\d*[\])]", text):
        return "interval"
    if any(ch in text for ch in "=√π≤≥"):
        return "expression"
    if re.search(r"[a-z]+\s*\(", text, re.IGNORECASE):
        return "expression"
    return "other"


def detect_response_kind(problem: str, metadata: Optional[Dict] = None) -> str:
    """Detect proof vs answer from metadata and problem text."""
    try:
        meta = dict(metadata or {})
        for key in _RESPONSE_META_KEYS:
            value = str(meta.get(key, "") or "").strip()
            if not value:
                continue
            if _META_PROOF_RE.search(value):
                return "proof"
            if _META_ANSWER_RE.search(value):
                return "answer"
        text = str(problem or "")
        if _PROOF_VERB_RE.search(text):
            return "proof"
        if _JUDGE_RE.search(text) and _REASON_RE.search(text):
            return "proof"
        return "answer"
    except Exception:
        return "answer"


# =============================================================================
# BudgetManager (simplified, built-in)
# =============================================================================
class BudgetManager:
    """Tracks wall-clock budget for the per-problem solve window."""

    def __init__(self, config: SVRConfig) -> None:
        self._wall = float(getattr(config, "wall_clock_s", 1140.0))

    def elapsed_s(self, session: SVRSession) -> float:
        start = float(getattr(session, "start_ts", 0.0) or 0.0)
        if start <= 0.0:
            return 0.0
        return time.time() - start

    def remaining_s(self, session: SVRSession) -> float:
        return max(0.0, self._wall - self.elapsed_s(session))


# =============================================================================
# TraceRecorder (simplified, built-in)
# =============================================================================
class TraceRecorder:
    """Appends structured trace entries to the session."""

    def __init__(self, config: SVRConfig) -> None:
        self._max_items = int(getattr(config, "max_trace_items", 80))
        self._max_chars = int(getattr(config, "max_trace_content_chars", 1500))

    def add(self, session: SVRSession, step: str, data: Dict[str, Any]) -> None:
        try:
            content = self._clip(data)
            entry = {
                "step": step,
                "elapsed_s": round(time.time() - float(
                    getattr(session, "start_ts", time.time()) or time.time()), 2),
                "content": content,
            }
            with session.lock:
                session.trace.append(entry)
                while len(session.trace) > self._max_items:
                    session.trace.pop(0)
        except Exception:
            pass

    def _clip(self, data: Dict[str, Any]) -> Dict[str, Any]:
        s = str(data)
        if len(s) <= self._max_chars:
            return data
        result = dict(data)
        for key, value in result.items():
            if isinstance(value, str) and len(value) > self._max_chars // 4:
                result[key] = value[:self._max_chars // 4] + "...[clipped]"
        return result


# =============================================================================
# Finalizer
# =============================================================================
class Finalizer:
    """Guaranteed non-empty, clean, JSON-serializable final output."""

    def __init__(self, agent: "ReasoningAgent") -> None:
        self.agent = agent

    def finalize(self, session: SVRSession) -> Dict[str, Any]:
        try:
            final = str(session.final_answer or "").strip()
            if not final:
                final = self._rescue_raw(session)
            if not final:
                final = _NONEMPTY_FALLBACK
                session.forced_submit = True
                if session.final_source == "unknown":
                    session.final_source = "undetermined"
                session.verification_status = session.verification_status or "unverified"

            # Leak audit
            if _LEAK_MARKERS.search(str(final or "")):
                final = _NONEMPTY_FALLBACK
                session.forced_submit = True

            # Language consistency check
            if getattr(session, "problem", "") and any(
                    "一" <= ch <= "鿿" for ch in str(session.problem or "")):
                if final and not any(
                        "一" <= ch <= "鿿" for ch in final[:400]):
                    final = _NONEMPTY_FALLBACK
                    session.forced_submit = True

            final = self._normalize_final_line(final)

            # Length budget protection
            if len(final) > 30_000:
                head, tail = final[:20_000], final[-8_000:]
                final = head + "\n...[输出超长截断]...\n" + tail
                session.forced_submit = True

            # Compute answer format fingerprint
            short = str(getattr(session, "final_short", "") or "")

            stats = {
                "llm_calls": int(session.llm_calls or 0),
                "tool_calls": int(session.tool_calls or 0),
                "elapsed_s": round(self.agent.budget.elapsed_s(session), 1),
                "stage": str(session.stage or ""),
                "response_kind": str(session.response_kind or "answer"),
                "final_answer_short": short,
                "answer_format": _format_fingerprint(short),
                "final_source": str(session.final_source or "unknown"),
                "confidence": float(getattr(session, "final_confidence", 0.5) or 0.5),
                "verification_status": str(session.verification_status or "unverified"),
                "forced_submit": bool(session.forced_submit),
                "profile": str(getattr(self.agent, "profile", "wide")),
                "config_hash": str(getattr(self.agent, "config_hash", "")),
            }

            self.agent.trace.add(session, "finalize", {
                "final_chars": len(final),
                "final_source": stats["final_source"],
                "verification_status": stats["verification_status"],
                "forced_submit": stats["forced_submit"],
                "llm_calls": stats["llm_calls"],
            })

            return {
                "final_response": str(final),
                "trace": list(session.trace),
                "stats": stats,
            }
        except Exception:
            return {
                "final_response": _NONEMPTY_FALLBACK,
                "trace": [],
                "stats": {
                    "forced_submit": True,
                    "final_source": "finalizer_error",
                    "profile": str(getattr(self.agent, "profile", "wide")),
                    "config_hash": str(getattr(self.agent, "config_hash", "")),
                },
            }

    @staticmethod
    def _normalize_final_line(final: str) -> str:
        body = str(final or "")
        pattern = re.compile(r"(?m)^[ \t]*FINAL[ \t]*[:：][ \t]*(.+?)[ \t]*$")

        def _format_value(value: str) -> str:
            value = re.sub(r"[ \t]+", " ", value.strip())
            if re.fullmatch(r"[+-]?\d[\d,]*", value):
                value = value.replace(",", "")
            elif re.fullmatch(r"[+-]?\d+\.\d+", value):
                value = re.sub(r"(\.\d*?)0+$", r"\1", value)
                if value.endswith("."):
                    value = value[:-1]
            return value

        return pattern.sub(lambda m: "FINAL: %s" % _format_value(m.group(1)), body)

    def _rescue_raw(self, session: SVRSession) -> str:
        drafts = [str(raw or "").strip() for raw in session.accumulated_raw]
        drafts = [d for d in drafts if d]
        if not drafts:
            return ""
        session.final_source = "wide_raw_rescue"
        session.verification_status = "unverified"
        session.forced_submit = True
        return max(drafts, key=len)


# =============================================================================
# ReasoningAgent
# =============================================================================
class ReasoningAgent:
    """Platform-compatible math reasoning agent.

    Uses the WidePipeline: 4 parallel blind routes → consensus voting → review.
    Compatible with the competition platform's ``client.chat()`` interface.
    """

    def __init__(self, client: Any = None, config: Optional[Any] = None) -> None:
        self.client = client
        self.config = self._coerce_config(config)
        self.trace = TraceRecorder(self.config)
        self.budget = BudgetManager(self.config)
        self.parser = OutputParser()
        self.normalizer = AnswerNormalizer()
        self.llm_call = LLMCaller(client)
        self.wide = WidePipeline(self)
        self.profile_manifest = production_profile_manifest(self.config)
        self.config_hash = production_config_hash(self.config)
        self.profile = self.profile_manifest.get("profile", "wide")
        self.finalizer = Finalizer(self)

    @staticmethod
    def _coerce_config(config: Any) -> SVRConfig:
        if config is None:
            return SVRConfig()
        if isinstance(config, SVRConfig):
            config.validate()
            return config
        base = SVRConfig()
        known = set(base.__dataclass_fields__)
        for key in known:
            if hasattr(config, key):
                setattr(base, key, getattr(config, key))
        base.validate()
        return base

    @staticmethod
    def answers_equal_static(a: str, b: str) -> bool:
        return answers_equal(a, b)

    def solve(self, problem: str, metadata: Optional[Dict] = None) -> Dict[str, Any]:
        session = SVRSession(
            problem=str(problem or ""), metadata=dict(metadata or {}))
        # Normalize problem text
        session.problem = _normalize_problem_text(session.problem)
        session.prompt_problem = session.problem
        session.mark_start()

        # Routing signals
        self.trace.add(session, "routing_signals", {
            "problem_chars": len(session.problem or ""),
            "has_latex": "\\" in (session.problem or ""),
            "has_chinese": any(
                "一" <= ch <= "鿿" for ch in (session.problem or "")),
        })

        # Config fingerprint
        self.trace.add(session, "config_fingerprint", {
            "config_hash": str(getattr(self, "config_hash", "")),
            "pipeline": "wide",
            "wall_clock_s": float(getattr(self.config, "wall_clock_s", 1140.0)),
        })

        try:
            session.response_kind = detect_response_kind(
                session.problem, session.metadata)
            self.trace.add(session, "start", {
                "idx": session.metadata.get("idx"),
                "response_kind": session.response_kind,
                "backend": "svragent",
                "profile": self.profile,
                "config_hash": self.config_hash,
            })
            self.trace.add(session, "submission_profile", self.profile_manifest)

            # Empty problem shortcut
            empty = self._empty_problem_shortcut(session)
            if empty:
                session.final_answer = empty
                session.final_source = "empty_problem"
                session.verification_status = "empty_problem"
                session.response_kind = "answer"
                return self.finalizer.finalize(session)

            # Run the wide pipeline
            self.wide.run(session)
            return self.finalizer.finalize(session)

        except Exception as exc:
            self.trace.add(session, "error", repr(exc))
            session.final_source = "error"
            session.forced_submit = True
            return self.finalizer.finalize(session)

    @staticmethod
    def _empty_problem_shortcut(session: SVRSession) -> Optional[str]:
        try:
            raw = str(session.problem or "")
            s = raw.strip()
            if not s:
                return "无法确定"
            stripped = re.sub(r"\$+|\\\(|\\\)|\\\[|\\\]|```|[*_`~]", " ", s)
            stripped = re.sub(
                r"[，。、；：;:,.!?！？\-\(\)\[\]\{\}\"']", " ", stripped)
            if not re.search(r"[A-Za-z0-9_一-鿿]", stripped.strip()):
                return "无法确定"
            return None
        except Exception:
            return None
