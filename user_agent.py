"""user_agent.py — ReasoningAgent for competition evaluation.

Platform interface: the judging system provides client with client.chat().
分类 → 求解 → 答案提取 → 兜底
"""

import re
from typing import Dict, List, Optional

from agents import MathClassifier, ComputeSolver, ProofSolver


class ReasoningAgent:
    """数学推理智能体 — 兼容平台 official_client"""

    def __init__(self, client, *args, **kwargs):
        self.client = client
        self.classifier = MathClassifier()
        self.compute_solver = ComputeSolver(client)
        self.proof_solver = ProofSolver(client)

    def solve(self, problem: str, metadata: Optional[Dict] = None) -> Dict:
        if metadata is None:
            metadata = {}

        try:
            return self._do_solve(problem, metadata)
        except Exception as e:
            return {
                "final_response": "未能求解",
                "trace": [
                    {"step": "错误", "content": f"求解异常: {type(e).__name__}: {e}"},
                ],
                "verification": {},
            }

    def _do_solve(self, problem: str, metadata: Dict) -> Dict:
        domain, ptype, difficulty = self.classifier.classify(problem)

        if ptype == "证明题":
            result = self.proof_solver.solve(problem, domain, difficulty, metadata)
        else:
            result = self.compute_solver.solve(problem, domain, difficulty, metadata)

        # 安全兜底提取
        raw = result.get("final_answer", "")
        if not raw or _is_invalid_answer(raw):
            for item in result.get("trace", []):
                content = item if isinstance(item, str) else ""
                ans = _extract_from_text(content)
                if ans and not _is_invalid_answer(ans):
                    raw = ans
                    break
        if not raw or _is_invalid_answer(raw):
            raw = "未能求解"

        # 直接使用 solver 返回的 steps（已含启发性标签）
        trace = list(result.get("steps", []))

        # 如果 steps 为空，构建最小 trace
        if not trace:
            trace = [
                {"step": "分类", "content": f"领域：{domain}，题型：{ptype}，难度：{difficulty}"},
            ]

        lp = result.get("learning_points", [])
        if lp:
            trace.append({"step": "知识点", "content": "；".join(lp)})

        v = result.get("verification", {})
        if v:
            trace.append({"step": "验证", "content": v.get("反馈", "")})

        return {
            "final_response": raw,
            "trace": trace,
            "verification": v,
        }


def _is_invalid_answer(text: str) -> bool:
    """Check if text looks like an error/placeholder, not a real answer."""
    if not text or text in ("未能求解", ""):
        return True
    t = text.strip()
    if t.startswith("[API错误") or t.startswith("[API"):
        return True
    if re.search(r"\[API[^\]]*错误[^\]]*\]", t):
        return True
    return False


def _extract_from_text(text: str) -> str:
    """从文本中提取答案（兜底用）"""
    if not text:
        return ""
    lines = text.strip().split('\n')
    for i in range(len(lines) - 1, -1, -1):
        m = re.search(r'ANSWER\s*[：:]\s*(.+)', lines[i], re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return ""
