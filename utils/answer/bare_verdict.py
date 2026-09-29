# -*- coding: utf-8 -*-
"""裸判断词回填：修复"判断 + 求值/求类型"复合题的答案丢失。

实证（本地 benchmark 子集 idx 38/90，及决赛 83 分评测同源病灶）：题目为
「判断 Dirichlet 函数是否可积。若可积，求积分值。」或「判断平衡点稳定性」这种
复合题时，分类器归为 `true_false`，reasoning 的 objective 两行契约只把「答案」
写成「正确」，而真正的结论（「积分值为 0」、「渐近稳定」）被塞进「依据」——
reasoning 解析把「依据」存进 `steps[].description`，`answer` 只剩「正确」，
coordinator 的 objective/deadline 路径原样输出「最终答案：正确」，丢掉判分所需
的数值/类型结论。

本模块在 coordinator 成稿前做零成本确定性兜底：当 validated 是裸判断词
（正确/错误/成立/不成立/是/否/…），且 reasoning 的结论文本里携带更具体的结论
（含数值/等式或「可积/渐近稳定」等定性词）时，用具体结论回填，并打上
`bare_verdict_enriched` 来源标记供审计。

纯判断题（答案本就是「是/否」，无额外求值）不触发：其「依据」无法提取出
携带数字/定性词的独立结论句。
"""

from __future__ import annotations

import re

#: 理由引导词：后接理由/前提从句，剥到第一个逗号（「由于…，」「根据…，」）。
#: 长词在前，避免「由」截胡「由于」、「因」截胡「因为」。
_REASON_LEAD_RE = re.compile(r"^(?:由于|根据|因为|依据|既然|由|因)\s*")

#: 结论引导词：只剥词本身，后面直接是结论（「故 X 成立」→「X 成立」）。
_VERDICT_LEAD_RE = re.compile(
    r"^(?:因此|所以|综上|故此|进而|于是|由此可知|由此可得|由此|则|故|即)\s*")

#: 中缀结论定位词：句中出现「过程…意味着/可知…结论」时，取最后一个定位词后的结论。
#: 「故/因此/所以」在中缀位置同样表示结论在后（如「实部全负，故渐近稳定」）。
_INFIX_CONCL_RE = re.compile(
    r"(?:意味着|也就是说|亦即|等价于|当且仅当|可知|可得|从而|进而|"
    r"因此|所以|综上|故)")

#: 句尾判断词：结论句尾部的「命题成立/结论正确/原判定正确/成立/…」及其前面的
#: 连接词、可选结论引导词（「，故原判定正确」「，命题成立」）。剥离后剩下
#: 具体结论本体。
_TAIL_VERDICT_RE = re.compile(
    r"(?:，|,|；|;)?\s*(?:故|因此|所以|综上)?\s*"
    r"(?:该命题|上述命题|命题|原判定|结论|该结论)?\s*"
    r"(?:不成立|不正确|成立|正确|错误|为真|为假|是对的|是错的)\s*$")

#: 具体结论必须携带的信息负载：数字/等式/公式，或定性结论词。
_PAYLOAD_RE = re.compile(
    r"\d|[=<>≤≥≈]|\\frac|\\sqrt|\\int|\\sum|\\lim|\\lambda|\\pi|π|∞|"
    r"稳定|收敛|发散|可积|积分值|独立|相关|不可约|可约|存在|唯一|"
    r"拒绝|接受|显著|极大|极小|最大|最小|有限|无穷|渐近|螺旋|焦点|节点|鞍点|"
    r"同构|单群|正规|交换|可分|完备")

#: 句边界。新行、句号、分号都算；十进制小数点不切断 `0.5`。
_SENTENCE_SPLIT_RE = re.compile(r"(?:[。；;!?！？\n]|(?<!\d)\.(?!\d))+")

_MIN_CHARS = 4
_MAX_CHARS = 150

#: 理由从句在引导词后允许的最大长度（超过则视为误匹配，保留原句）。
_MAX_LEAD_CLAUSE = 30


def _clean_conclusion(sentence: str) -> str:
    """把结论句剥离成干净结论：去理由从句、结论引导词、尾部判断词、过程前缀。"""
    s = sentence.strip().rstrip("。．. ")
    # 1. 剥理由引导从句（「由于…，」「根据…，」），可连续多层。
    for _ in range(4):
        m = _REASON_LEAD_RE.match(s)
        if not m:
            break
        rest = s[m.end():].lstrip()
        comma = rest.find("，")
        if comma < 0:
            comma = rest.find(",")
        if 0 <= comma <= _MAX_LEAD_CLAUSE:
            s = rest[comma + 1:].strip()
        else:
            break
    # 2. 剥结论引导词（只剥词本身）。
    s = _VERDICT_LEAD_RE.sub("", s).strip()
    # 3. 剥尾部判断词。
    s = _TAIL_VERDICT_RE.sub("", s).strip().rstrip("，, ")
    # 4. 中缀结论定位：去过程前缀。
    parts = _INFIX_CONCL_RE.split(s)
    if len(parts) >= 2:
        s = parts[-1].strip()
    return s


def _extract_specific_conclusion(state: dict) -> str:
    """从 reasoning 结论文本提取比裸判断词更具体的结论；失败返回 ''。

    源优先级：最后一步 `steps[].description`（reasoning 已把「依据」填入），
    其次 raw response 的「依据/理由/说明」段。取每段最后一个携带负载的句子，
    剥离后返回。
    """
    rr = state.get("reasoning_result") or {}
    candidates = []
    steps = rr.get("steps") or []
    for step in reversed(steps):
        desc = (step.get("description") or "").strip()
        if desc:
            candidates.append(desc)
            break
    raw = state.get("reasoning_raw_response") or ""
    m = re.search(r"(?:依据|理由|说明)\s*[：:]\s*(.+)", raw or "", re.S)
    if m:
        candidates.append(m.group(1).strip())

    for text in candidates:
        sentences = [s.strip() for s in _SENTENCE_SPLIT_RE.split(text) if s.strip()]
        for sentence in reversed(sentences):
            if not (_MIN_CHARS <= len(sentence) <= _MAX_CHARS):
                continue
            if not _PAYLOAD_RE.search(sentence):
                continue
            cleaned = _clean_conclusion(sentence)
            if not cleaned or len(cleaned) < _MIN_CHARS:
                continue
            return cleaned
    return ""


def enrich_bare_verdict(state: dict, validated: str) -> tuple[str, str]:
    """裸判断词 → 具体结论回填。返回 (新答案, 来源标记)；不满足时原样返回。

    `validated` 是「正确/错误/成立/不成立/是/否/对/错」等裸判断词、且能从
    reasoning 结论文本提取到携带数值/定性词的结论时才回填。提取到的结论若本身
    仍是一个裸判断词（如「结论正确」）则视为无增益，保持原答案。
    """
    from utils.verify.judge_confirm import normalize_judge_word

    if not validated or not normalize_judge_word(validated):
        return validated, ""
    conclusion = _extract_specific_conclusion(state)
    if not conclusion or normalize_judge_word(conclusion):
        return validated, ""
    return conclusion, "bare_verdict_enriched"
