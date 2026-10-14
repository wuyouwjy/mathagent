# -*- coding: utf-8 -*-
"""把 data/olympiad_solutions.json 的真解法合并进检索语料 retrieval_corpus.json。

合规约束：只追加 solution 为真解法（≥30 字符，含推导正文）的条目；现有语料里
solution 是纯答案（answer 冒充）的条目原样保留、不动——注入层
``utils.retrieval.reference_block._usable_solution`` 会在运行时跳过它们，不把答案
喂给模型。合并后按 problem 去重，写回前备份原语料到 .bak。

用法：
    python scripts/merge_solutions_corpus.py
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

MIN_SOLUTION_CHARS = 30


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    corpus_path = root / "data" / "retrieval_corpus.json"
    olympiad_path = root / "data" / "olympiad_solutions.json"

    corpus = json.load(open(corpus_path, encoding="utf-8"))
    olympiad = json.load(open(olympiad_path, encoding="utf-8"))
    original_count = len(corpus)

    new_pairs = [
        p for p in olympiad
        if len(str(p.get("solution", "")).strip()) >= MIN_SOLUTION_CHARS
    ]

    seen = {str(p.get("problem", "")).strip() for p in corpus}
    added = 0
    for p in new_pairs:
        prob = str(p.get("problem", "")).strip()
        if not prob or prob in seen:
            continue
        seen.add(prob)
        corpus.append({
            "problem": prob,
            "solution": str(p.get("solution", "")).strip(),
            "source": str(p.get("source", "") or "AI-MO/olympiads"),
            "subject": str(p.get("subject", "") or ""),
        })
        added += 1

    # 备份原语料（仅首次，避免覆盖已有备份）。
    backup = corpus_path.with_suffix(".json.bak")
    if not backup.exists():
        shutil.copy2(corpus_path, backup)

    with open(corpus_path, "w", encoding="utf-8") as fh:
        json.dump(corpus, fh, ensure_ascii=False)

    print(f"原语料 {original_count} 条 + 新增真解法 {added} 条 = {len(corpus)} 条")
    print(f"备份：{backup}")
    print(f"已写：{corpus_path}")


if __name__ == "__main__":
    main()
