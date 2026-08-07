"""user_agent.py — ReasoningAgent for 2026 Challenge Cup (v6).

Multi-stage math reasoning agent for Intern-S series models.

Key improvements over v5:
- JSON-aware answer extraction: Intern-S models often output JSON;
  we now parse JSON and extract answer fields before falling back to
  text-pattern extraction.
- Robust client.chat() response handling: handles str, dict, and
  OpenAI-style SDK objects (any object with .content or .choices).
- Hardened prompt: explicitly prohibits JSON output and requires the
  "ANSWER:" format for reliable extraction.
- Cleaner answer stripping: removes JSON syntax fragments (quotes,
  brackets, braces) that would cause the Judger to mark the answer
  as "invalid".
- Better trace diagnostics: traces include extraction strategy info.

Platform interface (fixed by competition rules):
    from user_agent import ReasoningAgent
    agent = ReasoningAgent(client=official_client)
    result = agent.solve(problem="...", metadata={"idx": 0})
    # → {"final_response": "72", "trace": [...], ...}
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional


# ============================================================
# Inline prompts — always available
# ============================================================

_SOLVE_PROMPT = """你是一位数学研究者。请解答以下数学问题。

【问题】
{problem}

【重要规则 — 必须严格遵守】
1. 全程使用中文推理，分步骤写出完整推导过程
2. 数学公式使用 LaTeX 格式（行内 $...$，独立 $$...$$）
3. **禁止输出 JSON 格式的回复**，请用自然语言写解答
4. 在解答的最后一行，必须以如下格式单独写出最终答案：
   ANSWER: <最终答案>
   （答案应简洁明确——计算题写数值或表达式，证明题写关键结论等式）

请现在开始解答。"""

_REFINE_PROMPT = """你之前的解答可能没有正确提取最终答案。请重新审视以下问题，并给出最终答案。

【问题】
{problem}

【之前的解答摘要】
{solution_summary}

请严格按以下格式在最后一行输出：
ANSWER: <最终答案>

（只需给出最终答案的简洁形式——数值、表达式或关键结论等式）"""


# ============================================================
# JSON answer extraction
# ============================================================

def _try_extract_json_answer(text: str) -> Optional[str]:
    """Try to parse the entire text (or JSON blocks inside it) as JSON
    and extract an answer from known keys.

    Returns None if no JSON or no recognised answer key is found.
    """
    if not text or not text.strip():
        return None

    def _from_obj(obj: Any, _depth: int = 0) -> Optional[str]:
        """Recurse into nested JSON to find an answer value."""
        if _depth > 5:
            return None
        if isinstance(obj, dict):
            for key in ("answer", "final_answer", "result", "conclusion",
                        "final_response", "value", "output", "答案", "最终答案"):
                val = obj.get(key)
                if val is not None and not isinstance(val, (dict, list)):
                    s = str(val).strip()
                    if s and len(s) <= 500:
                        return s
            for v in obj.values():
                found = _from_obj(v, _depth + 1)
                if found:
                    return found
        elif isinstance(obj, list) and obj:
            for item in obj:
                found = _from_obj(item, _depth + 1)
                if found:
                    return found
        return None

    stripped = text.strip()

    # Strategy 1: whole text is JSON object/array
    if stripped.startswith("{") and stripped.endswith("}"):
        try:
            obj = json.loads(stripped)
            ans = _from_obj(obj)
            if ans:
                return ans
        except (json.JSONDecodeError, ValueError):
            pass

    if stripped.startswith("[") and stripped.endswith("]"):
        try:
            obj = json.loads(stripped)
            ans = _from_obj(obj)
            if ans:
                return ans
        except (json.JSONDecodeError, ValueError):
            pass

    # Strategy 2: fenced JSON blocks ```json ... ```
    for m in re.finditer(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL):
        try:
            obj = json.loads(m.group(1).strip())
            ans = _from_obj(obj)
            if ans:
                return ans
        except (json.JSONDecodeError, ValueError):
            pass

    # Strategy 3: inline JSON objects (greedy, longest first)
    for m in re.finditer(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", text):
        try:
            obj = json.loads(m.group())
            ans = _from_obj(obj)
            if ans:
                return ans
        except (json.JSONDecodeError, ValueError):
            pass

    return None


# ============================================================
# Answer extraction utilities
# ============================================================

def _is_plausible_answer(text: str) -> bool:
    """Quick check: does this look like it could be an answer?

    Rejects strings that are clearly NOT answers (pure JSON structure, etc.).
    """
    if not text or not text.strip():
        return False
    t = text.strip()

    if t in ("{", "}", "[", "]", "null", "None", "N/A", "无", "未能求解", "未知"):
        return False

    if re.match(r'^\s*"[^"]+"\s*:\s*[\[{"]', t):
        return False

    if len(t) < 2:
        return False

    return True


def _strip_json_artifacts(text: str) -> str:
    """Strip JSON syntax fragments from text that was inside a JSON value.

    Handles cases like:
      "answer": 72         → 72
      {"answer": "72"}     → 72
      72\n}                → 72
      "72"                 → 72
    """
    if not text:
        return ""
    t = text.strip()

    # Step 1: Strip leading JSON structural characters first
    # (so kv-pair detection works on {"key": val} after { is removed)
    for ch in ("{", "[", "}", "]"):
        while t.startswith(ch):
            t = t[1:].lstrip()

    # Step 2: If it looks like a JSON key-value pair, extract the value
    m = re.match(r'^"[^"]+"\s*:\s*(.+)$', t)
    if m:
        t = m.group(1).strip()

    # Step 3: Strip trailing JSON structural characters
    for ch in (",", "}", "]", "{"):
        while t.endswith(ch):
            t = t[:-1].rstrip()

    # Step 4: Strip leading JSON chars again (kv extraction may leave some)
    for ch in ("{", "[", "}", "]"):
        while t.startswith(ch):
            t = t[1:].lstrip()

    # Step 5: Strip surrounding quotes (only if no inner quotes)
    if len(t) >= 2 and t[0] == '"' and t[-1] == '"':
        inner = t[1:-1]
        if '"' not in inner:
            t = inner

    # Step 6: Strip single trailing quote
    if t.endswith('"') and t.count('"') == 1:
        t = t[:-1]

    return t.strip()


def _extract_answer(text: str) -> str:
    """Multi-strategy answer extraction.

    Priority:
    P0 – JSON parsing (handles Intern-S default structured output)
    L1 – Explicit ANSWER: marker
    L2 – \\boxed{...} LaTeX
    L3 – Chinese / English conclusion markers
    L4 – Last line with mathematical content
    L5 – Last non-empty line
    """
    if not text or not text.strip():
        return ""

    # ── P0: JSON parsing ────────────────────────────────────────
    json_ans = _try_extract_json_answer(text)
    if json_ans and _is_plausible_answer(json_ans):
        return json_ans

    lines = text.strip().split("\n")

    # ── L1: explicit ANSWER: marker ─────────────────────────────
    for i in range(len(lines) - 1, -1, -1):
        m = re.search(r"ANSWER\s*[：:]\s*(.+)", lines[i], re.IGNORECASE)
        if m:
            ans = m.group(1).strip().rstrip("。，,;；. ")
            if ans:
                return _strip_json_artifacts(ans)

    # ── L2: \\boxed{...} LaTeX ──────────────────────────────────
    for i in range(len(lines) - 1, -1, -1):
        matches = re.findall(r"\\boxed\{([^{}]+)\}", lines[i])
        if matches:
            return matches[-1].strip()

    # ── L3: Chinese / English conclusion markers ────────────────
    markers = [
        "最终答案", "答案是", "答案为", "结果为", "结论为",
        "答案：", "答案:", "解：", "解:",
        "Final answer:", "Final Answer:", "The answer is",
    ]
    for marker in markers:
        for i in range(len(lines) - 1, -1, -1):
            if marker in lines[i]:
                idx = lines[i].find(marker)
                tail = lines[i][idx + len(marker):].strip().lstrip("：: ")
                if tail and _is_plausible_answer(tail):
                    return _strip_json_artifacts(tail)[:300]
                if i + 1 < len(lines):
                    nxt = lines[i + 1].strip()
                    if nxt and _is_plausible_answer(nxt):
                        return _strip_json_artifacts(nxt)[:300]

    # ── L4: last line with mathematical content ─────────────────
    for i in range(len(lines) - 1, -1, -1):
        s = lines[i].strip()
        if not s:
            continue
        if s.startswith(("#", "//", ">", "-", "*", "```")):
            continue
        if re.match(r'^\s*"[^"]+"\s*:\s*', s):
            continue
        if s in ("{", "}", "[", "]", "},{", "},"):
            continue
        if re.search(r"[$\\{}]|\d+", s):
            return _strip_json_artifacts(s)[:300]

    # ── L5: last non-empty line ─────────────────────────────────
    for i in range(len(lines) - 1, -1, -1):
        s = lines[i].strip()
        if s and not s.startswith(("#", "//", "```")) and s not in ("{", "}", "[", "]"):
            return _strip_json_artifacts(s)[:200]

    return ""


def _is_valid_answer(text: str) -> bool:
    """Return False for error strings, template residues, or empty placeholders."""
    if not text or not text.strip():
        return False
    t = text.strip()

    if t in {
        "无", "无解", "未能求解", "未知", "N/A", "null", "None",
        "命题得证", "证毕", "QED", "证明完毕", "得证", "结论成立",
        "{", "}", "[", "]",
    }:
        return False

    if "API错误" in t or t.startswith("[API"):
        return False

    if re.search(
        r"(?i)(?:specific (?:equation|mathematical|conclusion)"
        r"|must include|no more than|only.*no reasoning"
        r"|<[^>]*(?:final answer|具体数学|最终答案)[^>]*>)",
        t,
    ):
        return False

    if re.match(r'^\s*[{}[\]],:\s"]+\s*$', t):
        return False

    return True


def _has_english_leak(content: str) -> bool:
    """Detect if Intern-S leaked English chain-of-thought instead of Chinese."""
    if not content:
        return False
    cn_chars = sum(1 for c in content if "\u4e00" <= c <= "\u9fff")
    total = max(len(content.strip()), 1)
    if cn_chars / total < 0.08 and total > 100:
        return True
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
    """Final cleanup: strip common prefixes, JSON artifacts, limit length."""
    if not text:
        return ""
    text = text.strip()

    for prefix in [
        "因此，", "因此", "所以，", "所以", "故",
        "综上所述，", "综上所述", "综上，", "综上",
        "由此可得，", "由此可得", "即", "即得",
    ]:
        if text.startswith(prefix):
            text = text[len(prefix):].strip().lstrip("，, ")

    text = _strip_json_artifacts(text)

    if len(text) > 500:
        text = text[:500].rstrip()

    return text


# ============================================================
# Client response extraction (handles opaque objects)
# ============================================================

def _extract_content_from_object(obj: Any) -> Optional[str]:
    """Best-effort extraction of text content from an opaque response object.

    Tries common attribute paths used by OpenAI-compatible SDKs before
    falling back to str(obj).
    """
    # Path 1: .content (simple object)
    try:
        val = obj.content
        if isinstance(val, str) and val.strip():
            return val
    except (AttributeError, TypeError):
        pass

    # Path 2: .message.content
    try:
        val = obj.message.content
        if isinstance(val, str) and val.strip():
            return val
    except (AttributeError, TypeError):
        pass

    # Path 3: .choices[0].message.content (OpenAI SDK)
    try:
        val = obj.choices[0].message.content
        if isinstance(val, str) and val.strip():
            return val
    except (AttributeError, IndexError, TypeError):
        pass

    # Path 4: .text
    try:
        val = obj.text
        if isinstance(val, str) and val.strip():
            return val
    except (AttributeError, TypeError):
        pass

    # Path 5: iterate choices
    try:
        for choice in obj.choices:
            try:
                val = choice.message.content
                if isinstance(val, str) and val.strip():
                    return val
            except (AttributeError, TypeError):
                pass
    except (AttributeError, TypeError):
        pass

    # Last resort: string representation
    s = str(obj)
    if s and s.strip() and not s.startswith("<"):
        return s
    return None


# ============================================================
# ReasoningAgent
# ============================================================

class ReasoningAgent:
    """Math reasoning agent — multi-stage pipeline.

    The competition platform instantiates this class as:
        agent = ReasoningAgent(client=official_client)
    then calls:
        agent.solve(problem="...", metadata={"idx": 0})

    The *client* object is provided by the platform and exposes:
        client.chat(messages, temperature, max_tokens) -> str | dict | object
    """

    def __init__(self, client: Any, *args: Any, **kwargs: Any) -> None:
        self.client = client

    # ── public entry point ────────────────────────────────────────────

    def solve(self, problem: str, metadata: Optional[Dict] = None) -> Dict:
        """Solve a math problem and return the competition-format result."""
        if metadata is None:
            metadata = {}

        try:
            return self._do_solve(problem, metadata)
        except Exception as exc:
            return {
                "final_response": "0",
                "trace": [
                    {"step": "error",
                     "content": f"{type(exc).__name__}: {exc}"}
                ],
            }

    # ── main pipeline ─────────────────────────────────────────────────

    def _do_solve(self, problem: str, metadata: Dict) -> Dict:
        trace: List[Dict[str, str]] = []

        # ---- Stage 1: Primary solve -----------------------------------
        prompt = _SOLVE_PROMPT.format(problem=problem)

        solution = self._chat(prompt, temperature=0.1, max_tokens=8192)
        if solution is None or not solution.strip():
            trace.append({"step": "error", "content": "模型调用失败：无响应"})
            return {"final_response": "0", "trace": trace}

        trace.append({
            "step": "solve",
            "content": solution[:500] + ("..." if len(solution) > 500 else ""),
        })

        # ---- Stage 1b: Handle English leak ----------------------------
        if _has_english_leak(solution):
            cn_prompt = (
                f"请用中文重新解答以下数学问题。直接写出完整推导和答案。"
                f"最后一行必须是 ANSWER: <最终答案>\n\n{problem}"
            )
            retry = self._chat(cn_prompt, temperature=0.15, max_tokens=8192)
            if retry and retry.strip():
                solution = retry
                trace.append({
                    "step": "retry_cn",
                    "content": retry[:300] + ("..." if len(retry) > 300 else ""),
                })

        # ---- Stage 2: Answer extraction --------------------------------
        answer = _extract_answer(solution)
        extraction_method = "primary"

        trace.append({
            "step": "extract",
            "content": f"策略: {extraction_method}, 候选: {answer[:200] if answer else '(空)'}",
        })

        # ---- Stage 2b: Refinement if answer empty/suspect --------------
        if not answer or not _is_valid_answer(answer):
            refine_prompt = _REFINE_PROMPT.format(
                problem=problem,
                solution_summary=solution[-1500:],
            )
            refined = self._chat(refine_prompt, temperature=0.05, max_tokens=2048)
            if refined and refined.strip():
                trace.append({
                    "step": "refine",
                    "content": refined[:400] + ("..." if len(refined) > 400 else ""),
                })
                better = _extract_answer(refined)
                if better and _is_valid_answer(better):
                    answer = better
                    extraction_method = "refined"

        # ---- Stage 2c: JSON-aware fallback -----------------------------
        if not answer or not _is_valid_answer(answer):
            json_ans = _try_extract_json_answer(solution)
            if json_ans and _is_valid_answer(json_ans):
                answer = json_ans
                extraction_method = "json"
                trace.append({
                    "step": "json_extract",
                    "content": f"JSON提取: {answer[:200]}",
                })

        # ---- Stage 3: Last-resort fallback -----------------------------
        if not answer or not _is_valid_answer(answer):
            answer = self._fallback_extract(solution)

        if not answer or not answer.strip():
            answer = "0"

        final_answer = _clean_answer(answer)
        if not final_answer or not final_answer.strip():
            final_answer = "0"

        trace.append({
            "step": "finalize",
            "content": f"最终答案: {final_answer} (策略: {extraction_method})",
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
        """Wrapper around client.chat with robust response handling.

        Handles return types:
          - str  → returned directly
          - dict → looks for "content", "message", "text", "response" keys
          - object → tries .content, .message.content, .choices[0].message.content
        """
        if messages is None:
            messages = [{"role": "user", "content": content}]
        try:
            resp = self.client.chat(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except Exception:
            return None

        # — str —
        if isinstance(resp, str):
            return resp

        # — dict —
        if isinstance(resp, dict):
            for key in ("content", "message", "text", "response", "output"):
                val = resp.get(key)
                if isinstance(val, str) and val.strip():
                    return val
            choices = resp.get("choices", [])
            if choices:
                msg = choices[0].get("message", {}) if isinstance(choices[0], dict) else {}
                val = msg.get("content", "")
                if isinstance(val, str) and val.strip():
                    return val
            return str(resp)

        # — object (e.g. OpenAI SDK ChatCompletion) —
        return _extract_content_from_object(resp)

    def _fallback_extract(self, text: str) -> str:
        """Last-resort extraction: grab any plausible answer from the text."""
        if not text:
            return ""
        json_ans = _try_extract_json_answer(text)
        if json_ans:
            return json_ans
        boxes = re.findall(r"\\boxed\{([^{}]+)\}", text)
        if boxes:
            return boxes[-1].strip()
        for line in reversed(text.split("\n")):
            s = line.strip()
            if not s or len(s) < 2:
                continue
            if s in ("{", "}", "[", "]", "null"):
                continue
            if s.startswith(("#", "//", "```")):
                continue
            if re.match(r'^\s*"[^"]+"\s*:', s):
                continue
            if re.search(r"[\u4e00-\u9fff].*\d|\d.*[\u4e00-\u9fff]|[${}\\]", s):
                return _strip_json_artifacts(s)[:300]
        return "0"
