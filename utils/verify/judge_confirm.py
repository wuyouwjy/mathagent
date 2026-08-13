"""判断题双向确认（VeritasMath，移植自启元 MathAgent 实证机制）。

实证根因（启元 v24.19e 监督轮次实测）：Intern-S2 对"是否/能否/对不对"判断题
存在系统性"否"偏向，**90% 判断错题同根因**——单轮答案方向不可靠。

机制（按 VeritasMath 架构重写，保持独立可测）：
1. 检出：题面含 是否/能否/对不对/吗 等，且答案是判断词；
2. 独立自证：温度 0 追加一轮"独立验证该结论"（是给 1-2 句关键理由，
   否给一个具体反例），最后单独一行 `结论:是/否`；
3. 裁决：自证与首答一致 → 采纳；反向 → 温度 0 用主提示重解一次取新判断；
4. 成本：仅 true_false 题型、预算充足时触发（~30-60s），其余零成本。

与启元实现的关键差异：复用 VeritasMath 的 chat_with_retry 预算计价与
normalize_objective_answer 归一化，不重复造客户端轮子。
"""

from __future__ import annotations

import re

from config import CONFIG
from utils.llm.retry import chat_with_retry
from utils.budget.token import estimate_tokens

#: 判断题题面信号
_JUDGE_PROBLEM_RE = re.compile(r"是否|能否|能不能|可否|对不对|对吗|是不是|判别是否")

#: 合法判断词（先长后短防"不成立"被"成立"截胡）
_JUDGE_WORDS = ("不成立", "不正确", "成立", "正确", "错误", "是", "否", "对", "错")
_POSITIVE = {"是", "正确", "成立", "对"}
_NEGATIVE = {"否", "错误", "不成立", "不正确", "错"}

_JUDGE_ANSWER_RE = re.compile(
    r"^[（(]?\s*(不成立|不正确|成立|正确|错误|是|否|对|错)\s*[)）。.．]?\s*$")

#: 调用估时（自证 ~512 token + 可能的重解 ~2048 token，温度 0）
_CONFIRM_CALL_ESTIMATE_S = 45
_RESOLVE_CALL_ESTIMATE_S = 90


def is_judge_problem(problem: str) -> bool:
    return bool(_JUDGE_PROBLEM_RE.search(str(problem or "")))


def normalize_judge_word(answer: str) -> str:
    """把答案归一到判断词；非判断词返回 ""。先剥包装再匹配。"""
    s = str(answer or "").strip()
    s = re.sub(r"^(?:最终答案|答案|结论|答)\s*[：:]\s*", "", s)
    s = s.strip().strip("$* ").rstrip("。．，,；;：:").strip()
    m = _JUDGE_ANSWER_RE.match(s)
    if not m:
        return ""
    return m.group(1)


def judge_polarity(word: str) -> str:
    """判断词 → "是"/"否" 极性；无法判定返回 ""。"""
    if word in _POSITIVE:
        return "是"
    if word in _NEGATIVE:
        return "否"
    return ""


def should_confirm(problem: str, answer: str) -> bool:
    """是否触发双向确认：判断题 + 答案是合法判断词。"""
    return is_judge_problem(problem) and bool(normalize_judge_word(answer))


def run_judge_confirmation(problem: str, answer: str, deps,
                           main_prompt_builder=None) -> dict:
    """执行双向确认。返回 {"action": "confirm"|"reverse"|"keep"|"skip",
    "final_word": 判断词, "note": str}。任何失败都保守返回 keep/keep 原答案。

    main_prompt_builder: 可选，反向时重建主提示（温度0重解）；
    缺省时反向仅采纳自证结论（自证含反例/理由，已是一次独立判断）。
    """
    word = normalize_judge_word(answer)
    polarity = judge_polarity(word)
    if not polarity:
        return {"action": "skip", "final_word": answer, "note": "非判断词"}

    clock = getattr(deps, "time_budget", None)
    margin = CONFIG.get("critic_reserve_margin_s", 60)
    if clock and clock.remaining_hard() - margin < _CONFIRM_CALL_ESTIMATE_S:
        return {"action": "skip", "final_word": word, "note": "预算不足"}

    role = "是/成立" if polarity == "是" else "否/不成立"
    ask = ("给出 1-2 句关键数学理由" if polarity == "是"
           else "给出一个具体反例或关键反证理由")
    confirm_prompt = (
        f"【题目】{problem}\n\n"
        f"前一轮求解给出的结论是：{polarity}。\n"
        f"请【独立验证】该结论是否正确（不要受前一轮结论影响）：\n"
        f"1. 若结论为{role}：{ask}；\n"
        f"2. 最后单独一行输出你的独立结论，格式：结论:是 或 结论:否"
    )
    try:
        raw = chat_with_retry(
            deps.client,
            messages=[{"role": "user", "content": confirm_prompt}],
            temperature=0.0,
            max_tokens=512,
            logger=deps.logger,
            time_budget=clock,
            expected_call_seconds=_CONFIRM_CALL_ESTIMATE_S,
            label="judge_confirm",
        )
    except Exception as exc:  # noqa: BLE001 - 确认失败保守保留原答案
        deps.logger.warning("Judge confirm call failed: %s", exc)
        return {"action": "keep", "final_word": word, "note": "确认调用失败"}
    if deps.token_budget:
        deps.token_budget.consume(estimate_tokens(confirm_prompt), estimate_tokens(raw))

    m = re.search(r"结论\s*[:：]\s*(不成立|不正确|成立|正确|错误|是|否|对|错)",
                  str(raw or ""))
    confirm_polarity = judge_polarity(m.group(1)) if m else ""
    if not confirm_polarity:
        return {"action": "keep", "final_word": word, "note": "自证未产出判断词"}

    if confirm_polarity == polarity:
        return {"action": "confirm", "final_word": word,
                "note": f"确认轮一致（{polarity}），采纳"}

    # 反向：自证与首答冲突。用主提示温度 0 重解一次（独立性最强的第三票）。
    if main_prompt_builder is not None and clock and \
            clock.remaining_hard() - margin >= _RESOLVE_CALL_ESTIMATE_S:
        try:
            re_prompt = main_prompt_builder()
            raw2 = chat_with_retry(
                deps.client,
                messages=[{"role": "user", "content": re_prompt}],
                temperature=0.0,
                max_tokens=2048,
                logger=deps.logger,
                time_budget=clock,
                expected_call_seconds=_RESOLVE_CALL_ESTIMATE_S,
                label="judge_resolve",
            )
            re_word = normalize_judge_word(str(raw2 or ""))
            if re_word:
                return {"action": "reverse",
                        "final_word": re_word,
                        "note": f"确认轮反向（{polarity}→{confirm_polarity}），温度0重解判定"}
        except Exception as exc:  # noqa: BLE001
            deps.logger.warning("Judge resolve call failed: %s", exc)
    # 重解不可用：采纳自证结论（它附带了反例/理由，是独立判断）
    new_word = "是" if confirm_polarity == "是" else "否"
    return {"action": "reverse", "final_word": new_word,
            "note": f"确认轮反向（{polarity}→{confirm_polarity}），采纳自证"}
