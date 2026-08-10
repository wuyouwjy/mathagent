# -*- coding: utf-8 -*-
"""Configuration for the math reasoning agent."""

from __future__ import annotations

from dataclasses import dataclass

# intern-s2-preview-397b shares max_tokens between reasoning and content.
# The hard-screen run naturally stopped at 4,250--55,072 completion tokens
# (p95 42,346); a 16k/32k ladder would truncate 76%/17% of complete solutions.
DEFAULT_REASONING_TOKEN_CEILING = 131_072
REVIEW_TOKEN_CEILING = 8192


@dataclass
class SVRConfig:
    """Pipeline configuration with sensible defaults.

    The official per-problem timeout is 1200s; reserve one minute to serialize.
    """

    wall_clock_s: float = 1140.0

    # Pipeline selection: "wide" = 4-route blind solving + conditional review
    pipeline: str = "wide"

    # Review phase (only when ANSWER has < 2-route consensus):
    enable_review: bool = True
    review_min_remaining_s: float = 360.0
    review_max_tokens: int = REVIEW_TOKEN_CEILING

    # Trace limits
    max_trace_items: int = 80
    max_trace_content_chars: int = 1500

    def validate(self) -> None:
        if self.pipeline not in {"wide"}:
            raise ValueError("unknown pipeline: %s" % (self.pipeline,))
        if self.enable_review and self.review_max_tokens < 8192:
            raise ValueError(
                "review_max_tokens must be >= 8192 for the 397b shared budget")

    def __post_init__(self) -> None:
        self.validate()
