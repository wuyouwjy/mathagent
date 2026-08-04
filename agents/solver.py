"""Unified math solver (v5) — replaces separate compute/proof solvers.

Uses the same multi-stage pipeline as user_agent.py but exposed as a
standalone module for optional use by the classifier dispatch path.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

# Safe import with fallback
try:
    from prompts import (
        COMPUTE_SOLVE_PROMPT,
        PROOF_SOLVE_PROMPT,
        ENGLISH_THINK_PATTERNS,
        TEMPLATE_LEAK_PATTERNS,
    )
except ImportError:
    COMPUTE_SOLVE_PROMPT = """题目（{domain}）：\n{problem}\n\n请逐步解答，最后输出 ANSWER: <答案>"""
    PROOF_SOLVE_PROMPT = """题目（{domain}）：\n{problem}\n\n请逐步证明，最后输出 ANSWER: <结论>"""
    ENGLISH_THINK_PATTERNS: List[str] = []
    TEMPLATE_LEAK_PATTERNS: List[str] = []


# ── answer extraction (same strategies as user_agent.py) ─────────────

def extract_answer(text: str) -> str:
    """5-layer answer extraction."""
    if not text or not text.strip():
        return ""

    lines = text.strip().split("\n")

    # L1: ANSWER: marker
    for i in range(len(lines) - 1, -1, -1):
        m = re.search(r"ANSWER\s*[：:]\s*(.+)", lines[i], re.IGNORECASE)
        if m:
            ans = m.group(1).strip().rstrip("。，,;；. ")
            if ans:
                return ans

    # L2: \boxed{}
    for i in range(len(lines) - 1, -1, -1):
        matches = re.findall(r"\\boxed\{([^{}]+)\}", lines[i])
        if matches:
            return matches[-1].strip()

    # L3: conclusion markers
    for marker in ["最终答案", "答案是", "答案为", "结果为", "结论为", "答案：", "答案:"]:
        for i in range(len(lines) - 1, -1, -1):
            if marker in lines[i]:
                idx = lines[i].find(marker)
                tail = lines[i][idx + len(marker):].strip().lstrip("：: ")
                if tail:
                    return tail[:300]
                if i + 1 < len(lines) and lines[i + 1].strip():
                    return lines[i + 1].strip()[:300]

    # L4: last math line
    for i in range(len(lines) - 1, -1, -1):
        s = lines[i].strip()
        if s and re.search(r"[$\\{}]|\d+", s):
            return s[:300]

    # L5: last non-empty
    for i in range(len(lines) - 1, -1, -1):
        s = lines[i].strip()
        if s:
            return s[:200]

    return ""


def is_truncated(content: str) -> bool:
    """Detect truncated model output."""
    if not content or len(content.strip()) < 10:
        return False
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
    if re.search(r"[。！？\.!?]\)]$", last_line):
        return False
    connecting_words = [
        "虽然", "但是", "因此", "所以", "由于", "当", "若", "令", "设",
        "对于", "考虑", "由", "根据", "利用", "通过", "于是", "故",
        "假设", "注意到",
    ]
    stripped = re.sub(r"[,，；;、\s]+$", "", last_line)
    for w in connecting_words:
        if stripped.endswith(w):
            return True
    if last_line.count("$") % 2 == 1:
        return True
    if re.search(r"[,，\(（]\s*$", last_line):
        return True
    if len(content) > 2000 and not re.search(r"[。！？\.!?]\s*$", last_line):
        return True
    return False


def has_english_leak(content: str) -> bool:
    """Detect English chain-of-thought leakage."""
    if not content:
        return False
    cn_chars = sum(1 for c in content if "\u4e00" <= c <= "\u9fff")
    total = max(len(content.strip()), 1)
    if cn_chars / total < 0.08 and total > 100:
        return True
    matches = sum(1 for p in ENGLISH_THINK_PATTERNS if re.search(p, content[:500], re.I))
    return matches >= 3 and cn_chars < 50


# ── unified solver class ──────────────────────────────────────────────

class MathSolver:
    """Unified solver for both computation and proof problems."""

    MAX_TOKENS = 8192
    CONTINUATION_TOKENS = 4096

    def __init__(self, client: Any) -> None:
        self.client = client

    def solve(
        self,
        problem: str,
        domain: str = "数学",
        ptype: str = "计算题",
        metadata: Optional[Dict] = None,
    ) -> Dict:
        """Solve a math problem and return the result dict."""
        if metadata is None:
            metadata = {}

        all_contents: List[str] = []
        is_continued = False
        is_followup = False

        # Choose prompt template
        if ptype == "证明题":
            template = PROOF_SOLVE_PROMPT
        else:
            template = COMPUTE_SOLVE_PROMPT

        prompt = template.format(domain=domain, problem=problem)

        # ── Main solve ──────────────────────────────────────────
        try:
            resp = self.client.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=self.MAX_TOKENS,
            )
            content = resp.get("content", "") if isinstance(resp, dict) else str(resp)
        except Exception as e:
            return self._empty_result(f"API调用失败: {e}", domain, ptype)

        all_contents.append(content)

        # ── Continuation if truncated ───────────────────────────
        if is_truncated(content):
            try:
                resp2 = self.client.chat(
                    messages=[
                        {"role": "user", "content": prompt},
                        {"role": "assistant", "content": content},
                        {"role": "user", "content": "继续完成解答。最后给出 ANSWER: <答案>"},
                    ],
                    temperature=0.1,
                    max_tokens=self.CONTINUATION_TOKENS,
                )
                cont = resp2.get("content", "") if isinstance(resp2, dict) else str(resp2)
                all_contents.append(cont)
                content = content + "\n" + cont
                is_continued = True
            except Exception:
                pass

        # ── Retry if English leak ───────────────────────────────
        if has_english_leak(content):
            try:
                cn_prompt = (
                    f"请用中文重新解答以下数学题。直接给出完整解答，"
                    f"不要用英文自言自语。\n\n{problem}\n\n"
                    f"解答最后写 ANSWER: <最终答案>"
                )
                resp3 = self.client.chat(
                    messages=[{"role": "user", "content": cn_prompt}],
                    temperature=0.15,
                    max_tokens=self.MAX_TOKENS,
                )
                cn_content = resp3.get("content", "") if isinstance(resp3, dict) else str(resp3)
                all_contents.append(cn_content)
                content = cn_content
                is_followup = True
            except Exception:
                pass

        # ── Answer extraction ───────────────────────────────────
        answer = extract_answer(content)
        if not answer:
            for raw in all_contents:
                answer = extract_answer(raw)
                if answer:
                    break

        if not answer:
            answer = "未能求解"

        # ── Build trace ─────────────────────────────────────────
        steps = self._build_trace(content, domain, ptype)

        return {
            "final_answer": answer,
            "steps": steps,
            "trace": all_contents,
            "is_followup": is_followup,
            "is_continued": is_continued,
            "learning_points": self._learning_points(domain),
            "verification": {
                "置信度": 0.90 if answer != "未能求解" else 0.40,
                "方法": f"续写={is_continued}, 追问={is_followup}",
                "反馈": f"解题{len(steps)}步, 答案{'有效' if answer != '未能求解' else '缺失'}",
            },
        }

    def _build_trace(self, content: str, domain: str, ptype: str) -> List[Dict]:
        """Build structured trace from model output."""
        steps: List[Dict] = [{"step": "分类", "content": f"领域：{domain}，题型：{ptype}"}]

        if not content:
            return steps

        # Extract reasoning chunks (lines with Chinese + math content)
        chunks: List[str] = []
        for line in content.split("\n"):
            line = line.strip()
            if len(line) > 10 and re.search(r"[\u4e00-\u9fff]", line):
                # Skip ANSWER lines
                if re.match(r"ANSWER\s*[：:]", line, re.IGNORECASE):
                    continue
                chunks.append(line[:200])
            if len(chunks) >= 8:
                break

        for i, chunk in enumerate(chunks):
            steps.append({
                "step": f"步骤{i + 1}",
                "content": chunk,
                "tool": "推理" if ptype == "证明题" else "计算",
            })

        return steps

    @staticmethod
    def _learning_points(domain: str) -> List[str]:
        """Map domain to learning points."""
        mapping = {
            "数学分析": ["极限与连续性", "微分学", "积分学", "级数"],
            "高等代数": ["行列式", "矩阵", "线性空间", "特征值"],
            "抽象代数": ["群论基础", "环论", "域论", "伽罗瓦理论"],
            "概率论": ["随机变量", "概率分布", "期望与方差"],
            "数论": ["整除性", "同余", "素数", "不定方程"],
            "组合数学": ["计数原理", "生成函数", "递推关系"],
            "拓扑学": ["点集拓扑", "连通性", "紧性"],
            "复分析": ["全纯函数", "积分", "留数定理"],
            "实分析": ["Lebesgue测度", "可积函数", "L^p空间"],
            "偏微分方程": ["常微分方程", "偏微分方程"],
            "解析几何": ["向量", "平面与直线", "曲面"],
            "微分几何": ["曲线论", "曲面论", "曲率"],
        }
        return mapping.get(domain, ["数学推理", "逻辑推导", "结果验证"])

    @staticmethod
    def _empty_result(error: str, domain: str, ptype: str) -> Dict:
        return {
            "final_answer": "未能求解",
            "steps": [{"step": "错误", "content": error}],
            "trace": [],
            "is_followup": False,
            "is_continued": False,
            "learning_points": [],
            "verification": {"置信度": 0.0, "方法": "失败", "反馈": error},
        }
