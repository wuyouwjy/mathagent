"""Agents module (v5) — simplified exports.

Provides:
- MathClassifier: keyword-based domain classifier (optional)
- MathSolver: unified solver for all math problems
- ComputeSolver / ProofSolver: aliases for backward compatibility
"""

from .classifier import MathClassifier
from .solver import MathSolver

# Backward-compatible aliases
ComputeSolver = MathSolver
ProofSolver = MathSolver

__all__ = ["MathClassifier", "MathSolver", "ComputeSolver", "ProofSolver"]
