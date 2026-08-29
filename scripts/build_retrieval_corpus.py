"""离线构建题库检索语料。

从比赛公开的 sample_data（putnam/aime/imo 等 jsonl）提取 (problem, answer) 对，
按题面归一化去重，写成 data/retrieval_corpus.json。这个 JSON 是唯一随项目提交
的检索数据；运行时 TfidfRetriever 只读它，不依赖 sample_data、模型权重或任何
外部语料目录。

用法：
    python scripts/build_retrieval_corpus.py --sample-data <path/to/sample_data>

合规：本脚本只读公开 benchmark 数据，answer 字段仅用于离线构建检索库，
求解器运行时绝不读取评测传入的 metadata 里的标准答案。
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, List


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _load_records(sample_data: Path) -> List[Dict[str, Any]]:
    """遍历 sample_data 下所有 jsonl，提取 (problem, answer, source, subject)。"""
    records: List[Dict[str, Any]] = []
    files = sorted(sample_data.rglob("*.jsonl"))
    for path in files:
        try:
            with open(path, "r", encoding="utf-8") as fh:
                lines = fh.readlines()
        except Exception as exc:  # noqa: BLE001
            print(f"[skip] 无法读取 {path}: {exc}")
            continue
        for ln in lines:
            ln = ln.strip()
            if not ln:
                continue
            try:
                obj = json.loads(ln)
            except Exception:  # noqa: BLE001 - 跳过损坏/空行
                continue
            if not isinstance(obj, dict):
                continue
            problem = _norm(obj.get("problem") or "")
            if not problem:
                continue
            # 标准答案字段：answer 优先，gold_answer 兜底。wrong 类文件里这两个
            # 字段都是标准答案（错误答案在 model_answer 里），不是模型输出。
            answer = obj.get("answer")
            if answer is None or str(answer).strip() == "":
                answer = obj.get("gold_answer")
            if answer is None:
                answer = ""
            records.append({
                "problem": problem,
                "solution": str(answer).strip(),
                "source": str(obj.get("source") or path.name),
                "subject": str(obj.get("subject") or ""),
            })
    return records


def _dedup(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """按归一化题面去重，保留首见；无解答的题不占用检索结果。"""
    seen: Dict[str, bool] = {}
    out: List[Dict[str, Any]] = []
    for rec in records:
        key = rec["problem"]
        if key in seen:
            continue
        seen[key] = True
        out.append(rec)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="构建题库检索语料 JSON")
    parser.add_argument("--sample-data", required=True,
                        help="sample_data 目录路径（含 *.jsonl）")
    parser.add_argument("--out", default=None,
                        help="输出 JSON 路径（默认 data/retrieval_corpus.json）")
    args = parser.parse_args()

    sample_data = Path(args.sample_data)
    if not sample_data.is_dir():
        raise SystemExit(f"sample_data 目录不存在: {sample_data}")

    records = _load_records(sample_data)
    deduped = _dedup(records)

    out = Path(args.out) if args.out else (
        Path(__file__).resolve().parent.parent / "data" / "retrieval_corpus.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(deduped, fh, ensure_ascii=False)

    with_solution = sum(1 for r in deduped if r["solution"])
    print(f"提取 {len(records)} 条 -> 去重后 {len(deduped)} 条"
          f"（{with_solution} 条含标准答案）")
    print(f"已写入 {out}（{out.stat().st_size / 1024:.1f} KB）")


if __name__ == "__main__":
    main()
