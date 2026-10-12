"""TF-IDF 题库检索器（轻量替代向量库 chroma + embedding 模型）。

为什么不用 chroma：原向量库（chroma.sqlite3）与 embedding 模型权重
在 git 里都是 LFS 指针，本地 checkout 无真实数据；其
语料目录也不存在于评测环境。照搬 chroma 路径等于在评测时
"检索永远为空"。

本实现用纯 scikit-learn 的 TF-IDF（char n-gram，捕捉 LaTeX 符号、CJK 子串与
英文子词），语料从比赛公开的 sample_data 离线提取成紧凑 JSON。检索近邻命中
"措辞接近"的相似题——这正是 RAG 要的东西——且零新增依赖、任何环境可跑。

相似度是余弦相似度（L2 归一化后点积），只用于排序与展示；绝对值与 embedding
的尺度不同，但排序与"近似题"识别能力等价，且反锚定机制（reference_block）不
依赖相似度的绝对阈值。
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

#: 语料 JSON 的默认位置（相对项目根目录）。运行时只依赖这个文件，不依赖任何
#: 外部语料目录、模型权重或 LFS 数据。
_DEFAULT_CORPUS = Path(__file__).resolve().parent.parent.parent / "data" / "retrieval_corpus.json"


def _norm(text: str) -> str:
    """归一化题面：折叠空白，便于 TF-IDF 与去重时得到稳定特征。"""
    return re.sub(r"\s+", " ", str(text or "")).strip()


#: 纯答案（answer 字段）判定。语料 solution 字段大多源自公开样例的 answer 字段，
#: 其中既有短答案（"070"、"588"），也有长答案句（``\boxed{...}`` 数值列表、分情况
#: 答案描述）——单纯长度阈值拦不住后者。规则禁止依赖 answer 字段，检索只应提供
#: 「相似题面 + 解答方法」参考，不能把答案搬回来。故用「内容判定」：只有含推导/
#: 论证迹象（``_PROCESS_HINTS``）的才视为解答过程保留，其余（答案/答案句/占位）清空。
_SOLUTION_MIN_LEN = 30

#: 解答过程的强信号：这些论证词/LaTeX 推导结构几乎只出现在「推导」里，不出现在
#: 纯答案里。语料基本是英文（solution 含中文仅 1/1555），故只列英文论证词。
_PROCESS_HINTS = (
    "let ", "since ", "therefore", "hence", "thus ", "consider ", "suppose ",
    "assume ", "we have", "note that", "it follows", "implies", r"\begin{",
    r"\Rightarrow", r"\implies",
)


def _usable_solution(solution: str | None) -> bool:
    """solution 是否为「可用的解答过程」而非纯答案 answer 字段。

    规则禁止依赖 answer 字段——检索只提供「相似题面 + 解答方法」参考，不搬答案。
    清空（返回 False）的情形：空、占位文本、LaTeX 答案框 ``\boxed{...}``、过短、
    或没有任何推导/论证迹象（纯数值列表、答案描述句、分情况答案）。只有含
    ``_PROCESS_HINTS`` 里的论证词/推导结构的才视为解答过程，返回 True。
    """
    s = str(solution or "").strip()
    if not s:
        return False
    if r"\boxed{" in s:
        return False
    if "no solution provided" in s.lower():
        return False
    if len(s) < _SOLUTION_MIN_LEN:
        return False
    low = s.lower()
    return any(h in low for h in _PROCESS_HINTS)


class TfidfRetriever:
    """惰性加载语料 + 构建 TF-IDF 索引；query 返回 top-k 相似题。"""

    def __init__(self, corpus_path: Optional[str] = None):
        self.corpus_path = Path(corpus_path) if corpus_path else _DEFAULT_CORPUS
        self._records: List[Dict[str, Any]] = []
        self._vectorizer = None
        self._matrix = None
        self._loaded = False
        self._load_error: Optional[str] = None

    def _load(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        if not self.corpus_path.exists():
            self._load_error = f"corpus not found: {self.corpus_path}"
            return
        try:
            with open(self.corpus_path, "r", encoding="utf-8") as fh:
                raw = json.load(fh)
            self._records = [r for r in raw if isinstance(r, dict)
                             and str(r.get("problem") or "").strip()]
            if not self._records:
                self._load_error = "empty corpus"
                return
            from sklearn.feature_extraction.text import TfidfVectorizer

            self._vectorizer = TfidfVectorizer(
                analyzer="char_wb",
                ngram_range=(2, 5),
                min_df=2,
                sublinear_tf=True,
                strip_accents="unicode",
            )
            docs = [_norm(r["problem"]) for r in self._records]
            self._matrix = self._vectorizer.fit_transform(docs)
        except Exception as exc:  # noqa: BLE001 - 检索是纯增益，失败降级为空结果
            self._load_error = f"corpus load failed: {exc!r}"
            self._records = []
            self._vectorizer = None
            self._matrix = None

    def is_available(self) -> bool:
        self._load()
        return self._matrix is not None and bool(self._records)

    def query(self, problem: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """返回 top-k 条相似题，结构对齐 db_client.query。

        返回项键：problem / solution / similarity / source / subject。
        solution 对「纯答案（answer 字段，短于 30 字符）」已清空为空串——检索只提供
        题面+方法参考，不提供答案（规则禁止依赖 answer 字段）。
        任何失败（无语料、加载失败、查询异常）都返回空列表，绝不抛异常。
        """
        self._load()
        if self._matrix is None or not self._records:
            return []
        text = _norm(problem)
        if not text:
            return []
        try:
            from sklearn.metrics.pairwise import cosine_similarity

            q_vec = self._vectorizer.transform([text])
            sims = cosine_similarity(q_vec, self._matrix)[0]
            top_k = max(1, int(top_k or 1))
            order = sorted(range(len(sims)), key=lambda i: -sims[i])[:top_k]
            results = []
            for i in order:
                rec = self._records[i]
                # 跳过"与查询完全相同"的题（检索不该把题面本身喂回给模型）。
                if _norm(rec.get("problem", "")) == text:
                    continue
                # 纯答案（answer 字段）的 solution 清空为空串：检索只提供题面+方法
                # 参考，绝不把答案字段喂回给模型（规则禁止依赖 answer 字段）。
                raw_solution = rec.get("solution")
                results.append({
                    "problem": str(rec.get("problem") or ""),
                    "solution": (str(raw_solution) if _usable_solution(raw_solution)
                                 else ""),
                    "similarity": float(sims[i]),
                    "source": str(rec.get("source") or ""),
                    "subject": str(rec.get("subject") or ""),
                })
            return results
        except Exception:  # noqa: BLE001 - 检索失败降级为空，绝不打断求解
            return []
