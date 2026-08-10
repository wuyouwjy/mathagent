# -*- coding: utf-8 -*-
"""svragent — Multi-route math reasoning agent for Intern-S series models.

Adapted from the InternS-main competition-winning architecture.
Provides:

- ``ReasoningAgent``: platform-compatible agent entry point
- ``WidePipeline``: 4-route parallel blind solving + consensus voting + review
- ``AnswerExtractor`` / ``AnswerNormalizer``: answer extraction & normalization
- ``answers_equal``: symbolic answer equivalence for candidate clustering
- ``SVRConfig``: pipeline configuration
"""

from __future__ import annotations

from .agent import ReasoningAgent
from .config import SVRConfig
from .parser import AnswerExtractor, AnswerNormalizer, answers_equal
from .wide import WidePipeline

__all__ = [
    "ReasoningAgent",
    "SVRConfig",
    "WidePipeline",
    "AnswerExtractor",
    "AnswerNormalizer",
    "answers_equal",
]
