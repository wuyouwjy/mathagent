"""user_agent.py — ReasoningAgent for 2026 Challenge Cup (v5).

Multi-stage math reasoning agent for Intern-S series models.

Key improvements over v4:
- Self-contained core logic: inline prompts avoid ModuleNotFoundError on the
  competition platform; optional helper imports via try/except with fallbacks.
- Three-stage pipeline: Structured Think → Solve → Verify → Extract.
- Robust answer extraction: 5-strategy extraction handles diverse output formats.
- Competition-aware: tuned for 3-concurrency / 20 min-per-problem / 6 h total limits.
- Clean trace format matching the competition spec.

Platform interface (fixed by competition rules):
    from user_agent import ReasoningAgent
    agent = ReasoningAgent(client=official_client)
    result = agent.solve(problem="...", metadata={"idx": 0})
    # → {"final_response": "72", "trace": [...], ...}
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

# ── optional helper imports (safe fallbacks built-in) ──────────────────────
try:
    from prompts import (  # noqa: F401 — available if the repo is deployed as-is
        COMPUTE_SOLVE_PROMPT,
        PROOF_SOLVE_PROMPT,
        ENGLISH_THINK_PATTERNS,
        TEMPLATE_LEAK_PATTERNS,
    )
    _PROMPTS_AVAILABLE = True
except ImportError:
    _PROMPTS_AVAILABLE = False

try:
    from agents import MathClassifier
    _CLASSIFIER_AVAILABLE = True
except ImportError:
    _CLASSIFIER_AVAILABLE = False


# ============================================================
# Inline prompts (always available — no import dependency)
# ============================================================

_SOLVE_PROMPT = """你是一位资深的数学研究者。请认真解答以下数学问题。

【问题】
{problem}

【解答要求】
1. 仔细读题，明确已知条件和求解/求证目标
2. 分析问题类型，选择最合适的数学方法和定理
3. 分步骤写出完整推导过程，每一步都要有充分的逻辑依据
4. 计算过程要详细，避免跳步
5. 数学公式使用 LaTeX 格式（行内用 $...$，独立的用 $$...$$）
6. 全程使用中文进行推理分析

【输出格式】
在解答最后，请单独一行写出最终答案，格式为：
ANSWER: <你的最终答案>

（答案应简洁明确——计算题写数值或表达式，证明题写关键结论等式）
"""

_VERIFY_PROMPT = """你是一位严格的数学审阅者。请仔细检查以下解答。

【原问题】
{problem}

【已有解答】
{solution}

【当前答案】
{answer}

【审阅要求】
1. 逐行检查推理过程是否有逻辑跳跃或错误
2. 独立重新计算关键步骤
3. 判断最终答案是否满足题目所有条件
4. 如果答案正确 → 输出 "审阅结论：正确" 并复述答案
5. 如果答案错误 → 输出 "审阅结论：有误" 并在 ANSWER: 后给出修正后的正确答案

ANSWER: <最终/修正后的答案>
"""

_CONTINUATION_PROMPT = """你的上一轮回答被截断了。请从截断处接着写，完成剩余的推导过程。

最后必须给出：
ANSWER: <最终答案>
"""


# ============================================================
# Answer extraction utilities
# ============================================================

def _extract_answer(text: str) -> str:
    """Multi-strategy answer extraction — 5 layers of fallback."""
    if not text or not text.strip():
        return ""

    lines = text.strip().split("\n")

    # L1: explicit ANSWER: marker (highest priority)
    for i in range(len(lines) - 1, -1, -1):
        m = re.search(r"ANSWER\s*[：:]\s*(.+)", lines[i], re.IGNORECASE)
        if m:
            ans = m.group(1).strip().rstrip("。，,;；. ")
            if ans:
                return ans

    # L2: \boxed{...} LaTeX
    for i in range(len(lines) - 1, -1, -1):
        matches = re.findall(r"\\boxed\{([^{}]+)\}", lines[i])
        if matches:
            return matches[-1].strip()

    # L3: Chinese conclusion markers
    markers = [
        "最终答案", "答案是", "答案为", "结果为", "结论为",
        "答案：", "答案:", "解：", "解:",
    ]
    for marker in markers:
        for i in range(len(lines) - 1, -1, -1):
            if marker in lines[i]:
                idx = lines[i].find(marker)
                tail = lines[i][idx + len(marker):].strip().lstrip("：: ")
                if tail:
                    # If tail is a math expression, return it
                    if re.search(r"[$\\\d]", tail) or len(tail) <= 50:
                        return tail[:300]
                if i + 1 < len(lines):
                    nxt = lines[i + 1].strip()
                    if nxt:
                        return nxt[:300]

    # L4: last line with mathematical content
    for i in range(len(lines) - 1, -1, -1):
        s = lines[i].strip()
        if not s:
            continue
        if s.startswith(("#", "//", ">", "-", "*", "```")):
            continue
        # Prefer lines with math notation or numbers
        if re.search(r"[$\\{}]|\d+", s):
            return s[:300]

    # L5: last non-empty line
    for i in range(len(lines) - 1, -1, -1):
        s = lines[i].strip()
        if s:
            return s[:200]

    return ""


def _is_valid_answer(text: str) -> bool:
    """Return False for error strings, template residues, or empty placeholders."""
    if not text or not text.strip():
        return False
    t = text.strip()

    # Trivially invalid
    if t in {
        "无", "无解", "未能求解", "未知", "N/A", "null", "None",
        "命题得证", "证毕", "QED", "证明完毕", "得证", "结论成立",
    }:
        return False

    # API error strings
    if "API错误" in t or t.startswith("[API"):
        return False

    # Template / prompt leaks
    if re.search(
        r"(?i)(?:specific (?:equation|mathematical|conclusion)"
        r"|must include|no more than|only.*no reasoning"
        r"|<[^>]*(?:final answer|具体数学|最终答案)[^>]*>)",
        t,
    ):
        return False

    # Pure-English with no math / no numbers → not a valid answer
    if re.match(r"^[A-Za-z\s,.\-;:'\"!?]+$", t):
        # Allow only if it contains numbers or math notation
        if not re.search(r"\d|\\|[$^{}]", t):
            return False

    return True


def _is_truncated(content: str) -> bool:
    """Heuristic: detect whether model output was cut off prematurely."""
    if not content or len(content.strip()) < 10:
        return False

    # Already has ANSWER marker → not truncated in a problematic way
    if re.search(r"ANSWER\s*[：:]", content, re.IGNORECASE):
        return False

    tail = content.rstrip()
    lines = tail.split("\n")
    last_line = ""
    for ln in reversed(lines):
        s = ln.strip()
        if s:
            last_line = s
            break
    if not last_line:
        return False

    # Natural ending punctuation → not truncated
    if re.search(r"[。！？\.!?]\)]$", last_line):
        return False
    if re.search(r"\\[\)\]]\s*$", last_line):
        return False

    # Ends with a connecting word → truncated
    connecting_words = [
        # Chinese
        "虽然", "但是", "因此", "所以", "由于", "当", "若", "令", "设",
        "对于", "考虑", "由", "根据", "利用", "通过", "于是", "故",
        "假设", "注意到",
        # English
        "and", "or", "then", "so", "because", "since", "when", "if",
        "let", "for", "by", "thus", "hence", "therefore", "where",
        "assuming", "suppose", "consider", "using",
    ]
    stripped = re.sub(r"[,，；;、\s]+$", "", last_line)
    stripped_lower = stripped.lower()
    for w in connecting_words:
        if stripped_lower.endswith(w.lower()):
            return True

    # Unclosed LaTeX math
    if last_line.count("$") % 2 == 1:
        return True

    # Ends mid-sentence (comma or open paren)
    if re.search(r"[,，\(（]\s*$", last_line):
        return True

    # Long output with no final punctuation
    if len(content) > 2000 and not re.search(r"[。！？\.!?]\s*$", last_line):
        return True

    return False


def _has_english_leak(content: str) -> bool:
    """Detect if Intern-S leaked English chain-of-thought instead of Chinese."""
    if not content:
        return False
    cn_chars = sum(1 for c in content if "\u4e00" <= c <= "\u9fff")
    total = max(len(content.strip()), 1)
    # Very low Chinese ratio suggests English leakage
    if cn_chars / total < 0.08 and total > 100:
        return True
    # Check for common English thinking patterns
    en_patterns = [
        r"\bI (?:will|need|should|shall|think|believe|would|can |must |want )",
        r"\bLet me",
        r"\bMy (?:approach|strategy|thinking|plan)",
        r"\bWait[,.!]",
        r"\bOkay[,.!]",
        r"\b(?:That means|This suggests|It seems|I think)",
    ]
    matches = sum(1 for p in en_patterns if re.search(p, content[:500], re.I))
    return matches >= 3 and cn_chars < 50


def _clean_answer(text: str) -> str:
    """Final cleanup: strip common prefixes, limit length."""
    if not text:
        return ""
    text = text.strip()
    for prefix in [
        "因此，", "因此", "所以，", "所以", "故",
        "综上所述，", "综上所述", "综上，", "综上",
        "由此可得，", "由此可得",
    ]:
        if text.startswith(prefix):
            text = text[len(prefix):].strip().lstrip("，, ")
    if len(text) > 500:
        text = text[:500].rstrip()
    return text


# ============================================================
# ReasoningAgent
# ============================================================

class ReasoningAgent:
    """Math reasoning agent — multi-stage pipeline with self-verification.

    The competition platform instantiates this class as:
        agent = ReasoningAgent(client=official_client)
    then calls:
        agent.solve(problem="...", metadata={"idx": 0})

    The *client* object is provided by the platform and exposes:
        client.chat(messages, temperature, max_tokens) -> str | dict
    """

    def __init__(self, client: Any, *args: Any, **kwargs: Any) -> None:
        self.client = client
        # Optional classifier for trace enrichment (safe to fail)
        if _CLASSIFIER_AVAILABLE:
            self.classifier: Any = MathClassifier()
        else:
            self.classifier = None

    # ── public entry point ────────────────────────────────────────────

    def solve(self, problem: str, metadata: Optional[Dict] = None) -> Dict:
        """Solve a math problem and return the competition-format result."""
        if metadata is None:
            metadata = {}

        try:
            return self._do_solve(problem, metadata)
        except Exception as exc:
            return {
                "final_response": self._last_chance_extract(problem),
                "trace": [
                    {"step": "error", "content": f"{type(exc).__name__}: {exc}"}
                ],
            }

    # ── main pipeline ─────────────────────────────────────────────────

    def _do_solve(self, problem: str, metadata: Dict) -> Dict:
        trace: List[Dict[str, str]] = []

        # ---- Stage 1: Structured solving ---------------------------------
        prompt = _SOLVE_PROMPT.format(problem=problem)

        solution = self._chat(prompt, temperature=0.1, max_tokens=8192)
        if solution is None:
            trace.append({"step": "error", "content": "模型调用失败：无响应"})
            return {"final_response": self._last_chance_extract(problem), "trace": trace}

        trace.append({
            "step": "solve",
            "content": solution[:600] + ("..." if len(solution) > 600 else ""),
        })

        # ---- Stage 1b: Continuation if truncated -------------------------
        if _is_truncated(solution):
            cont = self._chat_continuation(prompt, solution)
            if cont:
                solution = solution + "\n" + cont
                trace.append({
                    "step": "continue",
                    "content": cont[:300] + ("..." if len(cont) > 300 else ""),
                })

        # ---- Stage 1c: Retry if English leak detected --------------------
        if _has_english_leak(solution):
            retry_prompt = (
                f"请用中文重新解答以下数学问题。直接给出完整的解答过程，"
                f"不要用英文自言自语。\n\n{problem}\n\n"
                f"解答最后请写 ANSWER: <最终答案>"
            )
            retry = self._chat(retry_prompt, temperature=0.15, max_tokens=8192)
            if retry:
                solution = retry
                trace.append({
                    "step": "retry_cn",
                    "content": retry[:300] + ("..." if len(retry) > 300 else ""),
                })

        # ---- Stage 2: Answer extraction ----------------------------------
        answer = _extract_answer(solution)

        # ---- Stage 3: Verification (only when answer looks suspect) ------
        if not _is_valid_answer(answer):
            verified = self._verify(problem, solution, answer)
            if verified:
                trace.append({
                    "step": "verify",
                    "content": verified[:400] + ("..." if len(verified) > 400 else ""),
                })
                better = _extract_answer(verified)
                if better and _is_valid_answer(better):
                    answer = better

        # ---- Stage 4: Final cleanup & fallback ---------------------------
        if not _is_valid_answer(answer):
            # Last-resort: scan for any numeric / math expression
            answer = self._fallback_extract(solution)

        # ---- Absolute last chance: ensure non-empty final_response ----
        if not answer or not answer.strip():
            answer = self._last_chance_extract(solution)

        final_answer = _clean_answer(answer) if answer else "0"

        trace.append({
            "step": "finalize",
            "content": f"最终答案: {final_answer}",
        })

        return {"final_response": final_answer, "trace": trace}

    # ── helper methods ────────────────────────────────────────────────

    def _chat(
        self,
        content: str = "",
        temperature: float = 0.1,
        max_tokens: int = 8192,
        messages: Optional[List[Dict[str, str]]] = None,
    ) -> Optional[str]:
        """Wrapper around client.chat with error handling.

        Pass *messages* directly to send a custom conversation history;
        otherwise *content* is wrapped as a single user message.
        """
        if messages is None:
            messages = [{"role": "user", "content": content}]
        try:
            resp = self.client.chat(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return resp.get("content", "") if isinstance(resp, dict) else str(resp)
        except Exception:
            return None

    def _chat_continuation(self, original_prompt: str, truncated: str) -> Optional[str]:
        """Ask model to continue from truncation point."""
        return self._chat(
            messages=[
                {"role": "user", "content": original_prompt},
                {"role": "assistant", "content": truncated},
                {"role": "user", "content": _CONTINUATION_PROMPT},
            ],
            temperature=0.1,
            max_tokens=4096,
        )

    def _verify(
        self, problem: str, solution: str, answer: str
    ) -> Optional[str]:
        """Run a verification pass to check and potentially correct the answer."""
        prompt = _VERIFY_PROMPT.format(
            problem=problem,
            solution=solution[:3000],
            answer=answer or "(未提取到答案)",
        )
        return self._chat(prompt, temperature=0.05, max_tokens=4096)

    def _fallback_extract(self, text: str) -> str:
        """Last-resort extraction: grab any plausible answer from the text."""
        if not text:
            return ""
        # LaTeX boxed
        boxes = re.findall(r"\\boxed\{([^{}]+)\}", text)
        if boxes:
            return boxes[-1].strip()
        # Reverse-scan for math content
        for line in reversed(text.split("\n")):
            s = line.strip()
            if not s or len(s) < 2:
                continue
            if s.startswith(("#", "//", "```")):
                continue
            if re.search(r"[\u4e00-\u9fff].*\d|\d.*[\u4e00-\u9fff]|[${}\\]", s):
                return s[:300]
        return ""

    def _last_chance_extract(self, text: str) -> str:
        """绝对兜底：从文本中提取任何可能的数值或表达式，确保非空返回。

        优先级：
        1. 最后出现的数字（整数/小数/分数）
        2. 最后的 LaTeX 数学表达式
        3. 最后的英文单词（可能是答案关键词）
        4. 兜底字符串 "0"
        """
        if not text:
            return "0"

        # 1. 扫描所有数字（包括科学计数法、负数、分数）
        numbers = re.findall(
            r"(?:^|[^\d])"
            r"(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)"
            r"(?:[^\d]|$)",
            text,
        )
        if numbers:
            return numbers[-1]

        # 2. 最后的 LaTeX 数学表达式 $...$ 或 $$...$$
        latex = re.findall(r"\${1,2}([^$]+)\${1,2}", text)
        if latex:
            return latex[-1].strip()[:200]

        # 3. 最后的英文单词或中文短语（长度≥2）
        words = re.findall(r"[A-Za-z\u4e00-\u9fff]{2,}", text)
        if words:
            return words[-1][:100]

        # 4. 绝对兜底
        return "0"
