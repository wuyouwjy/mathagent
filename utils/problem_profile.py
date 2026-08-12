"""题型画像与客观题快速路径。

题面通常不会显式携带 ``type`` 字段，且官方题集同时包含证明、计算、选择、
判断和填空。把题型识别放在一个小的、无副作用的模块里，避免每个节点各自用
不一致的关键词判断，尤其避免把“判断题”误当成证明题。
"""

from __future__ import annotations

import re
from typing import Any, Mapping


QUESTION_MODES = frozenset({"proof", "computation", "choice", "true_false", "fill"})
OBJECTIVE_MODES = frozenset({"choice", "true_false", "fill"})

_TYPE_TO_MODE = {
    "计算": "computation", "计算题": "computation", "computation": "computation",
    "proof": "proof", "证明": "proof", "证明题": "proof",
    "choice": "choice", "选择": "choice", "选择题": "choice", "单选": "choice", "多选": "choice",
    "fill": "fill", "填空": "fill", "填空题": "fill",
    "true_false": "true_false", "判断": "true_false", "判断题": "true_false",
}

# Option markers occur both at line starts and inline in the official JSONL set.
_OPTION_RE = re.compile(r"(?<![A-Za-z0-9])[A-EＡ-Ｅ]\s*[.．、:：)）]")
_OPTION_PAREN_RE = re.compile(r"(?<![A-Za-z0-9])[（(]\s*[A-EＡ-Ｅ]\s*[）)]")
_TRUE_FALSE_RE = re.compile(
    r"(?:^|[\n。；;])\s*(?:判断|正误|对错)\s*(?:题)?\s*[:：]?|"
    r"(?:判断题|正误题|对错题|正确与否|命题是否正确|说法是否正确|"
    r"(?:判断|判定)(?:下列|该|此)?(?:命题|说法|结论))",
    re.I,
)
_FILL_RE = re.compile(
    r"填空|填“|填\"|填入|_{3,}|＿{2,}|[(（]\s*(?:\\\s*)?[)）]"
)
_PROOF_RE = re.compile(
    r"(?:^|[\n])\s*(?:证明|试证)|(?:^|[\n])\s*(?:prove|show)\b|"
    r"证明题|(?<!or )\b(?:prove|show|demonstrate|establish|justify)\s+that\b|"
    r"\b(?:prove|show|demonstrate|establish|justify)\b",
    re.I,
)


def mode_from_metadata(metadata: Mapping[str, Any] | None) -> str:
    """Read an evaluator-provided type without making it a runtime dependency.

    The public competition input normally contains only ``problem`` and ``idx``.
    Some harnesses also provide ``type``/``question_mode``; honoring those fields
    removes avoidable ambiguity while the text-only path remains unchanged.
    """
    if not isinstance(metadata, Mapping):
        return ""
    for key in ("question_mode", "type", "question_type", "problem_type"):
        value = str(metadata.get(key, "") or "").strip().lower()
        if value in QUESTION_MODES:
            return value
        if value in _TYPE_TO_MODE:
            return _TYPE_TO_MODE[value]
    return ""


def classify_question_mode(problem: str) -> str:
    """Return one stable mode name from raw problem text.

    Objective markers are checked before proof words: a multiple-choice stem may
    contain “判断下列命题” but should still use the short objective path.
    """

    text = str(problem or "").strip()
    if not text:
        return "computation"
    if _TRUE_FALSE_RE.search(text) or re.search(r"判断\s*(?:题)?\s*[：:]", text):
        return "true_false"
    # Official questions often use ``（）`` after the stem and place options
    # inline (``A.均值B.方差``).  Option detection must therefore precede the
    # generic blank marker; otherwise almost every objective item becomes fill-in.
    option_count = len(_OPTION_RE.findall(text)) + len(_OPTION_PAREN_RE.findall(text))
    if option_count >= 2 or re.search(r"(?:选择题|单选|多选|下列.*(?:正确|错误|是|为).*选)", text, re.I):
        return "choice"
    if _FILL_RE.search(text) or re.search(
        r"(?:填空题|fill\s*in|blank|指标是|分别为\s*$)", text, re.I
    ):
        return "fill"
    if _PROOF_RE.search(text):
        return "proof"
    return "computation"


def is_objective_mode(mode: str) -> bool:
    return mode in OBJECTIVE_MODES


# ---- 题面结构探测（评委建议 6/7/8） ----

_BLANK_MARK_RE = re.compile(r"_{3,}|＿{2,}|—{3,}|[（(]\s*(?:\\\s*)?[）)]")

#: "求所有/找出全部" 型题：解空间可能含多个分支，单一构造不可作答。
_ALL_SOLUTIONS_RE = re.compile(
    r"(?i)find\s+all|determine\s+all|all\s+possible|every\s+possible|"
    r"所有可能|全部(?:的)?(?:解|值|情况|可能)|求所有|找出所有|确定所有|哪些"
)

#: 极值/最优题：需要构造与上/下界双向闭环，且构造须与竞争构造比较。
_EXTREMAL_RE = re.compile(
    r"(?i)最大|最小|最多|最少|至多|至少|最优|最短|最长|极值|"
    r"\b(?:maximum|minimum|maximal|minimal|largest|smallest|greatest|least|"
    r"at\s+most|at\s+least|optimal)\b"
)

#: 值域为二元域/模 m 结构的函数声明（f: Q → F_2 等）。
_MOD_CODOMAIN_RE = re.compile(
    r"(?:\\rightarrow|\\to|→|->)\s*\\?(?:mathbb\s*\{?\s*F\s*\}?_\{?2\}?|F_?2\b|"
    r"GF\(2\)|\\?mathbb\s*\{?\s*Z\s*\}?\s*/\s*2)"
)

#: 同名函数值相加（f(a)+f(b)）——和落在函数值域所在的代数结构里。
_FUNC_SUM_RE = re.compile(r"([a-zA-Z])\s*\([^()]{1,60}\)\s*\+\s*\1\s*\(")

#: 开区间/严格不等式限定的取值范围。"between a and b" 是竞赛惯用的开区间表述；
#: 由 ≤ 推出的界在严格范围内取不到，临界值必须逐一核验可达性。
_OPEN_BOUND_RE = re.compile(
    r"(?i)\bbetween\b[^,.;]{1,40}\band\b|strictly\s+(?:between|less|greater)|"
    r"开区间|严格(?:小于|大于|介于|单调)|"
    # |x| < 1 型严格不等式（排除 ≤/\le/\leq）
    r"(?<![\\])<(?!=)"
)

#: "第 k 大/第 k 小/第 k 个" 型序号问法：通项与序号极易差一。
#: 序数词与数字之间常隔着 LaTeX 包裹（``$9$th``、``{10}th``），必须允许。
_ORDINAL_RANK_RE = re.compile(
    r"(?i)\b\d+\s*[$}\s]*(?:st|nd|rd|th)\b[^.\n]{0,40}"
    r"\b(?:largest|smallest|greatest|least|biggest|term|element|number|value)\b|"
    r"第\s*\$?\s*[0-9一二三四五六七八九十k]+\s*\$?\s*(?:大|小|个|项|位)"
)

#: 可行性 + 计数的双问项（"是否可能…若可能，最少需要多少"）。
_FEASIBILITY_RE = re.compile(
    r"(?i)\bis it possible\b|\bcan (?:we|you|one|it)\b|\bdoes there exist\b|"
    r"是否(?:可能|存在|能)|能否|可否"
)
_COUNT_ASK_RE = re.compile(
    r"(?i)\b(?:minimum|maximum|smallest|largest|fewest|greatest)\s+number\b|"
    r"\bhow many\b|最少(?:需要)?(?:多少|几)|最多(?:能|可以)?(?:多少|几)|"
    r"需要多少|数量是多少"
)


def has_open_interval_bound(problem: str) -> bool:
    """题面用开区间/严格不等式限定取值（端点不可达，临界值需 +1 核验）。"""
    return bool(_OPEN_BOUND_RE.search(str(problem or "")))


def asks_ordinal_rank(problem: str) -> bool:
    """题面问"第 k 大/小/个"（序号与通项必须逐项对齐核验）。"""
    return bool(_ORDINAL_RANK_RE.search(str(problem or "")))


def asks_feasibility_then_count(problem: str) -> bool:
    """题面同时问"是否可能"与"最少/最多需要多少"（不可能性论证须先证伪）。"""
    text = str(problem or "")
    return bool(_FEASIBILITY_RE.search(text)) and bool(_COUNT_ASK_RE.search(text))


def count_blanks(problem: str) -> int:
    """题面可见空位数（填空题输出契约用）。检测不到显式空位记号时返回 0。

    评委报告 idx 86：三空只答零空、置信 0.78 直接放行——缺的就是这个计数。
    """
    return len(_BLANK_MARK_RE.findall(str(problem or "")))


def fill_part_count(answer: str) -> int:
    """填空答案里的分项数（按分号切分）。"""
    text = str(answer or "").strip()
    if not text:
        return 0
    return len([part for part in re.split(r"[；;]", text) if part.strip()])


def requires_all_solutions(problem: str) -> bool:
    """题面是否要求"所有解/全部值"（须触发解空间枚举，不得单支作答）。"""
    return bool(_ALL_SOLUTIONS_RE.search(str(problem or "")))


def is_extremal_problem(problem: str) -> bool:
    """题面是否为极值/最优化问题（构造须与竞争构造对照，防自洽陷阱）。"""
    return bool(_EXTREMAL_RE.search(str(problem or "")))


def has_mod2_valued_sum(problem: str) -> bool:
    """函数值域为 F₂/模 2 且所求为函数值之和（和必须在该结构内聚合）。

    评委报告 idx 7：六个 f 值全对，最后按整数相加得 3；题面 f:Q→F₂，
    和应在 F₂ 中为 1。通用口径清单不足以扭转，这里做题面条件触发的定向注入。
    """
    text = str(problem or "")
    return bool(_MOD_CODOMAIN_RE.search(text)) and bool(_FUNC_SUM_RE.search(text))


def mode_instruction(mode: str) -> str:
    """Prompt suffix shared by reasoning/Python nodes.

    The instruction deliberately asks for the exact deliverable, not a guessed
    answer. It keeps objective questions concise while preserving the full
    four-section contract for the parser.
    """

    if mode == "choice":
        return (
            "\n\n[题型画像：选择题快速路径]\n"
            "先判断单选还是多选：题面注明'多选/不定项'或多个选项各自独立成立时按多选，"
            "否则倾向单选。逐项按教材定义的**严格措辞**核对：概念被替换、方向说反、"
            "表述不精确的选项一律不选，宁缺勿滥。最后在'最终答案'中明确写出全部正确选项"
            "（如 A、C），不要把选项说明误当成答案。最多 3 个短步骤。"
        )
    if mode == "true_false":
        return (
            "\n\n[题型画像：判断题快速路径]\n"
            "先给出‘正确’或‘错误/不正确’，再用一个反例或定理说明理由；不要把条件句当作最终判断。"
        )
    if mode == "fill":
        return (
            "\n\n[题型画像：填空题快速路径]\n"
            "按空位顺序逐项作答，答案行格式：空1: <结果>；空2: <结果>（只有一个空时直接给结果）。"
            "每个空必须填教材术语/具体数值/明确方向（如'有偏''低估或高估'），"
            "禁止填'不确定/视情况而定'；不要输出空位数量本身或任何操作说明，"
            "不要把一个空的同义解释拆成多个空，不输出与空位无关的长篇探索。"
        )
    if mode == "proof":
        return (
            "\n\n[题型画像：证明题]\n"
            "必须写出从假设到结论的关键蕴含链，至少列出两步，并检查边界条件/等号条件。"
        )
    return (
        "\n\n[题型画像：计算题]\n"
        "先列出题面要求的全部量，再计算并在最终答案中逐项标注；不要用一个中间量代替最终结论。"
        "若题目要求‘所有/确定集合/轨迹/最小或最大常数’，必须同时给出候选的必要性与充分性（或上界与构造）"
        "并核对边界，不能只报一个猜测值。"
    )


def structure_instruction(problem: str) -> str:
    """按题面结构追加的强制步骤（评委建议 6/7），推理与 Python 分支共用。

    与 mode_instruction 互补：mode 看题型，这里看题面语义（全部解/极值）。
    检测不到相应结构时返回 ""，不增加提示词负担。
    """
    parts: list[str] = []
    if has_mod2_valued_sum(problem):
        parts.append(
            "[值域聚合警告] 题面函数的值域是 F_2（模 2 的二元域）。所求的 f(⋯)+f(⋯)+… 是"
            " **F_2 中的加法**：先逐项求出各函数值（0 或 1），最后必须按模 2（异或）聚合，"
            "最终答案只能是 0 或 1；给出普通整数和（如 3）即错。"
        )
    if requires_all_solutions(problem):
        parts.append(
            "[全部解检查单] 本题要求给出**所有**解/值。禁止只验证一个已知解就作答："
            "必须先在小规模/截断版本上系统枚举解空间（列出发现的每一个解支），"
            "再证明再无其他分支；最终答案必须列出全部解支（含平凡支与例外支）。"
        )
    if is_extremal_problem(problem):
        parts.append(
            "[极值题对照检查] 本题求极值/最优。单一构造族内的自洽验证不构成最优性证明："
            "必须 (1) 用小规模精确解（暴力/DP）校准；(2) 至少比较两个结构不同的构造，"
            "取更优者；(3) 给出与构造值匹配的上界/下界论证。三者缺一即在验证点中声明未完成。"
        )
    # 以下三条针对 2026-08-10 复测轮的错因（评委建议 1/2/3/5）：口径与序号类错误
    # 都发生在"推理跑完了"之后，属于收尾核验缺失，成本极低但直接决定得分。
    if has_open_interval_bound(problem) and is_extremal_problem(problem):
        parts.append(
            "[端点可达性检查] 题面用开区间/严格不等式限定取值（如 between a and b、"
            "|S|<1）。由非严格不等式（≤）推出的界在严格范围内**取不到**："
            "推出 n ≥ K 之后必须对 n=K 显式写出**全部变量的具体数值或构造式**，"
            "并把它们逐条代回原式检验每一个等式与每一个严格不等号；"
            "禁止用“可以构造”“取 n=K 即可”一类断言代替检验。"
            "若检验发现只有让某个变量取到端点（或让某个严格不等式取等）才能成立，"
            "则 n=K 不可行，答案是 K+1，并在验证点中写出使等号无法成立的那一步。"
        )
    if asks_ordinal_rank(problem):
        parts.append(
            "[序号对齐检查] 本题问“第 k 大/第 k 小/第 k 个”。禁止直接写通项作答："
            "必须先显式列出 k=1、2、3 对应的前三个对象（写出具体表达式或数值），"
            "确认序号从 1 起数且与通项逐项对齐，再代入题面的 k；"
            "最终答案与该列表必须自洽（差一即错）。"
        )
    if asks_feasibility_then_count(problem):
        parts.append(
            "[不可能性论证的证伪要求] 本题先问可行性、再问所需数量。"
            "断言“不可能/不存在”之前必须完成两项证伪：(1) 在缩小规模的同类实例上"
            "（如把边长换成 3、5、7）实际构造或暴力搜索，只要小规模可行，"
            "不可能性论证即有误；(2) 复核不变量论证的每一步——同一形状/操作在染色或"
            "计数下的贡献若不唯一（例如一块拼图可覆盖 2 黑 1 白，也可覆盖 1 黑 2 白），"
            "总量整除性就**不构成**不可能性证明。若可行，最终答案必须给出具体数量，"
            "不得只回答“可能/不可能”。"
        )
    if not parts:
        return ""
    return "\n\n" + "\n".join(parts)


def answer_coverage_clause(problem: str) -> str:
    """压缩重试专用：必须保全的**答案覆盖度**（不是推导篇幅）。

    2026-08-10 复测轮 idx 14：截断后压缩重试的指令写着"沿最可行的一条路线、
    每章从简"，模型据此只报了三个可能值中的一个。压缩针对的是推导过程，
    答案该覆盖的分支一个都不能少——这句提醒随压缩指令一起发出。
    """
    clauses = []
    if requires_all_solutions(problem):
        clauses.append(
            "题目要求“所有可能的值/全部解”：压缩的是推导篇幅，不是解的个数——"
            "'## 最终答案' 必须把每一个解支都列出来（写成集合），"
            "只报一支按缺解计零分"
        )
    if asks_feasibility_then_count(problem):
        clauses.append("题目同时问可行性与数量：最终答案必须给出具体数量，不能只答可能/不可能")
    if is_multi_ask(problem):
        clauses.append("题目含多个问项：每一问都要在最终答案中单独给出结果")
    if not clauses:
        return ""
    return "\n**答案覆盖度要求（不受“从简”约束）**：" + "；".join(clauses) + "。"


def is_multi_ask(problem: str) -> bool:
    """题面是否有多个并列问项（复用答案抽取侧的多问项判定）。"""
    from utils.answer_extractor import is_multi_part_problem

    return is_multi_part_problem(problem)


_FULLWIDTH_TRANSLATION = str.maketrans("ＡＢＣＤＥａｂｃｄｅ", "ABCDEabcde")


def _strip_answer_wrappers(answer: str) -> str:
    text = str(answer or "").strip()
    # Prefer the last explicit label.  A response can quote an intermediate
    # ``答案：...`` and then commit to a second one; taking the last label avoids
    # treating the rationale as the submitted payload.
    labelled = list(re.finditer(
        r"(?:最终答案|答案|结论|选择)\s*[：:]\s*([^\n]+)", text, flags=re.I
    ))
    if labelled:
        text = labelled[-1].group(1).strip()
    else:
        text = re.sub(r"^\s*(?:最终答案|答案|结论|选择)\s*[：:]\s*", "", text, flags=re.I)
    # Keep the last boxed expression: an objective response may quote an option
    # in its rationale before committing to the answer line.
    boxed = re.findall(r"\\boxed\s*\{([^{}]*)\}", text, flags=re.S)
    if boxed:
        text = boxed[-1].strip()
    # The concise objective contract puts the evidence after a semicolon or a
    # dedicated ``依据/理由`` label.  Drop that suffix for choices/judgements;
    # fill answers keep internal semicolons because they can denote multiple blanks.
    text = re.split(r"(?:\n|[；;])\s*(?:依据|理由|说明)\s*[：:]", text, maxsplit=1)[0]
    return text.strip().strip("。．.;；\"'“”")


def normalize_objective_answer(answer: str, mode: str) -> str:
    """Canonicalize a short choice/judgement/fill answer without solving it.

    This is intentionally a formatting operation.  It removes wrappers and,
    for choices, retains option letters in their appearance order; it never
    derives a missing option from the explanation.
    """
    text = _strip_answer_wrappers(answer)
    if not text:
        return ""
    if mode == "choice":
        text = text.translate(_FULLWIDTH_TRANSLATION)
        # 连写形态（"BD"、"\boxed{BD}" 剥壳后）：字母间无分隔符时逐字母展开。
        # 单词边界正则对连写必然失配（B 的后瞻撞上 D），评委报告 idx 87 的
        # \boxed{BD} 曾因此归一化为空。仅限 2-5 个纯 A-E 字母的短串，避免把
        # 普通英文单词错当选项串。
        if re.fullmatch(r"[A-E](?:\s*[A-E]){1,4}", text, flags=re.I):
            letters = re.findall(r"[A-E]", text, flags=re.I)
        else:
            letters = re.findall(r"(?<![A-Za-z0-9])[A-E](?![A-Za-z0-9])", text, flags=re.I)
        ordered = []
        for letter in letters:
            upper = letter.upper()
            if upper not in ordered:
                ordered.append(upper)
        return "、".join(ordered)
    if mode == "true_false":
        # Prefer the two-character negative phrase before the bare ``正确``.
        matches = list(re.finditer(r"不正确|错误|正确|不对|对|错|×|√", text, flags=re.I))
        if not matches:
            return ""
        # The first judgement token is the answer; later occurrences usually
        # belong to the explanatory sentence (e.g. ``错误，因为...正确``).
        value = matches[0].group(0)
        return "正确" if value in {"正确", "对", "√"} else "错误"
    return text


def objective_answer_is_usable(answer: str, mode: str) -> bool:
    normalized = normalize_objective_answer(answer, mode)
    if not normalized:
        return False
    if mode == "choice":
        return bool(re.fullmatch(r"[A-E](?:、[A-E])*", normalized))
    if mode == "true_false":
        return normalized in {"正确", "错误"}
    if mode == "fill":
        # A section-less long CoT can be mistaken for a fill answer by the prose
        # salvage fallback (e.g. an English sentence ending in a formula).  Reject
        # obvious narrative so the bounded prefilled retry gets a chance to emit
        # the requested blank payload.  Mathematical expressions and multi-blank
        # textbook phrases remain allowed.
        from utils.answer_cleanliness import is_noise_answer
        from utils.answer_extractor import looks_incomplete_answer

        if looks_incomplete_answer(normalized):
            return False
        # 元指令回显 / 思维碎片（评委报告 idx 105 "Count blanks: 1"）与
        # 非答案术语（idx 108 "不确定"）都不是可提交的填空内容。
        if is_noise_answer(normalized):
            return False
        if re.fullmatch(r"不确定|不一定|视情况(?:而定)?|无法判断", normalized):
            return False
        # 带"空N:"前缀的不确定类回答（2026-08-09 冒烟回归 idx 108："空1: 不确定"）：
        # 逐空剥掉前缀后检查；全部空位都是不承诺答案时整体拒收，混合时保留部分得分。
        parts = [re.sub(r"^\s*空\s*\d+\s*[:：]\s*", "", part).strip()
                 for part in re.split(r"[；;]", normalized)]
        parts = [part for part in parts if part]
        if parts and all(
            re.fullmatch(r"不确定|不一定|视情况(?:而定)?|无法判断|无法确定|不能确定", part)
            for part in parts
        ):
            return False
        # 填空答案是术语/数值/短表达式；成段英文散句只可能是泄漏的思考文本
        # （2026-08-09 冒烟回归：idx 108 的答题纠结独白曾以 fill 答案形态出厂）。
        # LaTeX 表达式的词数远低于此阈值（\frac/\partial 等 2-3 词）。
        if len(re.findall(r"[A-Za-z]{2,}", normalized)) > 6:
            return False
        if len(normalized) > 420 or "\n" in normalized or "?" in normalized or "？" in normalized:
            return False
        if re.search(
            r"\b(?:let's|consider|under|because|therefore|we need|the phrase|actually|however)\b"
            r"|(?:如果|是否|请判断|请问|无法确定|不能确定)[^；;。]*[？?]?$",
            normalized,
            flags=re.I,
        ):
            return False
    return not re.fullmatch(r"(?:答案|结果|待求|无法确定|不能确定)(?:[：:].*)?", normalized)


def fill_answer_matches_blanks(answer: str, problem: str) -> bool:
    """填空答案的分项数是否覆盖题面的全部空位（空位 ≤1 时恒真）。

    评委建议 8：填空题必须"校验空数一致"。检测不到显式空位记号时不设限，
    以免误伤没有下划线记号的填空题。
    """
    blanks = count_blanks(problem)
    if blanks <= 1:
        return True
    return fill_part_count(answer) >= blanks
