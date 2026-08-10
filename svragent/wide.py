# -*- coding: utf-8 -*-
"""Production solver: four blind routes, wall-gated review, deterministic selection.

Answer tasks launch four independent blind routes (A standard / D solve-then-check
/ L logic-scope / X bounded-exact-kernel) in one parallel wave.  When at least
two independent routes declare semantically equivalent answers, the solver stops
immediately and submits the most complete body from that consensus cluster —
no second stage.  When the routes disagree, a single wall-gated review call
checks the candidate answers against the problem.

Proof tasks launch four blind proof routes (direct / contradiction / induction /
extremal) and submit the first complete proof by preregistered order.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .config import DEFAULT_REASONING_TOKEN_CEILING
from .parser import AnswerExtractor, answers_equal


_PROBLEM_CLIP = 8000
_TERMINAL_RE = re.compile(r"[。．.!?！？)\]}>」』]\s*$")
_QED_RE = re.compile(r"(?:QED|证毕|∎|□)[.．。!！]?\s*$", re.IGNORECASE)

# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------
SOLVE_SYSTEM = """\
你是数学专家,正在参加高水平数学解题评测。

要求:
1. 不复述题目,直接给出简洁但完整的解答;只写真正使用的定义、定理前提与关键推导。
2. 不添加与结论无关的背景、直觉比较或额外断言;承重步骤不能用"显然"跳过。
3. 结论必须明确、可独立判分;若题面确有编号小问,逐问作答并保留编号。
4. 正文写完后,最后一行单独写:
   FINAL: <最终答案>
   多问写成 `FINAL: (1) <第一问答案>; (2) <第二问答案>; ...`
   答案是表达式、集合、名称或判断时就直接写它,不要强行换算成一个数字。
5. 只依据原题独立求解:不得依据选项分布、措辞模式或"看起来像"来猜答案;
   核心步骤尚未完成时,不得声称已完成计算、枚举或证明。
6. 解答末尾另起一行写 `CONFIDENCE: <0-1 的置信度>`,例如 CONFIDENCE: 0.8。
"""

PROOF_SYSTEM = """\
你是数学证明写作专家,正在参加高水平数学评测。

要求:
1. 写出可以被逐行检查的完整严格证明:写全假设与量词范围,每一步给出依据,
   引用定理时写明名称并核对其全部前提,分情况讨论必须穷尽。
2. 不要写元分析、计划清单或思考过程,直接写证明正文。
3. 证明结尾单独一行写 `结论: <被证明的命题(如需数值,一并给出)>`,再单独一行写 `QED`。
"""

# Four production answer routes
SOLVE_STANCES: Tuple[Tuple[str, str], ...] = (
    ("A", "用最标准、最稳妥的路线独立求解,保留支撑最终结论的关键步骤。"),
    ("D", "独立求解并用代回原条件、边界或等价计算复核最终答案;冲突时重算。"),
    ("L", "独立求解时只挑出最多两个真正承重的逻辑跳跃;区分充分、必要与等价,"
          "核对关键定理的前提,并尝试最有判别力的边界、退化情形或反例。"),
    ("X", "判断答案是否取决于一个有限且可执行的计算核;若存在,只选择其中一个最小"
          "决定性核并实际执行,例如离散转移、有限枚举、若干步递推、指定系数展开、"
          "精确积分代入或带保护位的数值计算。若不存在,不得强行制造计算任务;"
          "完成该核后用正常方法解决其余部分。"),
)

# Four production proof routes
PROOF_STANCES: Tuple[Tuple[str, str], ...] = (
    ("direct", "从定义、已知条件与可明确陈述前提的标准定理出发,建立一条最短的正向推导链。"),
    ("contradiction", "优先检查反证、逆否、最小反例或不变量能否形成独立于直接路线的证明。"),
    ("induction", "优先考虑数学归纳/结构归纳/强归纳,明确写清奠基步、归纳假设与递推步。"),
    ("extremal", "优先考虑极值原理、最小反例/最大元素、不等式链或单调性论证,"
                 "构造独立于其他路线的证明。"),
)

_SOLVE_USER_TEMPLATE = """\
解题姿态:{instruction}

题目:
{problem}

请写出完整解答,最后一行写 `FINAL: <最终答案>`。
"""

_PROOF_USER_TEMPLATE = """\
本次独立证明路线:{instruction}
请给出下述命题的完整严格证明。

题目:
{problem}

直接写证明正文;结尾单独一行写 `结论: ...`,再一行 `QED`。
"""

_ANSWER_TEMPERATURES = (0.2, 0.5, 0.3, 0.3)
_PROOF_TEMPERATURES = (0.2, 0.55, 0.35, 0.35)


# ---------------------------------------------------------------------------
# Review phase
# ---------------------------------------------------------------------------
REVIEW_SYSTEM = """\
你是数学复核员,负责在多个候选答案之间做独立复核。

给定原题与候选答案列表(来自不同求解路线,编号 1..N):
1. 对每个候选,独立核对它是否真正回答了题目要求:关键推导、代入原条件、
   量词与定义域、精度与格式。
2. 不能因为某个候选"看起来更合理"就放行;没有实际核对依据就写 FAIL。
3. 输出格式(每个候选都要写):
   CANDIDATE <n>: <该候选的答案>
   CHECK <n>: <具体复核,必须包含实际代入/计算/核对,不得照抄模板>
   VERDICT <n>: PASS 或 FAIL
4. 最后一行单独写 FINAL: <判定正确的候选编号>;若都无法确认,写 FINAL: NONE
"""

_REVIEW_USER_TEMPLATE = """\
题目:
{problem}

候选答案:
{candidates}

请按复核格式输出。
"""

_REVIEW_VERDICT_RE = re.compile(
    r"VERDICT\s*(\d+)\s*[:：]\s*(PASS|FAIL)", re.IGNORECASE)
_REVIEW_CHECK_RE = re.compile(
    r"CHECK\s*(\d+)\s*[:：]\s*(.+?)(?=\n\s*(?:CANDIDATE|CHECK|VERDICT|FINAL)|$)",
    re.IGNORECASE | re.DOTALL)
_REVIEW_FINAL_RE = re.compile(
    r"FINAL\s*[:：]\s*(NONE|\d+)\s*$", re.IGNORECASE | re.MULTILINE)
_REVIEW_TEMPLATE_ECHO_RE = re.compile(
    r"VERDICT\s*[:：]\s*PASS\s+or\s+FAIL", re.IGNORECASE)
_REVIEW_MAX_CANDIDATES = 3
_REVIEW_CANDIDATE_CLIP = 200


def _review_candidates(clusters: List["Cluster"]) -> List[Dict[str, Any]]:
    """Return up to three candidate surfaces, ordered by votes then route order."""
    order = {route: index for index, (route, _) in enumerate(SOLVE_STANCES)}
    ordered = sorted(
        clusters,
        key=lambda cluster: (-cluster.votes, min(
            (order.get(sample.route_id, 99) for sample in cluster.samples),
            default=99)),
    )
    picked: List[Dict[str, Any]] = []
    for cluster in ordered[:_REVIEW_MAX_CANDIDATES]:
        best = cluster.best()
        surface = str(best.answer_surface or cluster.answer or "").strip()
        if not surface:
            continue
        picked.append({
            "answer": surface[:_REVIEW_CANDIDATE_CLIP],
            "samples": [sample for sample in cluster.samples],
        })
    return picked


def _review_is_substantive_check(text: str) -> bool:
    """A CHECK line only counts when it carries actual math content."""
    body = str(text or "").strip()
    if len(body) < 25:
        return False
    if re.search(
        r"必须包含实际代入|不得照抄模板|候选答案|请按复核格式",
        body, re.IGNORECASE,
    ):
        return False
    return bool(re.search(r"[0-9]|[=<>≤≥∈=]|\\[A-Za-z]+", body))


def parse_review(text: str) -> Optional[Dict[str, Any]]:
    """Strictly parse a review response into a decision.

    Returns None on any ambiguity (template echo, missing checks, multiple PASS,
    FINAL disagreement). Template recitation must never produce a decision.
    """
    raw = str(text or "").strip()
    if not raw:
        return None
    if _REVIEW_TEMPLATE_ECHO_RE.search(raw):
        return None
    try:
        verdicts = {
            int(m.group(1)): str(m.group(2)).upper()
            for m in _REVIEW_VERDICT_RE.finditer(raw)
        }
        checks = {
            int(m.group(1)): str(m.group(2)).strip()
            for m in _REVIEW_CHECK_RE.finditer(raw)
        }
    except Exception:
        return None
    if not verdicts:
        return None
    if not any(_review_is_substantive_check(text) for text in checks.values()):
        return None
    passed = [n for n, verdict in verdicts.items() if verdict == "PASS"]
    failed = [n for n, verdict in verdicts.items() if verdict == "FAIL"]
    if not failed or len(passed) != 1:
        return None
    chosen = passed[0]
    final_match = _REVIEW_FINAL_RE.search(raw)
    if final_match:
        declared = final_match.group(1).upper()
        if declared != "NONE" and int(declared) != chosen:
            return None
    return {
        "chosen": chosen,
        "passed": passed,
        "failed": failed,
        "verdicts": verdicts,
        "checks": {n: checks.get(n, "") for n in verdicts},
    }


def _prompt_hash(system: str, template: str, instruction: str) -> str:
    payload = system + "\n" + template.format(
        instruction=instruction, problem="{problem}")
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def production_profile_manifest(config: Any) -> Dict[str, Any]:
    """Describe the exact production behavior without item-specific data."""
    answer_routes = [
        {
            "route_id": route,
            "route_family": "blind_answer",
            "source_group": route,
            "temperature": _ANSWER_TEMPERATURES[index],
            "prompt_hash": _prompt_hash(SOLVE_SYSTEM, _SOLVE_USER_TEMPLATE, instruction),
        }
        for index, (route, instruction) in enumerate(SOLVE_STANCES)
    ]
    proof_routes = [
        {
            "route_id": route,
            "route_family": "blind_proof",
            "source_group": route,
            "temperature": _PROOF_TEMPERATURES[index],
            "prompt_hash": _prompt_hash(PROOF_SYSTEM, _PROOF_USER_TEMPLATE, instruction),
        }
        for index, (route, instruction) in enumerate(PROOF_STANCES)
    ]
    return {
        "profile": "submission_v2_quad_review",
        "answer": {
            "routes": answer_routes,
            "parallel_at_start": True,
            "max_tokens": DEFAULT_REASONING_TOKEN_CEILING,
            "selection": "consensus_else_review_else_preregistered",
            "review": {
                "enabled": bool(getattr(config, "enable_review", True)),
                "min_remaining_s": float(getattr(config, "review_min_remaining_s", 360.0)),
                "max_tokens": int(getattr(config, "review_max_tokens", 8192)),
            },
        },
        "proof": {
            "routes": proof_routes,
            "parallel_at_start": True,
            "max_tokens": DEFAULT_REASONING_TOKEN_CEILING,
            "selection": "first_complete_preregistered_route",
        },
        "second_stage": "conditional_review_answer_only",
        "dynamic_token_reduction": False,
        "wall_clock_s": float(getattr(config, "wall_clock_s", 1140.0)),
    }


def production_config_hash(config: Any) -> str:
    payload = json.dumps(
        production_profile_manifest(config), ensure_ascii=False,
        sort_keys=True, separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------
@dataclass
class Sample:
    """One independent full-solution call."""

    route_id: str
    route_family: str
    text: str = ""
    answer: str = ""
    answer_surface: str = ""
    explicit_final: bool = False
    truncated: bool = False
    duration_s: float = 0.0
    max_tokens: int = 0
    transport_status: str = "unknown"
    tool_usage: List[str] = field(default_factory=list)
    tool_errors: int = 0
    confidence: float = 0.5

    @property
    def source_group(self) -> str:
        return self.route_id

    @property
    def usable(self) -> bool:
        return bool(str(self.text or "").strip())

    def record(self) -> Dict[str, Any]:
        return {
            "route_id": self.route_id,
            "route_family": self.route_family,
            "source_group": self.source_group,
            "blind": True,
            "derived_from": None,
            "answer": self.answer,
            "answer_surface_chars": len(self.answer_surface or ""),
            "explicit_final": self.explicit_final,
            "chars": len(self.text or ""),
            "truncated": self.truncated,
            "transport_status": self.transport_status,
            "duration_s": round(self.duration_s, 1),
            "max_tokens": self.max_tokens,
        }


@dataclass
class Cluster:
    answer: str
    samples: List[Sample] = field(default_factory=list)

    @property
    def votes(self) -> int:
        return len({sample.source_group for sample in self.samples})

    def best(self) -> Sample:
        """Choose completeness only among semantically equivalent answers."""
        return max(
            self.samples,
            key=lambda sample: (
                not sample.truncated,
                sample.explicit_final,
                len(sample.text or ""),
            ),
        )

    def record(self) -> Dict[str, Any]:
        return {
            "answer": self.answer,
            "votes": self.votes,
            "source_groups": [sample.source_group for sample in self.samples],
        }


# ---------------------------------------------------------------------------
# WidePipeline
# ---------------------------------------------------------------------------
class WidePipeline:
    """Four parallel blind routes, conditional review, deterministic selection."""

    def __init__(self, agent: Any) -> None:
        self.agent = agent

    def run(self, session: Any) -> None:
        try:
            if str(getattr(session, "response_kind", "answer")) == "proof":
                session.stage = "wide_proof"
                self.run_proof(session)
            else:
                session.stage = "wide_answer"
                self.run_answer(session)
        except Exception as exc:
            self._trace(session, "wide_error", repr(exc)[:300])
            self._rescue(session)

    # ----------------------------------------------------------------- answer
    def run_answer(self, session: Any) -> None:
        problem = self._problem(session)
        max_tokens = DEFAULT_REASONING_TOKEN_CEILING
        jobs = [
            lambda route=route, inst=inst, temp=temp: self._one_answer(
                session, problem, route, inst, temp, max_tokens)
            for (route, inst), temp in zip(SOLVE_STANCES, _ANSWER_TEMPERATURES)
        ]
        samples = self._parallel(session, jobs)
        clusters = self._cluster(samples)
        self._trace(session, "wide_wave", {
            "wave": 1,
            "width": len(SOLVE_STANCES),
            "new_samples": [s.record() for s in samples],
            "clusters": [c.record() for c in clusters],
            "remaining_s": round(self._remaining_s(session), 1),
        })
        self._submit_answer(session, samples, clusters)

    def _submit_answer(self, session: Any, samples: List[Sample],
                       clusters: List[Cluster]) -> None:
        consensus = next((c for c in clusters if c.votes >= 2), None)
        if consensus is not None:
            best = consensus.best()
            short = consensus.answer
            source = "wide_consensus"
            decision = "consensus"
            reason = "equivalent_answers"
            verification = "independent_consensus"
        elif len(clusters) >= 2:
            review = self._maybe_review(session, clusters)
            if review is not None:
                best, short, source, decision, reason, verification = review
            else:
                best = self._preregistered_fallback(samples)
                short = best.answer
                source = "wide_forced_route_%s" % best.route_id.lower()
                decision = "forced_submit"
                reason = "route_disagreement_no_review"
                verification = "unverified"
        elif len(clusters) == 1:
            best = clusters[0].best()
            short = clusters[0].answer
            source = "wide_single_valid"
            decision = "forced_submit"
            reason = "single_valid_route"
            verification = "unverified"
        else:
            usable = [s for s in samples if s.usable]
            if not usable:
                self._trace(session, "wide_no_output", {
                    "routes": [s.record() for s in samples],
                })
                return
            best = usable[0]
            short = ""
            source = "wide_no_declared_answer"
            decision = "forced_submit"
            reason = "no_declared_answer"
            verification = "unverified"

        session.final_answer = self._compose(
            best.text, best.answer_surface, best.explicit_final)
        session.final_short = short
        session.final_source = source
        session.verification_status = verification
        session.forced_submit = decision != "consensus" and decision != "review_decided"
        self._trace(session, "wide_submit", {
            "source": source,
            "decision": decision,
            "reason": reason,
            "selected_route": best.route_id,
            "verified": False,
            "short_answer": self._clip(short, 200),
            "final_chars": len(session.final_answer or ""),
            "elapsed_s": round(self._elapsed_s(session), 1),
        })

    def _maybe_review(self, session: Any,
                      clusters: List[Cluster]) -> Optional[Tuple[Any, ...]]:
        config = getattr(self.agent, "config", None)
        enabled = bool(getattr(config, "enable_review", True))
        min_remaining = float(getattr(config, "review_min_remaining_s", 360.0))
        if not enabled:
            return None
        if self._remaining_s(session) < min_remaining:
            self._trace(session, "wide_review_skipped", {
                "reason": "insufficient_wall_clock",
                "remaining_s": round(self._remaining_s(session), 1),
            })
            return None
        candidates = _review_candidates(clusters)
        if not candidates:
            return None
        review_tokens = int(getattr(config, "review_max_tokens", 8192))
        numbered = "\n".join(
            "%d. %s" % (i + 1, c["answer"])
            for i, c in enumerate(candidates)
        )
        messages = [
            {"role": "system", "content": REVIEW_SYSTEM},
            {"role": "user", "content": _REVIEW_USER_TEMPLATE.format(
                problem=self._clip(self._problem(session), _PROBLEM_CLIP),
                candidates=numbered)},
        ]
        text, duration = self._call(
            session, messages, 0.2, review_tokens, "review:candidates")
        decision = parse_review(text)
        chosen_cluster = None
        if decision is not None:
            index = decision["chosen"] - 1
            if 0 <= index < len(candidates):
                chosen_cluster = candidates[index]
        self._trace(session, "wide_review", {
            "candidates": [
                {"answer": self._clip(c["answer"], 160),
                 "votes": len(c["samples"])}
                for c in candidates
            ],
            "review_chars": len(text or ""),
            "duration_s": round(duration, 1),
            "parseable": decision is not None,
            "decision": decision,
            "chosen_index": decision["chosen"] if decision is not None else None,
            "remaining_s": round(self._remaining_s(session), 1),
        })
        if chosen_cluster is None:
            return None
        best = max(
            chosen_cluster["samples"],
            key=lambda sample: (
                not sample.truncated,
                sample.explicit_final,
                len(sample.text or ""),
            ),
        )
        short = best.answer or chosen_cluster["samples"][0].answer
        return (
            best, short, "wide_review_decided", "review_decided",
            "review_picked_candidate", "review_decided",
        )

    @staticmethod
    def _preregistered_fallback(samples: List[Sample]) -> Sample:
        for sample in samples:
            if sample.answer:
                return sample
        return samples[0]

    # ----------------------------------------------------------------- proof
    def run_proof(self, session: Any) -> None:
        problem = self._problem(session)
        max_tokens = DEFAULT_REASONING_TOKEN_CEILING
        jobs = [
            lambda route=route, inst=inst, temp=temp: self._one_proof(
                session, problem, route, inst, temp, max_tokens)
            for (route, inst), temp in zip(PROOF_STANCES, _PROOF_TEMPERATURES)
        ]
        samples = self._parallel(session, jobs)
        complete = [
            s for s in samples
            if s.usable and _QED_RE.search(s.text.strip())
        ]
        usable = [s for s in samples if s.usable]
        pool = complete or usable
        if not pool:
            self._trace(session, "wide_proof_empty", {
                "routes": [s.record() for s in samples],
            })
            return

        best = pool[0]
        session.proof_text = best.text
        session.final_answer = best.text.strip()
        session.final_source = "wide_proof"
        session.verification_status = "blind_proof_route"
        session.forced_submit = not bool(_QED_RE.search(best.text.strip()))
        self._trace(session, "wide_proof_submit", {
            "routes": [s.record() for s in samples],
            "decision": "first_complete_preregistered_route",
            "selected_route": best.route_id,
            "complete": not session.forced_submit,
            "verified": False,
            "final_chars": len(session.final_answer or ""),
            "elapsed_s": round(self._elapsed_s(session), 1),
        })

    # --------------------------------------------------------- internals
    def _one_answer(self, session: Any, problem: str, route: str,
                    instruction: str, temperature: float,
                    max_tokens: int) -> Sample:
        messages = [
            {"role": "system", "content": SOLVE_SYSTEM},
            {"role": "user", "content": _SOLVE_USER_TEMPLATE.format(
                instruction=instruction,
                problem=self._clip(problem, _PROBLEM_CLIP))},
        ]
        return self._sampled_call(
            session, messages, route, "blind_answer", temperature, max_tokens, None)

    def _one_proof(self, session: Any, problem: str, route: str,
                   instruction: str, temperature: float,
                   max_tokens: int) -> Sample:
        messages = [
            {"role": "system", "content": PROOF_SYSTEM},
            {"role": "user", "content": _PROOF_USER_TEMPLATE.format(
                instruction=instruction,
                problem=self._clip(problem, _PROBLEM_CLIP))},
        ]
        return self._sampled_call(
            session, messages, route, "blind_proof", temperature, max_tokens, _QED_RE)

    def _sampled_call(self, session: Any, messages: List[Dict[str, str]],
                      route: str, family: str, temperature: float,
                      max_tokens: int, complete_re: Any) -> Sample:
        sample = Sample(route_id=route, route_family=family, max_tokens=max_tokens)
        text, duration = self._call(
            session, messages, temperature, max_tokens,
            "%s:%s" % (family, route))
        sample.text = text
        sample.duration_s = duration
        sample.transport_status = "success" if str(text or "").strip() else "empty_or_error"
        sample.truncated = bool(str(text or "").strip()) and self._truncated(text, complete_re)
        try:
            parser = getattr(self.agent, "parser", None)
            if parser is not None:
                sample.explicit_final = bool(
                    getattr(parser, "has_explicit_final", lambda _: False)(text))
                sample.answer_surface = str(
                    getattr(parser, "extract_declared_final_surface",
                            lambda _: "")(text) or "").strip()
            else:
                sample.explicit_final = False
                sample.answer_surface = ""
        except Exception:
            sample.explicit_final = False
            sample.answer_surface = ""
        sample.answer = self._extract(text)
        return sample

    def _call(self, session: Any, messages: List[Dict[str, str]],
              temperature: float, max_tokens: int,
              purpose: str) -> Tuple[str, float]:
        started = time.time()
        llm_call = getattr(self.agent, "llm_call", None)
        try:
            if llm_call is not None:
                text = llm_call(
                    messages, temperature=float(temperature),
                    max_tokens=int(max_tokens))
            else:
                text = ""
        except Exception:
            text = ""
        duration = time.time() - started
        with session.lock:
            session.llm_calls += 1
            session.max_call_duration_s = max(
                float(session.max_call_duration_s or 0.0), duration)
        session.remember_raw(text)
        self._trace(session, "llm_call", {
            "purpose": purpose,
            "max_tokens": int(max_tokens),
            "chars": len(text or ""),
            "transport_status": "success" if str(text or "").strip() else "empty_or_error",
            "duration_s": round(duration, 1),
            "elapsed_s": round(self._elapsed_s(session), 1),
        })
        return str(text or ""), duration

    @staticmethod
    def _parallel(session: Any, thunks: List[Any]) -> List[Sample]:
        del session
        with ThreadPoolExecutor(max_workers=max(1, len(thunks))) as pool:
            futures = [pool.submit(thunk) for thunk in thunks]
            return [future.result() for future in futures]

    def _cluster(self, samples: List[Sample]) -> List[Cluster]:
        clusters: List[Cluster] = []
        for sample in samples:
            if not sample.answer:
                continue
            for cluster in clusters:
                if answers_equal(sample.answer, cluster.answer):
                    cluster.samples.append(sample)
                    break
            else:
                clusters.append(Cluster(answer=sample.answer, samples=[sample]))
        return clusters

    def _rescue(self, session: Any) -> None:
        if str(getattr(session, "final_answer", "") or "").strip():
            return
        drafts = [str(raw or "").strip() for raw in session.accumulated_raw]
        drafts = [d for d in drafts if d]
        if not drafts:
            return
        session.final_answer = max(drafts, key=len)
        session.final_short = self._extract(session.final_answer)
        session.final_source = "wide_rescue"
        session.verification_status = "unverified"
        session.forced_submit = True

    def _extract(self, text: str) -> str:
        parser = getattr(self.agent, "parser", None)
        try:
            if parser is not None:
                value = str(
                    getattr(parser, "extract_declared_final",
                            lambda _: "")(text) or "").strip()
            else:
                value = ""
        except Exception:
            return ""
        if not value:
            return ""
        try:
            if AnswerExtractor._is_placeholder(value):
                return ""
        except Exception:
            pass
        return value

    @staticmethod
    def _truncated(text: str, complete_re: Any = None) -> bool:
        body = str(text or "").strip()
        if not body:
            return False
        if complete_re is not None:
            return not bool(complete_re.search(body))
        if re.search(r"FINAL\s*[:：]", body, re.IGNORECASE):
            return False
        if re.search(r"\\boxed\s*\{", body):
            return False
        return not bool(_TERMINAL_RE.search(body))

    @staticmethod
    def _compose(text: str, surface: str, explicit_final: bool) -> str:
        body = str(text or "").strip()
        if explicit_final:
            return body
        declared = str(surface or "").strip()
        if not declared or body.rstrip().endswith(declared):
            return body
        return body.rstrip() + "\n\n【最终答案】" + declared

    @staticmethod
    def _problem(session: Any) -> str:
        return str(getattr(session, "prompt_problem", "") or session.problem)

    @staticmethod
    def _clip(text: str, limit: int) -> str:
        body = str(text or "")
        return body if len(body) <= limit else body[:limit] + "...[truncated]"

    # -------- agent budget helpers (simplified) --------
    def _trace(self, session: Any, step: str, data: Dict[str, Any]) -> None:
        trace_obj = getattr(self.agent, "trace", None)
        if trace_obj is not None and hasattr(trace_obj, "add"):
            trace_obj.add(session, step, data)

    def _elapsed_s(self, session: Any) -> float:
        budget = getattr(self.agent, "budget", None)
        if budget is not None and hasattr(budget, "elapsed_s"):
            return budget.elapsed_s(session)
        return time.time() - float(getattr(session, "start_ts", 0.0) or 0.0)

    def _remaining_s(self, session: Any) -> float:
        budget = getattr(self.agent, "budget", None)
        if budget is not None and hasattr(budget, "remaining_s"):
            return budget.remaining_s(session)
        return max(0.0, 1140.0 - self._elapsed_s(session))
