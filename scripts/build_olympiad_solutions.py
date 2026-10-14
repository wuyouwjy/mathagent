# -*- coding: utf-8 -*-
"""从 AI-MO/olympiads 提取 (题目, 解法) 对，构建真解法检索语料。

只提取 Evan Chen Solution Notes 格式（## Problems 列题 + ## Solutions 分节给解法），
目前覆盖 IMO / USAMO / EGMO / APMO 等主流竞赛。solution 是真推导过程（不是 answer
纯答案），合规：规则只禁止依赖 answer 字段，solution 字段是允许的（ICMAnew 同款）。

用法：
    python scripts/build_olympiad_solutions.py

输出：data/olympiad_solutions.json（追加进检索语料，不覆盖原 1555 条）。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.request import Request, urlopen, ProxyHandler, build_opener

PROXY = "http://127.0.0.1:7897"
BASE = "https://huggingface.co/datasets/AI-MO/olympiads/resolve/main"
API = "https://huggingface.co/api/datasets/AI-MO/olympiads/tree/main"

#: 只处理 Evan Chen notes 格式的竞赛（格式统一、题目+解法齐全）。
COMPETITIONS = ["IMO", "USAMO", "EGMO", "APMO"]

opener = build_opener(ProxyHandler({"http": PROXY, "https": PROXY}))


def _get(url: str) -> str:
    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    return opener.open(req, timeout=30).read().decode("utf-8", errors="replace")


def list_files(comp: str) -> list[str]:
    data = json.loads(_get(f"{API}/{comp}/md"))
    return [s["path"] for s in data if isinstance(s, dict) and s["path"].endswith(".md")]


#: Evan Chen notes 的题目编号行： "1. ..." / "## Problems" 之后的编号列表。
_PROBLEM_SPLIT_RE = re.compile(r"^(\d{1,2})\.\s+", re.MULTILINE)
#: 解法的分节标题： "## § 1.1 IMO 2019/1" / "## § 2.3 ..."
_SOL_HEADER_RE = re.compile(
    r"^#{1,4}\s*§?\s*(\d{1,2})\.(\d{1,2})\b", re.MULTILINE
)


def parse_notes(text: str) -> list[dict]:
    """从 Evan Chen notes.md 提取 [(problem, solution), ...]。

    结构（Evan Chen Solution Notes）：
    - `## Problems` 之后按 `N.` 编号列题目；
    - 之后 `## \\(\\S day\\) Solutions ...` 进入解法区，每道题的解法由
      `## \\(\\S day.num\\)` 分节。解法分节按**出现顺序**与题目编号一一配对
      （不依赖"每天 3 题"，USAMO/EGMO 等题数不同的竞赛同样适用）。
    """
    problems: dict[int, str] = {}
    solutions: dict[int, str] = {}

    # 1) 题目区：## Problems 到第一个含 "Solutions" 的 ## 标题之间。
    pm = re.search(r"##\s*Problems\b", text)
    if not pm:
        return []
    sm = re.search(r"##[^\n]*[Ss]olutions", text[pm.end():])
    prob_end = pm.end() + sm.start() if sm else len(text)
    prob_block = text[pm.end():prob_end]

    chunks = re.split(r"(?m)^(\d{1,2})\.\s+", prob_block)
    for i in range(1, len(chunks), 2):
        try:
            num = int(chunks[i])
            body = re.sub(r"\s+", " ", chunks[i + 1]).strip()
            if len(body) > 10:
                problems[num] = body
        except (ValueError, IndexError):
            continue

    # 2) 解法区：`## \(\S day.num\) IMO YYYY/N, proposed by ...` 分节（整行标题，
    # 含署名），按出现顺序 = 题号。每个分节 = 标题行之后到下一题标题之前。
    sol_header = re.compile(r"##\s*\\\(\s*\\S\s*\d{1,2}\.\d{1,2}\s*\\\)[^\n]*")
    matches = list(sol_header.finditer(text))
    for order, m in enumerate(matches, 1):
        start = m.end()
        end = matches[order].start() if order < len(matches) else len(text)
        body = text[start:end]
        # 删外部链接行与图片引用（非解法内容）。
        body = re.sub(r"Available online at [^\n]*", " ", body)
        body = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", body)
        # 只删 "## Problem statement" 标题本身，其后的题目正文**保留**在 solution 里。
        # 旧实现用「删到第一个推导词(Let/We/Since/...)」切分题目与解法，但解法常以
        # The/Obviously/Negating/Assume 开头（不在词表里），正则一路删到分节末尾，
        # 把解法整段误删（样本 1.1 的 solution 只剩署名标题）。题目在 problem 字段
        # 已有、混入无害，故不再切分——宁可多留题目正文，也不误删解法。
        body = re.sub(r"##\s*Problem\s+statement", " ", body)
        body = re.sub(r"\s+", " ", body).strip()
        if len(body) > 30:
            solutions[order] = body

    out = []
    for num in sorted(problems):
        out.append({
            "problem": problems[num],
            "solution": solutions.get(num, ""),
            "source": "AI-MO/olympiads",
            "subject": "",
        })
    return out


def main() -> None:
    all_pairs: list[dict] = []
    for comp in COMPETITIONS:
        files = list_files(comp)
        print(f"[{comp}] {len(files)} 个 md 文件", file=sys.stderr)
        for path in files:
            try:
                text = _get(f"{BASE}/{path}")
            except Exception as exc:  # noqa: BLE001
                print(f"  [skip] {path}: {exc}", file=sys.stderr)
                continue
            pairs = parse_notes(text)
            for p in pairs:
                p["source"] = f"AI-MO/{path.split('/')[0]}"
                all_pairs.append(p)
            if pairs:
                print(f"  {path.split('/')[-1]}: {len(pairs)} 题", file=sys.stderr)

    # 去重（按题面）
    seen, dedup = set(), []
    for p in all_pairs:
        if p["problem"] in seen:
            continue
        seen.add(p["problem"])
        dedup.append(p)

    out = Path(__file__).resolve().parent.parent / "data" / "olympiad_solutions.json"
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(dedup, fh, ensure_ascii=False)

    with_sol = sum(1 for p in dedup if len(p["solution"]) >= 30)
    print(f"\n提取 {len(all_pairs)} -> 去重 {len(dedup)}，"
          f"含真解法(≥30字符) {with_sol} 条", file=sys.stderr)
    print(f"已写 {out}（{out.stat().st_size / 1024:.1f} KB）", file=sys.stderr)


if __name__ == "__main__":
    main()
