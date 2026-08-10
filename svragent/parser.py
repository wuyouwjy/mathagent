# -*- coding: utf-8 -*-
"""Answer extraction, normalization, and equivalence for the math agent.

Core components adapted from the competition-winning architecture:
- ``AnswerExtractor``: multi-strategy answer extraction from model output
- ``AnswerNormalizer``: canonical answer form for reliable comparison
- ``answers_equal``: answer equivalence for candidate clustering
- ``OutputParser``: model output parser (code blocks + final answer)
"""

from __future__ import annotations

import json
import re
from decimal import Decimal, InvalidOperation
from fractions import Fraction
from typing import Any, Dict, List, Optional


# =============================================================================
# AnswerExtractor
# =============================================================================
class AnswerExtractor:
    """Extract the final answer from model output using multiple strategies."""

    MARKERS = [
        r"FINAL_ANSWER\s*[:：]",
        r"Final\s*Answer\s*[:：]",
        r"最终答案\s*[:：]",
        r"答案\s*[:：为是]",
        r"the\s*answer\s*is",
    ]

    _PLACEHOLDER_RE = re.compile(
        r"^(<[^>]*>|答案|最终答案|唯一答案|修正后的答案|corrected\s*answer|"
        r"short\s*reason|答案为|REPAIRED_ANSWER|REASON|VERDICT|"
        r"your\s*answer|the\s*answer|\*+|答案：|答案:|n/a|none|null|nil|tbd|todo)$",
        re.IGNORECASE,
    )
    _INSTRUCTION_RE = re.compile(
        r"FINAL_ANSWER|VERDICT|REPAIRED_ANSWER|followed\s+by|"
        r"紧(?:跟|接)|<[^>]*>|后面紧跟|唯一答案|short\s*reason",
        re.IGNORECASE,
    )
    _LEGAL_TEXT_ANSWERS = (
        "命题成立", "命题不成立", "成立", "不成立", "正确", "错误",
        "True", "False", "无解", "空集", "所有实数", "全体实数", "不存在",
    )
    _LEGAL_TEXT_RE = re.compile(
        r"^(?:no\s+solutions?|the\s+empty\s+set|empty\s+set|"
        r"all\s+(?:real|complex|rational|integer)\s+(?:numbers?|values?)|"
        r"infinitely\s+many(?:\s+solutions?)?|finitely\s+many(?:\s+solutions?)?|"
        r"does\s+not\s+exist|undefined|unbounded|"
        r"not\s+enough\s+information|insufficient\s+information|"
        r"cannot\s+be\s+determined|underdetermined|"
        r"无解|空集|所有实数|全体实数|所有复数|全体复数|"
        r"无穷多个(?:解)?|不存在|信息不足|条件不足|"
        r"∅|\\emptyset|\\varnothing)$",
        re.IGNORECASE,
    )
    _TOOL_PAYLOAD_RE = re.compile(
        r'"(?:op|expr|vars|where|objective|target)"\s*:', re.IGNORECASE)

    @classmethod
    def _is_placeholder(cls, s: str) -> bool:
        s = (s or "").strip().strip("`\"'").strip()
        if not s:
            return True
        if cls._TOOL_PAYLOAD_RE.search(s):
            return True
        if re.fullmatch(r"<[^>]*>", s):
            return True
        if cls._PLACEHOLDER_RE.match(s):
            return True
        if cls._INSTRUCTION_RE.search(s):
            return True
        if s in cls._LEGAL_TEXT_ANSWERS:
            return False
        if cls._LEGAL_TEXT_RE.fullmatch(s.strip(" .。")):
            return False
        # Vague words → model didn't compute a real answer
        if re.search(r"likely|maybe|probably|approx|大致|大概|可能|也许",
                     s, re.IGNORECASE):
            return True
        # Meta commentary detection
        meta_words = re.search(
            r"\b(said|explicitly|thinking|process|here'?s|let'?s|"
            r"note that|we need|step\s*\d|subst|substitut|simplif|"
            r"expand|derive|re-expand|re-expan|hence|therefore|thus|"
            r"since|because|equation|formula|solution|answer is|"
            r"we get|we have)\b",
            s, re.IGNORECASE)
        if meta_words:
            return True
        # Strip LaTeX commands before checking for English prose
        sentence_probe = re.sub(r"\\[A-Za-z]+\s*\{[^{}]*\}", " ", s)
        sentence_probe = re.sub(r"\\[A-Za-z]+", "", sentence_probe)
        if " " in sentence_probe and s not in cls._LEGAL_TEXT_ANSWERS:
            en_words = re.findall(r"[A-Za-z]{2,}", sentence_probe)
            if len(en_words) >= 2:
                return True
            if len(en_words) >= 1 and (
                len(sentence_probe) > 12
                or re.match(r"^[^0-9A-Za-z\\{]", sentence_probe)
            ):
                return True
        if not re.search(r"[A-Da-d]|\d|[/+\-^]|frac|\\|{|}", s):
            return True
        return False

    def extract(self, text: str) -> str:
        if not text:
            return ""
        text = str(text)
        candidates: List[str] = []

        # Choice letter: 选 A / 因此选 B
        m = re.search(r"(?:所以选|因此选|答案选|选)\s*([A-Da-d])[\.．、)\s\n。]?", text)
        if m:
            candidates.append(m.group(1).upper())

        for pattern in self.MARKERS:
            val = self._extract_after_marker(text, pattern)
            if val:
                candidates.append(val.strip())

        boxed = self._extract_last_boxed(text)
        if boxed:
            candidates.append(boxed.strip())

        tail = self._extract_from_tail(text)
        if tail:
            candidates.append(tail.strip())

        for cand in candidates:
            if cand and not self._is_placeholder(cand):
                return cand
        return candidates[0] if candidates else ""

    def _extract_after_marker(self, text: str, pattern: str) -> str:
        matches = list(re.finditer(pattern, text, flags=re.IGNORECASE))
        if not matches:
            return ""
        last = matches[-1]
        after = text[last.end():]
        line = re.split(r"[\n。]", after, maxsplit=1)[0]
        return line.strip(" :：。.，,")

    def _extract_last_boxed(self, text: str) -> str:
        idx = text.rfind(r"\boxed")
        while idx != -1:
            brace = text.find("{", idx)
            if brace == -1:
                break
            depth = 0
            for i in range(brace, len(text)):
                if text[i] == "{":
                    depth += 1
                elif text[i] == "}":
                    depth -= 1
                    if depth == 0:
                        return text[brace + 1:i]
            idx = text.rfind(r"\boxed", 0, idx)
        return ""

    def _extract_from_tail(self, text: str) -> str:
        lines = [ln.strip() for ln in text.strip().splitlines() if ln.strip()]
        if not lines:
            return ""
        for ln in reversed(lines[-6:]):
            m = re.fullmatch(r"([A-D])[\.．、)]?", ln)
            if m:
                return m.group(1)
            if re.fullmatch(r"-?\d+(?:\.\d+)?", ln):
                return ln
            if re.fullmatch(r"-?\d+/\d+", ln):
                return ln
            m = re.fullmatch(r"\\frac\{[^{}]+\}\{[^{}]+\}", ln)
            if m:
                return ln
            if re.fullmatch(r"\{.*\}", ln):
                return ln
        for ln in reversed(lines[-3:]):
            m = re.findall(r"-?\d+(?:\.\d+)?(?:/\d+)?", ln)
            if m:
                return m[-1]
        return ""


# =============================================================================
# AnswerNormalizer
# =============================================================================
class AnswerNormalizer:
    """Clean extracted answers into a short, clear, judgeable form."""

    PREFIX_WORDS = (
        "最终答案", "答案是", "答案为", "答案", "所以", "因此", "故",
        "为", "是", "Final Answer", "The answer is", "选",
    )

    def normalize(self, answer: str, profile: Optional[Dict] = None) -> str:
        if answer is None:
            return ""
        s = str(answer).strip()
        if not s:
            return ""
        original = s

        s = self._strip_unmatched_bold(s)

        # Unwrap \boxed{...}
        while True:
            m = re.fullmatch(r"\\boxed\{(.*)\}", s, flags=re.DOTALL)
            if not m:
                break
            s = m.group(1).strip()

        s = self._strip_unmatched_bold(s)
        s = self._strip_math_delimiters(s)
        s = re.sub(r"^\\\(|\\\)$", "", s).strip()
        s = re.sub(r"^\\\[|\\\]$", "", s).strip()

        # Unicode pi → LaTeX
        s = re.sub(r"π(?=[A-Za-z])", lambda _m: r"\pi ", s)
        s = s.replace("π", r"\pi")

        s = self._canonicalize_latex(s)
        s = self._strip_escaped_braces(s)
        s = s.strip()

        # Strip surrounding quotes
        while len(s) >= 2 and s[0] in "\"'`" and s[-1] == s[0]:
            s = s[1:-1].strip()

        # Strip prefix words
        changed = True
        while changed:
            changed = False
            for w in self.PREFIX_WORDS:
                if s.lower().startswith(w.lower()):
                    s = s[len(w):].lstrip(" :：。.，,、").strip()
                    changed = True

        # Handle multipart answers
        multipart = self._looks_like_multipart_answer(s)
        if multipart:
            s = self._normalize_multipart_layout(s)
        else:
            s = re.split(r"[。]|(?<!\\)[；;]", s)[0].strip()

        s = self._strip_explanatory_parentheses(s)
        s = self._frac_to_slash(s)

        # Choice letter normalization
        m = re.fullmatch(r"([A-Da-d])[\.\.、)]?", s)
        if m:
            return m.group(1).upper()

        s = self._strip_trailing_junk(s)
        if multipart:
            return s

        # Proof conclusion normalization
        concl = self._normalize_proof_conclusion(s)
        if concl:
            return concl

        # Undetermined normalization
        undet = self._normalize_undetermined(s)
        if undet:
            return undet

        if re.fullmatch(r"\{.*\}", s):
            return self._canonicalize_set(s)

        s = self._normalize_multi_answer(s)

        # Interval union normalization
        union = self._normalize_interval_union(s)
        if union:
            return union

        if self._is_interval_or_coord(s):
            s = re.sub(r"\s*,\s*", ",", s).strip()
            s = re.sub(r"\s+", " ", s).strip()
            return s.strip(" .。:：；;")

        s = self._normalize_number(s)
        s = re.sub(r"\s+", " ", s).strip(" .。,，:：；;")
        return s

    # ---- helper methods ----

    @staticmethod
    def _strip_unmatched_bold(text: str) -> str:
        s = str(text or "").strip()
        while (len(s) > 4 and s.startswith("**") and s.endswith("**")
               and "**" not in s[2:-2]):
            s = s[2:-2].strip()
            if not s:
                return str(text or "").strip()
        for _ in range(2):
            if s.startswith("**") and "**" not in s[2:]:
                s = s[2:].strip()
            elif s.endswith("**") and "**" not in s[:-2]:
                s = s[:-2].strip()
            else:
                break
            if not s:
                return str(text or "").strip()
        return s or str(text or "").strip()

    @staticmethod
    def _strip_math_delimiters(text: str) -> str:
        s = str(text or "")
        if "$" not in s:
            return s.strip()
        if s.count("$") % 2:
            return s.strip()
        return s.replace("$", "").strip()

    @staticmethod
    def _canonicalize_latex(s: str) -> str:
        try:
            text = re.sub(r"\\[dtc]frac(?![A-Za-z])", r"\\frac", str(s or ""))
            text = re.sub(
                r"\\frac\s*([A-Za-z0-9])\s*([A-Za-z0-9])(?![A-Za-z0-9])",
                r"\\frac{\1}{\2}", text)
            text = re.sub(r"\^\{([A-Za-z0-9])\}", r"^\1", text)
            text = re.sub(r"_\{([A-Za-z0-9])\}", r"_\1", text)
            text = re.sub(r"\\sqrt\s*([A-Za-z0-9])(?![A-Za-z0-9{])",
                         r"\\sqrt{\1}", text)
            text = re.sub(r"\\(?:text|textbf|textit)\{([^{}]*)\}", r"\1", text)
            return text
        except Exception:
            return s

    @staticmethod
    def _strip_escaped_braces(s: str) -> str:
        try:
            t = s.strip()
            if "\\{" not in t and "\\}" not in t:
                return s
            m = re.fullmatch(r"\\\{(.*)\\\}", t, flags=re.DOTALL)
            if m:
                return "{" + m.group(1) + "}"
            if re.search(r"\\\{", t) and re.search(r"\\\}", t):
                pair_count = min(t.count("\\{"), t.count("\\}"))
                if pair_count >= 1:
                    t2 = t
                    for _ in range(pair_count):
                        t2 = t2.replace("\\{", "{", 1).replace("\\}", "}", 1)
                    return t2
            return s
        except Exception:
            return s

    @staticmethod
    def _looks_like_multipart_answer(text: str) -> bool:
        try:
            pieces = [
                p.strip() for p in re.split(r"(?<!\\)[;；]|\n+", str(text or ""))
                if p.strip()
            ]
            if len(pieces) < 2:
                return False
            labelled = sum(
                bool(re.match(
                    r"^\s*(?:[\(（]\d+[\)）]|\d+[.)、:：]|[①-⑳]|"
                    r"[\(（][A-Za-z][\)）]|[A-Za-z][.)])\s*\S+", p))
                for p in pieces
            )
            return labelled == len(pieces) and labelled >= 2
        except Exception:
            return False

    @classmethod
    def _normalize_multipart_layout(cls, text: str) -> str:
        pieces = [
            p.strip() for p in re.split(r"(?<!\\)[;；]|\n+", str(text or ""))
            if p.strip()
        ]
        return "; ".join(re.sub(r"\s+", " ", p).strip(" 。.") for p in pieces)

    @staticmethod
    def _strip_explanatory_parentheses(s: str) -> str:
        if "(" not in s and "（" not in s:
            return s
        explanatory_inner = re.compile(
            r"^[即约大就也]|^也就是|^约等于|^answer|^i\.?e\.|"
            r"^e\.?g\.|^namely|^that is",
            re.IGNORECASE)
        result_chars: List[str] = []
        i, n = 0, len(s)
        while i < n:
            ch = s[i]
            if ch in "(（":
                close = ")" if ch == "(" else "）"
                depth, j = 1, i + 1
                start_inner = j
                while j < n and depth > 0:
                    if s[j] in "(（":
                        depth += 1
                    elif s[j] in ")）":
                        depth -= 1
                        if depth == 0:
                            break
                    j += 1
                if depth == 0:
                    inner = s[start_inner:j]
                    if explanatory_inner.match(inner.strip()):
                        i = j + 1
                        while result_chars and result_chars[-1] == " ":
                            result_chars.pop()
                        continue
                    else:
                        result_chars.append(s[i:j + 1])
                        i = j + 1
                        continue
                else:
                    result_chars.append(ch)
                    i += 1
                    continue
            else:
                result_chars.append(ch)
                i += 1
        return "".join(result_chars).strip()

    _ATOM_RE = re.compile(r"^[+-]?(?:\d+(?:\.\d+)?|[A-Za-z]|\\[A-Za-z]+)$")

    @classmethod
    def _is_atom(cls, text: str) -> bool:
        return bool(cls._ATOM_RE.fullmatch(str(text or "").strip()))

    @classmethod
    def _frac_to_slash(cls, s: str) -> str:
        try:
            pattern = re.compile(r"\\frac\{([^{}]+)\}\{([^{}]+)\}")
            pos = 0
            while True:
                m = pattern.search(s, pos)
                if not m:
                    return s
                a = re.sub(r"^\$|\$$", "", m.group(1)).strip()
                b = re.sub(r"^\$|\$$", "", m.group(2)).strip()
                if cls._is_atom(a) and cls._is_atom(b):
                    s = s[:m.start()] + f"{a}/{b}" + s[m.end():]
                    pos = 0
                else:
                    pos = m.end()
        except Exception:
            return s

    def _strip_trailing_junk(self, s: str) -> str:
        try:
            t = (s or "").strip()
            if not t:
                return s
            junk = set(")\"'`,，.。、；;")
            for _ in range(8):
                if not t or t[-1] not in junk:
                    break
                last = t[-1]
                if last in ")]":
                    opens = t.count("(") - t.count(")")
                    opens_sq = t.count("[") - t.count("]")
                    if last == ")" and opens < 0:
                        if opens_sq > 0 and opens + opens_sq == 0:
                            break
                        t = t[:-1].rstrip()
                        continue
                    if last == "]" and opens_sq < 0:
                        t = t[:-1].rstrip()
                        continue
                    break
                bal = ((t.count("(") - t.count(")")) +
                       (t.count("[") - t.count("]")) +
                       (t.count("{") - t.count("}")))
                if bal <= 0:
                    t = t[:-1].rstrip()
                    continue
                break
            return t if t else s
        except Exception:
            return s

    def _normalize_proof_conclusion(self, s: str) -> str:
        try:
            t = (s or "").strip()
            if not t or len(t) > 12:
                return ""
            t2 = re.sub(r"^(该|此|这个|本题|结论|所以|因此|故)\s*", "", t)
            t2 = t2.strip(" 。.，,：:；;")
            low = t2.casefold()
            if any(m in low for m in (
                "不一定", "未必", "不必然", "不确定", "无法确定", "不能确定")):
                return ""
            neg = {"不成立", "命题不成立", "不正确", "命题不正确", "false",
                   "错", "错误", "不真", "命题为假"}
            pos = {"成立", "命题成立", "正确", "命题正确", "得证", "命题得证",
                   "true", "对", "为真", "命题为真"}
            if low in neg:
                return "命题不成立"
            if low in pos:
                return "命题成立"
            return ""
        except Exception:
            return ""

    def _normalize_undetermined(self, s: str) -> str:
        try:
            t = (s or "").strip(" 。.，,：:；;()（）")
            if not t or len(t) > 24:
                return ""
            if re.search(r"-?\d+(?:\.\d+)?(?:/\d+)?|[A-Da-d]", t):
                return ""
            low = t.casefold()
            keys = ("无法确定", "无法解答", "无法判断", "无法给出", "不能确定",
                    "不能判断", "不能解答", "不确定", "难以确定", "无法求",
                    "题目为空", "题目内容为空", "缺少题目", "缺少条件",
                    "条件不足", "信息不足", "信息不全", "undetermined",
                    "cannot determine", "no answer",
                    "cannot be determined", "insufficient")
            if low in {k.casefold() for k in keys}:
                return "无法确定"
            return ""
        except Exception:
            return ""

    def _canonicalize_set(self, s: str) -> str:
        try:
            inner = str(s or "").strip()[1:-1].strip()
            if not inner:
                return "{}"
            parts = self._split_top_level_commas(inner)
            if not parts:
                return "{" + re.sub(r"\s+", " ", inner).strip() + "}"
            normalized = []
            for part in parts:
                value = re.sub(r"\s+", " ", part).strip()
                if value and value not in normalized:
                    normalized.append(value)
            return "{" + ",".join(sorted(normalized)) + "}"
        except Exception:
            return str(s or "").strip()

    @staticmethod
    def _split_top_level_commas(text: str) -> List[str]:
        parts: List[str] = []
        start, depth = 0, 0
        pairs = {"{": "}", "(": ")", "[": "]"}
        closing = set(pairs.values())
        for index, char in enumerate(text):
            if char in pairs:
                depth += 1
            elif char in closing and depth > 0:
                depth -= 1
            elif char == "," and depth == 0:
                parts.append(text[start:index])
                start = index + 1
        parts.append(text[start:])
        return parts

    def _normalize_multi_answer(self, s: str) -> str:
        try:
            t = s.strip()
            if not t:
                return s
            num = r"[+-]?\d+(?:\.\d+)?(?:/\d+)?"
            m = re.fullmatch(r"((?:%s)(?:\s*(?:或|or)\s*(?:%s))+)" % (num, num),
                             t, flags=re.IGNORECASE)
            if m:
                nums = re.findall(num, m.group(1))
                return "{" + ",".join(self._normalize_number(n) for n in nums) + "}"
            m = re.fullmatch(
                r"(?:%s)(?:\s*[,，]\s*(?:%s))+" % (num, num), t)
            if m:
                nums = re.findall(num, t)
                if len(nums) >= 2:
                    return "{" + ",".join(
                        self._normalize_number(n) for n in nums) + "}"
            return s
        except Exception:
            return s

    def _normalize_interval_union(self, s: str) -> str:
        try:
            t = (s or "").strip().strip(" 。.，,")
            if not t:
                return ""
            has_union = any(
                tok in t for tok in ("\\cup", "∪", "∪", "∪", " U ", ")U(", ")or(", ")或("))
            if not has_union:
                return ""
            if "(" not in t or ")" not in t:
                return ""
            parts = re.split(r"\\cup|∪|∪|∪|\bU\b|\bor\b|或", t)
            parts = [p.strip(" ,，") for p in parts if p and p.strip(" ,，")]
            if len(parts) < 2:
                return ""
            norm_parts = []
            for p in parts:
                pt = (p or "").strip()
                pt = re.sub(r"\\?infty|\\?inf\b|∞|无穷", "∞", pt,
                           flags=re.IGNORECASE)
                pt = re.sub(r"\+\s*∞", "∞", pt)
                pt = re.sub(r"\s+", "", pt)
                if not pt:
                    return ""
                norm_parts.append(pt)
            joined = "∪".join(norm_parts)
            return re.sub(r"\s+", "", joined)
        except Exception:
            return ""

    @staticmethod
    def _is_interval_or_coord(s: str) -> bool:
        try:
            t = s.strip()
            if not t or len(t) > 40:
                return False
            interval_re = re.compile(
                r"^[\[\(]\s*-?\s*(?:\\?infty|∞|\+?inf|-?\d+(?:\.\d+)?)"
                r"\s*,\s*-?\s*(?:\\?infty|∞|\+?inf|-?\d+(?:\.\d+)?)\s*[\]\)]$",
                re.IGNORECASE)
            if interval_re.match(t):
                return True
            if re.fullmatch(
                r"\(\s*-?\d+(?:\.\d+)?(?:\s*,\s*-?\d+(?:\.\d+)?)+\s*\)", t):
                return True
            return False
        except Exception:
            return False

    def _normalize_number(self, s: str) -> str:
        s = s.strip()
        if re.fullmatch(r"[+-]?\d+", s):
            try:
                return str(int(s))
            except Exception:
                return s
        if re.fullmatch(r"[+-]?\d+\.\d+", s):
            try:
                value = Decimal(s)
                if not value.is_finite():
                    return s
                normalized = format(value, "f")
                if "." in normalized:
                    normalized = normalized.rstrip("0").rstrip(".")
                return normalized or "0"
            except (InvalidOperation, ValueError):
                return s
        if re.fullmatch(r"[+-]?\d+/\d+", s):
            sign = ""
            body = s
            if s[0] in "+-":
                sign = "-" if s[0] == "-" else ""
                body = s[1:]
            num, den = body.split("/")
            try:
                fr = Fraction(int(num), int(den))
                if fr.denominator == 1:
                    return sign + str(fr.numerator) if sign == "-" else str(
                        fr.numerator)
                return f"{sign}{fr.numerator}/{fr.denominator}"
            except Exception:
                return s
        return s


# =============================================================================
# answers_equal — answer equivalence for clustering
# =============================================================================

def _as_fraction(text: str) -> Optional[Fraction]:
    try:
        s = str(text or "").strip()
        if not s:
            return None
        return Fraction(s)
    except Exception:
        return None


def answer_aliases(answer: str) -> List[str]:
    """Generate numeric aliases: fraction ↔ decimal ↔ percent."""
    text = str(answer or "").strip()
    aliases: List[str] = [text]
    try:
        if re.fullmatch(r"[+-]?\d+/\d+", text):
            value = Fraction(text)
            if value.denominator != 1:
                aliases.append(str(float(value)))
                percent = value * 100
                if percent.denominator == 1:
                    aliases.append("%d%%" % percent)
            else:
                aliases.append(str(value.numerator))
        elif re.fullmatch(r"[+-]?\d+\.\d+", text):
            value = Fraction(text)
            aliases.append("%d/%d" % (value.numerator, value.denominator))
            percent = value * 100
            if 0 < value < 1 and percent.denominator == 1:
                aliases.append("%d%%" % percent)
        elif re.fullmatch(r"[+-]?\d+%", text):
            value = Fraction(int(text[:-1]), 100)
            aliases.append(str(float(value)))
            aliases.append("%d/%d" % (value.numerator, value.denominator))
        elif re.fullmatch(r"[+-]?\d+ \d+/\d+", text):
            parts = text.split()
            whole = int(parts[0])
            num, den = (int(v) for v in parts[1].split("/"))
            if den != 0:
                mixed = whole * den + num
                aliases.append("%d/%d" % (mixed, den))
    except (ValueError, ZeroDivisionError):
        pass
    return [a for a in aliases if a]


def answers_equal(a: str, b: str) -> bool:
    """Generic answer equivalence for candidate clustering."""
    try:
        if a == b:
            return True
        if a is None or b is None:
            return False
        normalizer = AnswerNormalizer()
        sa = normalizer.normalize(str(a))
        sb = normalizer.normalize(str(b))
        if not sa or not sb:
            return False
        if sa == sb:
            return True
        # Union intervals: order-independent
        if "∪" in sa and "∪" in sb:
            try:
                if sorted(p for p in sa.split("∪") if p) == sorted(
                    p for p in sb.split("∪") if p):
                    return True
            except Exception:
                pass
        # Fraction equivalence
        fa = _as_fraction(sa)
        fb = _as_fraction(sb)
        if fa is not None and fb is not None and fa == fb:
            return True
        # Numeric aliases
        if set(answer_aliases(sa)) & set(answer_aliases(sb)):
            return True
        return False
    except Exception:
        return False


# =============================================================================
# OutputParser — model output analysis
# =============================================================================

_FINAL_RE = re.compile(
    r"FINAL\s*[:：]\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE)
_FINAL_PREFIX_RE = re.compile(r"FINAL\s*[:：]\s*", re.IGNORECASE)
_PART_VALUE_LINE_RE = re.compile(
    r"^\s*(?:[\(（]\d+[\)）]|\d+[.)、:：]|[①-⑳]|"
    r"[\(（][A-Za-z][\)）]|[A-Za-z][.)])\s*\S+")
_FENCE_RE = re.compile(
    r"```(?:python|py|tool|code|run)?\s*\n(.*?)```",
    re.DOTALL | re.IGNORECASE)


class OutputParser:
    """Parse model output: code blocks + final answer."""

    def __init__(self) -> None:
        self.extractor = AnswerExtractor()
        self.normalizer = AnswerNormalizer()

    @staticmethod
    def _strip_code(text: str) -> str:
        return _FENCE_RE.sub(" ", text or "")

    def has_explicit_final(self, text: str) -> bool:
        try:
            return bool(_FINAL_PREFIX_RE.search(
                self._strip_code(text or "")))
        except Exception:
            return False

    def extract_declared_final(self, text: str) -> str:
        """High-precision extraction: explicit FINAL > boxed > markers."""
        if not text:
            return ""
        try:
            txt = self._strip_code(text)
            values = self._explicit_final_values(txt)
            if self.has_explicit_final(txt):
                raw = str(values[-1] if values else "").strip()
                if not raw:
                    return ""
                normalized = self.normalizer.normalize(raw)
                if self.extractor._is_placeholder(raw):
                    return ""
                if normalized and self.extractor._is_placeholder(normalized):
                    return ""
                return normalized or raw

            boxed = self.extractor._extract_last_boxed(txt)
            if boxed:
                raw = str(boxed).strip()
                normalized = self.normalizer.normalize(raw)
                if normalized and not self.extractor._is_placeholder(normalized):
                    return normalized

            for pattern in self.extractor.MARKERS:
                raw = str(self.extractor._extract_after_marker(
                    txt, pattern) or "").strip()
                normalized = self.normalizer.normalize(raw)
                if normalized and not self.extractor._is_placeholder(normalized):
                    return normalized
            return ""
        except Exception:
            return ""

    def extract_declared_final_surface(self, text: str) -> str:
        """Extract the judge-facing declared answer without canonical rewriting."""
        if not text:
            return ""
        try:
            txt = self._strip_code(text)
            explicit = self._explicit_final_values(txt)
            if self.has_explicit_final(txt):
                raw = str(explicit[-1] if explicit else "").strip()
                if not raw:
                    return ""
                normalized = self.normalizer.normalize(raw)
                if self.extractor._is_placeholder(raw):
                    return ""
                if normalized and self.extractor._is_placeholder(normalized):
                    return ""
                return raw
            boxed = self.extractor._extract_last_boxed(txt)
            if boxed:
                raw = str(boxed).strip()
                normalized = self.normalizer.normalize(raw)
                if normalized and not self.extractor._is_placeholder(normalized):
                    return raw
            for pattern in self.extractor.MARKERS:
                raw = str(self.extractor._extract_after_marker(
                    txt, pattern) or "").strip()
                normalized = self.normalizer.normalize(raw)
                if normalized and not self.extractor._is_placeholder(normalized):
                    return raw
            return ""
        except Exception:
            return ""

    def extract_final(self, text: str) -> str:
        if not text:
            return ""
        try:
            txt = self._strip_code(text)
            for line in reversed(self._explicit_final_values(txt)):
                cand = self.normalizer.normalize(line)
                if cand and not self.extractor._is_placeholder(cand):
                    return cand
            raw = self.extractor.extract(txt)
            return self.normalizer.normalize(raw) if raw else ""
        except Exception:
            return ""

    def _explicit_final_values(self, text: str) -> List[str]:
        try:
            txt = self._strip_code(text or "")
            markers = list(_FINAL_PREFIX_RE.finditer(txt))
            values: List[str] = []
            for index, marker in enumerate(markers):
                end = (markers[index + 1].start()
                       if index + 1 < len(markers) else len(txt))
                segment = txt[marker.end():end].strip()
                lines = [
                    line.strip() for line in segment.splitlines()
                    if line.strip()
                ]
                if not lines:
                    values.append("")
                    continue
                first = lines[0]
                if _PART_VALUE_LINE_RE.match(first):
                    parts = [first]
                    for line in lines[1:]:
                        if not _PART_VALUE_LINE_RE.match(line):
                            break
                        parts.append(line)
                    values.append("; ".join(parts))
                else:
                    values.append(first)
            return values
        except Exception:
            return []

    def normalize(self, s: str) -> str:
        try:
            return self.normalizer.normalize(s)
        except Exception:
            return str(s or "").strip()
