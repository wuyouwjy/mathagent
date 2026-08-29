"""Python Agent: generate Python verification code, execute via MCP, self-correct. §3.4.

M4 hardening: intern-s2-preview-397b emits a 'Thinking Process:' CoT and sometimes
writes '```python' mid-sentence in prose. _extract_code uses a strict fence
(newline-required) + content-based fallback, and returns '' (→ retry) when no
code is found — never executes CoT as code.
"""
import re
from utils.deps import get_deps
from utils.llm.retry import chat_prefilled, chat_with_retry
from utils.llm.templates import PYTHON_PROMPT
from utils.budget.token import estimate_tokens
from utils.answer.cot_stripper import strip_cot_prefix
from utils.budget.affordability import can_afford_retry, last_attempt_cost
from utils.budget.timeout import NodeTimeoutError, run_with_timeout
from utils.skills_util.excerpt import select_script_excerpt, select_skill_excerpt
from utils.retrieval.reference_block import build_reference_block
from utils.verify.evidence import parse_verification_evidence
from utils.problem.profile import is_objective_mode, structure_instruction
from config import CONFIG


def _reference_examples_block(examples, problem: str = "") -> str:
    """Python 提示词里的题库参考区块（题面 600 / 解答 800 字符）。

    额度小于推理侧：这里的示例只用于提示"该用什么工具算"，验证脚本本身才是主体。
    仍需传入本题题面——验证脚本按近似题的参数写出来，会得出一个自洽但答非本题的
    "验证结论"，比推理侧照抄更难识破。
    """
    return build_reference_block(examples, problem_chars=600, solution_chars=800,
                                 problem=problem)


def _extract_code(response: str) -> str:
    """Extract Python code from an LLM response.

    1. strict fence (```python on its own line, newline required) — avoids
       matching '```python code block' written mid-sentence in CoT prose.
    2. loose fence, only if the content looks like code.
    3. content-based: first 'import'/'from' line to end (stop at closing ```).
    4. return '' if nothing code-like — do NOT execute CoT as code.
    """
    response = strip_cot_prefix(response)
    m = re.search(r"```python[ \t]*\n(.*?)\n```", response, re.DOTALL)
    if m:
        return m.group(1).strip()
    m = re.search(r"```python\s+(.*?)\s+```", response, re.DOTALL)
    if m:
        cand = m.group(1).strip()
        if re.match(r"^\s*(import |from |#|def |class |if |for |while |try |with |@[a-zA-Z]|[a-zA-Z_]\w*\s*=)", cand):
            return cand
    m = re.search(r"```\s+(.*?)\s+```", response, re.DOTALL)
    if m:
        cand = m.group(1).strip()
        if re.match(r"^\s*(import |from |#|def )", cand):
            return cand
    lines = response.splitlines()
    start = None
    for i, ln in enumerate(lines):
        if re.match(r"^\s*(import |from )", ln):
            start = i
            break
    if start is not None:
        block = []
        for ln in lines[start:]:
            if ln.strip() == "```":
                break
            block.append(ln)
        return "\n".join(block).strip()
    return ""


_ANSWER_PRINT_RE = re.compile(r"print\s*\(\s*[\"'][^\"']*最终答案")

#: Below this, a code-less response is a format slip; above it, generation was cut off
#: mid-flight. Mirrors the same threshold in the reasoning branch.
_EXHAUSTION_MIN_CHARS = 2000


_EVIDENCE_RETRY_CONTRACT = (
    "\n无论本轮是否成功，代码都必须在最终答案前打印两行："
    'print("验证状态:", status)，其中 status 必须是 "PASS"、"FAIL" 或 '
    '"INCONCLUSIVE"；以及 print("验证证据:", evidence)。'
    'FAIL 必须包含反例或失败断言，无法判断时使用 INCONCLUSIVE。'
    '最后一行必须是 print("最终答案:", answer)，不得省略这三类输出。'
)


def _retry_prompt(instruction: str, problem: str, candidate_answer: str = "") -> str:
    """Keep the evidence contract and candidate context in every short retry."""
    candidate_hint = ""
    if candidate_answer:
        candidate_hint = (
            "\n待核验候选（不可信，仅用于独立核对）：\n"
            + candidate_answer[:2000]
            + "\n请不要盲从候选，必须根据独立计算填写验证状态和验证证据。"
        )
    return instruction + _EVIDENCE_RETRY_CONTRACT + candidate_hint + "\n问题：" + problem


def _prints_answer(code: str) -> bool:
    """Does the code contain the mandated answer print at all?

    A cheap truncation detector: `max_tokens` cutting a generation mid-file leaves
    valid-looking but unfinished code. Matching the print call (rather than merely the
    marker text) avoids counting a comment that mentions 最终答案.
    """
    return bool(_ANSWER_PRINT_RE.search(code or ""))


_DEF_RE = re.compile(r"(?m)^def\s+([A-Za-z_]\w*)\s*\(([^)]*)\)\s*(?:->[^:\n]+)?:")
_MAIN_NAME_RE = re.compile(r"(?i)main|solve|count|compute|calc|answer|result|final")


def _append_answer_print(code: str) -> str:
    """定义了函数却没有产出结论的代码，确定性补一个主调用 + 打印。

    2026-08-10 评委报告 idx 0：DFS 建模方向完全正确，但只定义
    count_hamiltonian_paths() 未调用，stdout 空转 0.058s；补打印的 LLM 短重试又被
    预算门禁拒绝。改写是确定性的（不花 LLM 时间）：挑一个可无参调用的函数追加
    print("最终答案:", fn())，执行仍受 60s 执行器时限保护。挑不出目标时返回 ""。
    """
    source = code or ""
    if not source.strip():
        return ""
    callable_names = []
    for name, params in _DEF_RE.findall(source):
        params_clean = params.strip()
        if params_clean and not all("=" in part for part in params_clean.split(",")):
            continue  # 需要实参的函数不能盲调
        callable_names.append(name)
    if not callable_names:
        return ""
    preferred = [n for n in callable_names if _MAIN_NAME_RE.search(n)]
    target = (preferred or callable_names)[-1]
    return source + f'\n\nprint("最终答案:", {target}())\n'


#: 压缩重生成的估时（8192 token @ ~50 tok/s + 余量）。
_COMPRESSED_CALL_ESTIMATE_S = 200

#: 与推理分支同一条 reserve_margin 定价规则（2026-08-10 评委建议 2）：软预算
#: 已尽也放行压缩重生成，只要求硬上限前剩余 ≥ 估时 + 收尾余量。
_COMPRESSED_RESERVE_MARGIN_S = CONFIG.get("compressed_reserve_margin_s", 150)

#: 首轮 Python 调用的单次墙钟上限（断点续写三件套之一，与推理分支同规则）。
#: 难题上首轮会把整个节点 1100s 上限吃光、被 node_wrapper 掐断后压缩重生成
#: 永远没机会触发。压到 550s，超时就地转入压缩重生成（math_agent 实测）。
_FIRST_ATTEMPT_TIMEOUT_S = CONFIG.get("first_attempt_timeout_s", 550)

#: assistant 种子：以代码围栏开头接管助手轮，抑制 reasoning_content（机制同
#: 分类器/仲裁器 prefill），8192 token 全部用于代码本身。
_COMPRESSED_PREFILL = "```python\n"


def _compressed_python_call(deps, problem, candidate_answer,
                            failure="因长度超限在代码之前被截断"):
    """CoT 耗尽/传输超时后的熔断重生成（评委建议 4；2026-08-10 建议 2/3）。

    普通重试会以同样方式再截断一次；prefill 压缩调用直接从代码围栏开始续写。
    失败返回 (None, 原因)。
    """
    clock = deps.time_budget
    if clock and clock.remaining_hard() - _COMPRESSED_RESERVE_MARGIN_S \
            < _COMPRESSED_CALL_ESTIMATE_S:
        return None, "compressed_retry_unaffordable"
    instruction = _retry_prompt(
        f"上一次生成{failure}。现在禁止任何解释文字：直接给出一个"
        "**尽可能短**的完整 Python 程序。优先做小规模精确计算（枚举/DP/sympy），"
        "省略探索性打印。",
        problem, candidate_answer)
    try:
        resp = chat_prefilled(
            deps.client,
            messages=[{"role": "user", "content": instruction}],
            prefix=_COMPRESSED_PREFILL,
            temperature=CONFIG["temperatures"]["python"],
            max_tokens=CONFIG["max_tokens"]["python_compressed"],
            logger=deps.logger,
            time_budget=clock,
            expected_call_seconds=_COMPRESSED_CALL_ESTIMATE_S,
            label="python_compressed",
            reserve_margin_s=_COMPRESSED_RESERVE_MARGIN_S,
        )
    except Exception as exc:  # noqa: BLE001
        deps.logger.warning("Compressed python retry failed: %s", exc)
        return None, f"error: {str(exc)[:160]}"
    if deps.token_budget:
        deps.token_budget.consume(estimate_tokens(instruction), estimate_tokens(resp))
    return resp, ""


def python_agent_node(state, config):
    deps = get_deps(config)
    sl = deps.skills_loader
    client = deps.client
    mcp_client = deps.mcp_client
    budget = deps.token_budget
    max_attempts = 1 if budget and budget.is_tight() else CONFIG["max_retries_per_node"]
    problem, category = state["problem"], state["category"]
    question_mode = state.get("question_mode", "computation")
    if is_objective_mode(question_mode):
        # Choice/judgement/fill items are answered by the short reasoning path.
        # Generating a Python program for them adds latency and often produces a
        # misleading scalar that cannot represent multiple option letters or blanks.
        return {
            "python_code": "",
            "python_output": {
                "success": False,
                "skipped": True,
                "stdout": "",
                "stderr": "objective question: python verification skipped",
                "answer": "",
                "execution_time": 0.0,
                "evidence_status": "inconclusive",
                "evidence_summary": "客观题采用快速推理路径，未生成程序。",
                "contradictions": [],
            },
            "python_trace": [{"attempt": 0, "status": "skipped", "reason": "objective_mode"}],
            "python_attempts": 0,
            "python_evidence_status": "inconclusive",
            "python_evidence_summary": "客观题采用快速推理路径，未生成程序。",
            "python_contradictions": [],
        }
    reasoning_result = state.get("reasoning_result") or {}
    candidate_answer = str(reasoning_result.get("answer") or "").strip()
    try:
        validation_script = sl.get_validation_script(category)
    except Exception:
        validation_script = ""
    # 题库参考示例：与推理节点收到的是同一批（同一次检索的全部结果）。
    examples_text = _reference_examples_block(state.get("retrieved_examples"), problem)
    # Validation examples are prompt documents. Select the knowledge-point sections
    # whose vocabulary matches the problem instead of sending a positional prefix.
    base_prompt = PYTHON_PROMPT.format(
        validation_script=select_script_excerpt(validation_script, problem, 2000) + examples_text,
        problem=problem, category=category)
    base_prompt += structure_instruction(problem)
    # 技能手册的速查条目（题型方法论）与验证示例互补：前者决定"算什么/怎么建模"，
    # 后者给"怎么写验证代码"。同一素材源推理分支已在读，这里用小额度共享。
    try:
        skill_doc = sl.get_skill_document(category)
    except Exception:
        skill_doc = ""
    knowledge_ref = select_skill_excerpt(skill_doc, problem, 1600)
    if knowledge_ref:
        base_prompt += "\n\n[技能知识点参考]\n" + knowledge_ref
    if candidate_answer:
        base_prompt += (
            "\n\n待核验候选（不可信，仅用于独立核对）：\n"
            + candidate_answer[:2000]
            + "\n请不要盲从该候选；根据代码计算结果填写验证状态和验证证据。"
        )
    hint = state.get("branch_hint")
    prompt = f"{base_prompt}\n\n[复核提示] {hint}" if hint else base_prompt
    # VeritasMath 模结构守护：F_2/Z_m 语境注入"结构内聚合"强制条款
    # （评委报告 idx 7：六个 F_2 值被按普通整数相加；提示层自觉不可靠，
    #  生成后还有一道静态核查兜底）。
    modular = {"hit": False, "cues": []}
    if CONFIG.get("enable_modular_guard", True):
        from utils.verify.modular_guard import code_complies, detect_modular_context, prompt_clause
        modular = detect_modular_context(problem)
        if modular["hit"]:
            prompt += prompt_clause(problem)
    # VeritasMath 计数题枚举对照守护（M6，ultra_112 idx=40 实证）：组合计数是
    # LLM 最弱项，闭式极易错。检出计数题则注入强制枚举对照条款，生成后静态核查
    # 代码必须含枚举循环，否则打回（不执行只写闭式的代码）。
    counting = {"hit": False}
    if CONFIG.get("enable_counting_guard", True):
        from utils.verify.counting_guard import code_has_enumeration, detect_counting
        from utils.verify.counting_guard import prompt_clause as counting_clause
        counting = {"hit": detect_counting(problem)}
        if counting["hit"]:
            prompt += counting_clause(problem)

    trace = []
    attempts = 0
    last_output = None
    last_code = ""
    clock = deps.time_budget

    def finalize(output):
        enriched = parse_verification_evidence(
            output, candidate_answer=candidate_answer, code=last_code)
        return {
            "python_code": last_code,
            "python_output": enriched,
            "python_trace": trace,
            "python_attempts": attempts,
            "modular_guard": modular,
            "counting_guard": counting,
            "python_evidence_status": enriched.get("evidence_status", "inconclusive"),
            "python_evidence_summary": enriched.get("evidence_summary", ""),
            "python_contradictions": enriched.get("contradictions", []),
            "python_reference_chars": len(examples_text),
        }
    if clock and clock.fast_path():
        max_attempts = 1
    compressed_next = False
    compressed_used = False
    compressed_failure = "因长度超限在代码之前被截断"
    # 完整重生成只做一次：首轮生成截断/执行失败后，时间充裕时先做一次普通完整
    # 重生成（而非直接压缩硬写），把空余墙钟转化为更充分的代码生成；失败则落压缩。
    full_retried = False
    while True:
        if compressed_next:
            # 熔断重生成不占普通重试名额，也不按上一轮 450s 的实测成本计价——
            # 它的成本上界就是压缩额度本身（~200s），reserve_margin 检查在调用内。
            compressed_next = False
            compressed_used = True
            attempts += 1
            resp, comp_fail = _compressed_python_call(deps, problem, candidate_answer,
                                                      failure=compressed_failure)
            if resp is None:
                trace.append({"attempt": attempts, "status": "skipped",
                              "reason": comp_fail or "compressed_retry_failed"})
                break
        else:
            if attempts >= max_attempts:
                break
            # Same affordability rule as the reasoning branch: fund a retry against
            # what the last attempt actually cost. Both branches retrying blindly at
            # ~510s each is what overran the deadline and produced no answer on
            # 2026-07-29.
            if attempts and not can_afford_retry(clock, "python"):
                deps.logger.warning(
                    "Skipping Python retry: %.0fs left, last attempt cost %.0fs",
                    clock.remaining(), last_attempt_cost(clock, "python"))
                trace.append({"attempt": attempts + 1, "status": "skipped",
                              "reason": "retry_unaffordable"})
                break
            attempts += 1
            # Same rule as the reasoning branch: a transport failure keeps whatever
            # this branch already produced rather than emptying it, so the other
            # branch is never left as the sole candidate when it did not have to be.
            try:
                if attempts == 1 and _FIRST_ATTEMPT_TIMEOUT_S:
                    # 首轮调用加单次墙钟上限：与推理分支同规则，难题上首轮会把
                    # 整个节点 1100s 上限吃光、被 node_wrapper 掐断后压缩重生成
                    # 永远没机会触发。压到 550s，超时就地转入压缩重生成
                    # （math_agent 断点续写三件套之一）。
                    resp = run_with_timeout(
                        lambda: chat_with_retry(
                            client,
                            messages=[{"role": "user", "content": prompt}],
                            temperature=CONFIG["temperatures"]["python"],
                            max_tokens=CONFIG["max_tokens"]["python"],
                            logger=deps.logger,
                            time_budget=deps.time_budget,
                            label="python",
                        ),
                        _FIRST_ATTEMPT_TIMEOUT_S,
                    )
                else:
                    resp = chat_with_retry(
                        client,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=CONFIG["temperatures"]["python"],
                        max_tokens=CONFIG["max_tokens"]["python"],
                        logger=deps.logger,
                        time_budget=deps.time_budget,
                        label="python",
                    )
            except Exception as exc:  # noqa: BLE001
                if isinstance(exc, NodeTimeoutError) and clock:
                    # 与推理分支同规则：把首轮超时上限记入账，让对账定价看到完整
                    # 调用的真实成本，而不是压缩重生成的短耗时。
                    clock.record("python", _FIRST_ATTEMPT_TIMEOUT_S)
                deps.logger.warning("Python attempt %s failed: %s", attempts, exc)
                last_output = last_output or {
                    "success": False, "stdout": "", "stderr": str(exc)[:300],
                    "answer": None, "execution_time": 0.0,
                }
                trace.append({"attempt": attempts, "status": "failed", "error": str(exc)[:200]})
                # 首轮超时/传输失败同样先试压缩挽救（2026-08-10 评委建议 3，与
                # 推理分支同规则）：压缩调用输出短，在并发拥堵下更可能按时返回。
                if not compressed_used:
                    compressed_failure = (
                        "因首轮生成超出时限被切断" if isinstance(exc, NodeTimeoutError)
                        else "因网络传输故障未能返回")
                    compressed_next = True
                    continue
                break
            if budget:
                budget.consume(estimate_tokens(prompt), estimate_tokens(resp))
        code = _extract_code(resp)
        if code:
            last_code = code
        if code and modular.get("hit") and not code_complies(code):
            # 静态核查：模结构语境下最终聚合未见取模/异或——打回修复而非执行。
            # 执行一段聚合错误的代码只会产出一个"看起来更可信"的错误答案。
            trace.append({"attempt": attempts, "status": "modular_guard_violation"})
            if attempts >= max_attempts:
                break
            prompt = _retry_prompt(
                "上一次的代码在模结构语境下未做结构内聚合：最终求和/计数必须显式取模"
                "（F_2 用 % 2 或 ^，Z_m 用 % m），并在打印最终答案前加一行 "
                'print("结构核验:", total % m)。请只输出修正后的 ```python``` 代码块。',
                problem, candidate_answer)
            continue
        if code and counting.get("hit") and not code_has_enumeration(code):
            # 静态核查（M6）：计数题代码只写闭式、无小规模枚举对照——打回修复。
            # 闭式极易错（重数/漏数/边界），未对照的闭式不值得执行。
            trace.append({"attempt": attempts, "status": "counting_guard_violation"})
            if attempts >= max_attempts:
                break
            prompt = _retry_prompt(
                "上一次的代码直接写了闭式/公式，未做小规模枚举对照。计数题必须："
                "先把规模缩到最小实例（n=2,3,4），用 for/range/itertools 暴力枚举出精确值，"
                "再让候选公式在同规模逐点 assert 比对，全部吻合才外推。请只输出修正后的 "
                "```python``` 代码块（含枚举对照打印），结尾 print(\"最终答案:\", answer)。",
                problem, candidate_answer)
            continue
        if not code:
            # A *long* response with no code fence means CoT consumed the whole budget
            # before any code was written (this model bills reasoning_content against
            # max_tokens). Re-asking for the same program truncates the same way —
            # 评委报告模式 A 的 Python 侧（大量 "Python 无代码/无产出"）。改发
            # prefill 压缩重生成；压缩后仍无代码则放弃本分支。
            exhausted = len(resp or "") >= _EXHAUSTION_MIN_CHARS
            last_output = {"success": False, "stdout": "",
                           "stderr": "code generation truncated before any code block"
                                     if exhausted else "no code block extracted",
                           "answer": None, "execution_time": 0.0}
            trace.append({"attempt": attempts, "status": "failed",
                          "error": "truncated before code" if exhausted else "no code block",
                          "response_chars": len(resp or "")})
            if compressed_used:
                break
            if exhausted:
                # 完整重生成：时间充裕时先做一次普通完整重生成（而非直接压缩硬写），
                # 把空余墙钟转化为更充分的代码生成；失败再落压缩。full_retried 保证
                # 只做一次，max_attempts += 1 让这次普通调用绕过次数上限。
                if not full_retried and can_afford_retry(clock, "python"):
                    full_retried = True
                    max_attempts += 1
                    prompt = _retry_prompt(
                        "你上一次因长度超限没有输出 ```python``` 代码块。请重新生成完整 "
                        "Python 程序：用 sympy 计算，最后一行 print(\"最终答案:\", answer)。",
                        problem, candidate_answer)
                    continue
                compressed_next = True
                continue
            prompt = _retry_prompt(
                "你上一次没有输出 ```python``` 代码块。请只输出一个 ```python``` 代码块，"
                "不要任何其他文字。用 sympy 计算，最后一行 print(\"最终答案:\", answer)。",
                problem, candidate_answer)
            continue
        if not _prints_answer(code):
            # 缺少最终答案打印的代码**仍然执行**：stdout 里往往已有结论
            # （评委报告 idx 38：正确公式在代码里，旧逻辑拒绝执行去换一次
            # 450s 的重生成，最终一无所获）。执行后由 stdout 二次抽取兜底。
            trace.append({"attempt": attempts, "status": "missing_answer_print",
                          "note": "executing anyway; stdout miner may recover"})
        if mcp_client is None:
            output = {"success": False, "stdout": "", "stderr": "MCP client unavailable",
                      "answer": None, "execution_time": 0.0}
        else:
            output = mcp_client.execute(code, timeout=CONFIG["node_timeouts"]["python_mcp_execute"])
        last_output = output
        trace.append({
            "attempt": attempts,
            "status": "success" if output.get("success") else "failed",
            "error": (output.get("stderr") or "")[:200],
        })
        if output.get("success"):
            probe = parse_verification_evidence(
                output, candidate_answer=candidate_answer, code=code)
            if str(probe.get("answer") or "").strip():
                return finalize(output)
            # 执行成功但连 stdout 挖掘都拿不到结论 → 先做确定性补调用修复
            # （2026-08-10 评委建议 5：idx 0 的代码方向正确、只差一个主调用，
            # 而"补打印"LLM 短重试恰恰会被预算门禁拒绝）。修不动再花 LLM 重试。
            trace.append({"attempt": attempts, "status": "no_extractable_answer"})
            repaired = _append_answer_print(code)
            if repaired and mcp_client is not None:
                repaired_output = mcp_client.execute(
                    repaired, timeout=CONFIG["node_timeouts"]["python_mcp_execute"])
                repaired_probe = parse_verification_evidence(
                    repaired_output, candidate_answer=candidate_answer, code=repaired)
                answer_text = str(repaired_probe.get("answer") or "").strip()
                if repaired_output.get("success") and answer_text \
                        and answer_text.lower() not in {"none", "null"}:
                    last_code = repaired
                    trace.append({"attempt": attempts,
                                  "status": "deterministic_print_repair"})
                    return finalize(repaired_output)
                trace.append({"attempt": attempts, "status": "print_repair_failed",
                              "error": (repaired_output.get("stderr") or "")[:200]})
            if compressed_used:
                return finalize(output)
            prompt = _retry_prompt(
                "你上一次的代码执行成功但没有输出任何最终结论。请输出修正后的 "
                "```python``` 代码块：保留原计算，务必以 print(\"最终答案:\", answer) 结尾。",
                problem, candidate_answer)
            continue
        # 执行失败：改用压缩 prefill 重试（抑制私有 reasoning、代码更短，~150s
        # 而非 ~200s 完整重生成）。stderr 拼进 failure 让模型针对性修复；已用过
        # 压缩仍失败则放弃本分支，不再支付第二次完整生成。
        if compressed_used:
            break
        stderr_brief = (output.get('stderr') or '').replace('\n', ' ').strip()[:300]
        # 完整重生成：时间充裕时先做一次普通完整重生成（带 stderr 反馈），把空余
        # 墙钟转化为更充分的修复；失败再落压缩。full_retried 保证只做一次。
        if not full_retried and can_afford_retry(clock, "python"):
            full_retried = True
            max_attempts += 1
            prompt = _retry_prompt(
                f"你上一次的代码执行失败（错误：{stderr_brief}）。请修正后重新输出完整 "
                "```python``` 代码块，最后一行 print(\"最终答案:\", answer)。",
                problem, candidate_answer)
            continue
        compressed_failure = f"代码执行失败（错误：{stderr_brief}）"
        compressed_next = True
    return finalize(last_output)
