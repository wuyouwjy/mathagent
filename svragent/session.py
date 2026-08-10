# -*- coding: utf-8 -*-
"""Per-problem session state."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List

LONGEST_RAW_MAX_CHARS = 60000


@dataclass
class SVRSession:
    """Mutable per-problem state, threaded where needed."""

    problem: str = ""
    prompt_problem: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    trace: List[Dict[str, Any]] = field(default_factory=list)
    llm_calls: int = 0
    tool_calls: int = 0
    start_ts: float = 0.0
    max_call_duration_s: float = 0.0
    response_kind: str = "answer"
    stage: str = "route"
    accumulated_raw: List[str] = field(default_factory=list)
    final_answer: str = ""
    final_short: str = ""
    proof_text: str = ""
    final_source: str = "unknown"
    final_confidence: float = 0.5
    verification_status: str = "unverified"
    forced_submit: bool = False
    answer_type: str = "unknown"
    lock: threading.Lock = field(
        default_factory=threading.Lock, repr=False, compare=False)

    def mark_start(self) -> None:
        self.start_ts = time.time()

    def remember_raw(self, raw: str) -> None:
        """Retain recent complete outputs under a fixed character bound."""
        text = str(raw or "")[-LONGEST_RAW_MAX_CHARS:]
        if not text:
            return
        with self.lock:
            self.accumulated_raw.append(text)
            while (
                len(self.accumulated_raw) > 1
                and sum(len(item) for item in self.accumulated_raw)
                > LONGEST_RAW_MAX_CHARS
            ):
                self.accumulated_raw.pop(0)
