"""Prompts for Intern-S系列模型 (v5).

Simplified prompt templates — more natural, less rigid than v4.
These are optional: user_agent.py has inline fallbacks for all core prompts.
"""

# ── Core solving prompt (used by agents/solver.py) ────────────────────

COMPUTE_SOLVE_PROMPT = """你是一位资深的数学研究者。请认真解答以下数学问题。

【题目领域】{domain}
【问题】
{problem}

【解答要求】
1. 仔细读题，明确已知条件和求解目标
2. 分析适用的数学方法和定理
3. 分步骤写出完整推导过程，避免跳步
4. 数学公式使用 LaTeX 格式
5. 全程使用中文推理

【输出格式】
在解答最后单独一行输出：
ANSWER: <最终答案>
"""

PROOF_SOLVE_PROMPT = """你是一位资深的数学研究者。请认真证明以下数学命题。

【题目领域】{domain}
【问题】
{problem}

【证明要求】
1. 明确要证明的结论
2. 选择合适的证明策略（直接证明、反证法、归纳法等）
3. 写出完整的逻辑推导链
4. 数学公式使用 LaTeX 格式
5. 全程使用中文推理

【输出格式】
在证明最后单独一行输出具体数学结论：
ANSWER: <关键等式或结论>
"""

# ── Detection patterns (kept for backward compatibility) ──────────────

ENGLISH_THINK_PATTERNS = [
    r"\bI (?:will|need|should|shall|think|believe|would|can |must |want )",
    r"\bLet me",
    r"\bMy (?:approach|strategy|thinking|plan)",
    r"\bWait[,.!]",
    r"\bOkay[,.!]",
    r"\bPerhaps",
    r"\bMaybe",
    r"\b(?:That means|This suggests|It seems|I think)",
    r"\bproblem statement is (?:mathematically )?(?:false|incorrect)",
]

TEMPLATE_LEAK_PATTERNS = [
    r"(?i)Strategy Planning\)?.*specific to this problem",
    r"(?i)Key Insight\)?.*specific to this problem",
    r"(?i)Heuristic Summary\)?.*specific to this problem",
    r"(?i)<Specific mathematical conclusion",
    r"(?i)<Final Answer only",
    r"(?i)1-2 sentences analyzing core",
    r"(?i)1 sentence highlighting the key",
    r"(?i)1-2 sentences explaining broader",
]

TRUNCATION_TAIL_PATTERNS = [
    r"虽然$", r"但是$", r"因此$", r"所以$", r"由于$",
    r"当$", r"若$", r"令$", r"设$", r"对于$",
    r"考虑$", r"由$", r"根据$", r"利用$", r"通过$",
    r"[,，]\s*$", r"[\(（]\s*$", r"\\\s*$", r"&\s*$",
    r"\$\s*$", r"[a-zA-Z]$",
]
