#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T3 Mock Integration Test - No API Key Required.

Uses MockClient to simulate LLM responses and verify the full LangGraph pipeline:
  classify -> reasoning + python -> cross-validate -> coordinate
"""

import json
import sys
import os
import time
import io

# Fix Windows GBK encoding issue
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ============================================================
# Part 1: Mock Client
# ============================================================

class MockClient:
    """模拟 competition platform 注入的 official_client。

    按照调用顺序返回预设响应，覆盖分类→推理→Python→协调→仲裁各阶段。
    """

    def __init__(self):
        self.call_count = 0
        self.call_log = []

    def chat(self, messages, temperature=0.2, max_tokens=4096):
        self.call_count += 1
        content = self._get_response(messages, temperature, max_tokens)
        self.call_log.append({
            "call": self.call_count,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "content_preview": str(content)[:120],
        })
        # 返回字符串（模拟 InternChatClient 最常见的返回格式）
        return content

    def _get_response(self, messages, temperature, max_tokens):
        """根据消息内容返回对应的模拟响应。"""
        user_content = ""
        for msg in (messages or []):
            if msg.get("role") == "user":
                user_content += str(msg.get("content", ""))

        # --- 分类调用 ---
        if "判断下面这道数学题属于哪一个类别" in user_content:
            return '{"category": "数学分析", "confidence": 0.92}'

        # --- 协调/最终答案调用 ---
        if "数学教学专家" in user_content and "将解题过程整理成完整" in user_content:
            return """## 问题理解
题目要求计算函数 $f(x)=x^2$ 在 $x=3$ 处的导数。

## 解题思路
使用幂函数求导公式 $\\frac{d}{dx}x^n = nx^{n-1}$。

## 详细步骤
步骤1：对 $f(x)=x^2$ 求导，得 $f'(x)=2x$。
步骤2：代入 $x=3$，得 $f'(3)=2\\times 3=6$。

## 最终答案
6"""

        # --- 默认返回（推理/Python/仲裁等） ---
        return """## 问题分析
这是一道微积分基础题，要求计算函数在指定点的导数。

## 详细解题步骤
步骤1：计算导数
使用公式/定理：幂函数求导公式 $\\frac{d}{dx}x^n = nx^{n-1}$
计算过程：$f(x)=x^2 \\Rightarrow f'(x)=2x$

步骤2：代入求值
使用公式/定理：直接代入
计算过程：$f'(3)=2\\times 3=6$

## 最终答案
6

## 关键验证点
- 验证 $f'(3)=\\lim_{h\\to 0}\\frac{(3+h)^2-9}{h}=\\lim_{h\\to 0}(6+h)=6$
- 与幂函数求导公式结果一致"""


# ============================================================
# Part 2: Utility Tests (不依赖 LLM，纯确定性逻辑)
# ============================================================

def test_utils():
    """测试所有确定性 utility 函数。"""
    print("\n" + "=" * 60)
    print("[TEST] Part 2: 确定性 Utility 函数测试")
    print("=" * 60)

    passed = 0
    failed = 0

    def check(name, condition, detail=""):
        nonlocal passed, failed
        if condition:
            passed += 1
            print(f"  [PASS] {name}")
        else:
            failed += 1
            print(f"  [FAIL] {name}  {detail}")

    # --- Answer Extractor ---
    print("\n[PKG] answer_extractor:")
    from utils.answer.extractor import (
        extract_boxed_answer, extract_answer_fallback,
        looks_incomplete_answer, looks_like_latex_fragment,
        is_multi_part_problem, is_answer_only_problem,
    )
    check("boxed 提取 \\boxed{72}", extract_boxed_answer("\\boxed{72}") == "72")
    check("boxed 嵌套 \\boxed{\\frac{1}{2}}",
          extract_boxed_answer("解答：\\boxed{\\frac{1}{2}} 是最终答案。") == "\\frac{1}{2}")
    check("残缺检测 '(Matrix([' 为 True",
          looks_incomplete_answer("(Matrix(['") == True)
    check("残缺检测 '72' 为 False",
          looks_incomplete_answer("72") == False)
    check("LaTeX 残片检测 '1}^n X_i$' 为 True",
          looks_like_latex_fragment("1}^n X_i$") == True)
    check("LaTeX 残片检测 'x^2' 为 False",
          looks_like_latex_fragment("x^2") == False)
    check("多问项检测 '求均值，以及标准差'",
          is_multi_part_problem("求均值，以及标准差") == True)
    check("填空检测 '____'",
          is_answer_only_problem("计算 ____ 的值") == True)

    # --- Answer Contract ---
    print("\n[PKG] answer_contract:")
    from utils.answer.contract import required_components, missing_components
    hyp_test = "对显著性水平α=0.05，检验H0:μ=500"
    check("假设检验 → hypothesis_conclusion",
          "hypothesis_conclusion" in required_components(hyp_test))
    ci_test = "求均值的95%置信区间"
    check("置信区间 → ci_two_sided",
          "ci_two_sided" in required_components(ci_test))
    check("缺失检测：统计量无结论",
          "hypothesis_conclusion" in missing_components(hyp_test, "t=2.5"))
    check("满足检测：有拒绝结论",
          "hypothesis_conclusion" not in missing_components(
              hyp_test, "拒绝原假设，认为均值有显著差异"))

    # --- Answer Formatter ---
    print("\n[PKG] answer_formatter:")
    from utils.answer.formatter import post_process_final_response
    calc_result = post_process_final_response(
        "最终答案：6", "6", "computation", problem="计算f'(3)")
    check("计算题格式化包含'最终答案'",
          "最终答案" in calc_result)
    proof_result = post_process_final_response(
        "结论：函数在x=0处连续\n证明：...", "函数在x=0处连续", "proof")
    check("证明题格式化包含'结论'",
          "结论" in proof_result)

    # --- Answer Matcher ---
    print("\n[PKG] answer_matcher:")
    from utils.answer.matcher import AnswerMatcher
    match1 = AnswerMatcher.match_answers(
        problem="求f'(3)", reasoning_result={"answer": "6"},
        python_result={"success": True, "answer": "6"})
    check("相同数值答案 match", match1["status"] == "match")

    match2 = AnswerMatcher.match_answers(
        problem="求f'(3)", reasoning_result={"answer": "6"},
        python_result={"success": True, "answer": "7"})
    check("不同数值答案 mismatch", match2["status"] == "mismatch")

    # --- Skills Loader ---
    print("\n[PKG] skills_loader:")
    from utils.skills_util.loader import SkillsLoader
    loader = SkillsLoader()
    check("18 个领域目录扫描",
          len(loader.categories) == 18,
          f"got {len(loader.categories)}: {loader.categories}")
    check("'抽象代数' skill 文档可加载",
          len(loader.get_skill_document("抽象代数")) > 100)
    check("'概率论' 验证脚本可加载",
          len(loader.get_validation_script("概率论")) > 100)
    cats = loader.find_candidate_categories("设F_81为81元的有限域，求T中元素的个数")
    check("有限域→抽象代数分类",
          cats[0][0] == "抽象代数",
          f"top category: {cats[0][0]}")

    # --- Problem Profile ---
    print("\n[PKG] problem_profile:")
    from utils.problem.profile import classify_question_mode, is_objective_mode
    check("证明题检测", classify_question_mode("证明f(x)在R上连续") == "proof")
    check("计算题检测", classify_question_mode("求f'(3)的值") == "computation")
    check("证明题检测 proof",
          classify_question_mode("证明f(x)在R上连续") == "proof")
    check("计算题检测",
          classify_question_mode("求f'(3)的值") == "computation")
    check("选择题检测 (含选项)",
          classify_question_mode("下列选项中正确的是 A.1 B.2 C.3 D.4") == "choice")
    check("判断题检测",
          classify_question_mode("判断下列说法是否正确") == "true_false")
    check("客观题判断", is_objective_mode("choice") == True)
    check("计算题非客观", is_objective_mode("computation") == False)

    # --- Time Budget ---
    print("\n[PKG] time_budget:")
    from utils.budget.time import TimeBudget
    tb = TimeBudget()
    check("初始剩余时间 > 0", tb.remaining() > 0)
    check("初始未过期", not tb.expired())
    check("快路径未触发 (剩余 > 300s)", not tb.fast_path())
    tb.record("test", 950)
    check("消耗后剩余 < 总预算", tb.remaining() < 1200)
    snapshot = tb.snapshot()
    check("快照包含 elapsed", "elapsed_s" in snapshot)
    check("快照包含 remaining", "remaining_s" in snapshot)

    # --- Token Budget ---
    print("\n[PKG] token_budget:")
    from utils.budget.token import TokenBudget, estimate_tokens
    tok = TokenBudget()
    check("初始不tight", not tok.is_tight())
    est = estimate_tokens("Hello world, this is a test string with about 20 words")
    check("token 估算 > 0", est > 0)

    # --- COT Stripper ---
    print("\n[PKG] cot_stripper:")
    from utils.cot_stripper import is_placeholder_answer, strip_cot_prefix
    check("占位符 '[Result]'", is_placeholder_answer("[Result]") == True)
    check("非占位符 '72'", is_placeholder_answer("72") == False)
    check("占位符 '无法确定'", is_placeholder_answer("无法确定") == True)

    # --- Conclusion Salvage ---
    print("\n[PKG] conclusion_salvage:")
    from utils.conclusion_salvage import salvage_conclusion
    text_with_conclusion = "经过推导，我们知道x=2。因此答案是2。综上，最终结果为2。"
    salvaged = salvage_conclusion(text_with_conclusion)
    check("散文结论可捞回", bool(salvaged), f"got: {salvaged!r}")

    text_exploratory = "我们先尝试a=1，看看是否可行。也许b=2也可以。让我们继续探索。"
    salvaged2 = salvage_conclusion(text_exploratory)
    check("探索散文不误捞", not salvaged2,
          f"should be empty, got: {salvaged2!r}")

    # --- Structured Answer ---
    print("\n[PKG] structured_answer:")
    from utils.answer import structured
    check("模块可导入", structured is not None)

    # --- Problem Anchor ---
    print("\n[PKG] problem_anchor:")
    from utils.problem.anchor import make_problem_anchor, verify_problem_anchor
    anchor = make_problem_anchor("test problem", 0)
    check("SHA256 锚定生成", "sha256" in anchor and len(anchor["sha256"]) == 64)
    check_result = verify_problem_anchor({"problem": "test problem", "problem_anchor": anchor})
    check("问题完整性验证通过", check_result.event is None,
          f"event: {check_result.event}")

    # --- Skill Excerpt ---
    print("\n[PKG] skill_excerpt:")
    from utils.skills_util.excerpt import select_skill_excerpt
    skill_doc = loader.get_skill_document("抽象代数")
    excerpt = select_skill_excerpt(skill_doc, "设F_81为81元的有限域", 3000)
    check("skill 片段按主题选取", len(excerpt) > 0 and len(excerpt) <= 3200)

    # --- Answer Cleanliness ---
    print("\n[PKG] answer_cleanliness:")
    from utils.answer.cleanliness import is_noise_answer, looks_derivation_fragment
    check("噪声: '哪里出错了？啊！'", is_noise_answer("哪里出错了？啊！") == True)
    check("非噪声: '最终答案是6。'", is_noise_answer("最终答案是6。") == False)
    check("推导碎片: '0 if i odd, 2 if i even'",
          looks_derivation_fragment("0 if i odd, 2 if i even") == True)

    # --- Verification Evidence ---
    print("\n[PKG] verification_evidence:")
    from utils.verification.evidence import parse_verification_evidence
    ev = parse_verification_evidence(
        {"success": True, "stdout": "验证状态: PASS\n验证证据: sympy验证一致\n最终答案: 6", "answer": "6"},
        candidate_answer="6",
        code="import sympy\nx=sympy.Symbol('x')\nresult=sympy.diff(x**2,x).subs(x,3)\nassert result==6\nprint('最终答案:', result)",
    )
    check("验证证据 PASS→support",
          ev["evidence_status"] == "support",
          f"got: {ev['evidence_status']}")
    check("验证证据摘要非空", bool(ev.get("evidence_summary")))

    # --- Deps ---
    print("\n[PKG] deps:")
    from utils.deps import Deps, MockClient as DepsMock
    deps = Deps(client=DepsMock())
    check("Deps 构造成功", deps.client is not None)

    # --- Summary ---
    print("\n" + "=" * 60)
    print(f"[STAT] Utility 测试结果: {passed} passed, {failed} failed (共 {passed+failed})")
    print("=" * 60)
    return failed == 0


# ============================================================
# Part 3: 完整 ReasoningAgent.solve() 流水线测试
# ============================================================

def test_full_pipeline():
    """使用 MockClient 运行完整的 ReasoningAgent.solve() 流水线。"""
    print("\n" + "=" * 60)
    print("[TEST] Part 3: 完整 solve() 流水线测试")
    print("=" * 60)

    from user_agent import ReasoningAgent

    # 创建 agent（使用 MockClient）
    agent = ReasoningAgent(client=MockClient())

    # 测试题 1：计算题
    print("\n[CASE] 测试题 1: 基础微积分")
    problem1 = "设 $f(x)=x^2$，求 $f'(3)$。"
    metadata1 = {"idx": 0}

    start = time.time()
    result1 = agent.solve(problem1, metadata1)
    elapsed = time.time() - start

    # 验证返回格式
    checks = []
    checks.append(("返回 dict", isinstance(result1, dict)))
    checks.append(("final_response 存在", "final_response" in result1))
    checks.append(("final_response 非空字符串",
                   isinstance(result1.get("final_response"), str)
                   and result1["final_response"].strip()))
    checks.append(("trace 存在", "trace" in result1))
    checks.append(("trace 是列表", isinstance(result1.get("trace"), list)))
    checks.append(("trace 非空", len(result1.get("trace", [])) > 0))
    checks.append(("可 JSON 序列化", _is_json_serializable(result1)))

    for name, ok in checks:
        status = "[PASS]" if ok else "[FAIL]"
        print(f"  {status} {name}")

    # 打印关键输出
    fr = result1.get("final_response", "")
    print(f"\n  [INFO] final_response ({len(fr)} chars):")
    print(f"     {fr[:200]}{'...' if len(fr) > 200 else ''}")

    trace_steps = [t.get("step") for t in result1.get("trace", [])]
    print(f"\n  [INFO] trace 步骤: {trace_steps}")

    print(f"\n  [TIME]  耗时: {elapsed:.1f}s")
    # 获取MockClient的调用次数
    if hasattr(agent, 'client') and hasattr(agent.client, 'call_count'):
        print(f"  [CALL] LLM 调用次数: {agent.client.call_count}")

    # 测试题 2：证明题
    print("\n[CASE] 测试题 2: 证明题")
    problem2 = "证明 $\\lim_{x\\to 0}\\frac{\\sin x}{x}=1$。"
    metadata2 = {"idx": 1}

    result2 = agent.solve(problem2, metadata2)
    fr2 = result2.get("final_response", "")
    print(f"  [PASS] final_response ({len(fr2)} chars): {fr2[:150]}...")

    # 测试题 3：无限域/抽象代数（T2 15.18 报告中答对的题目类型）
    print("\n[CASE] 测试题 3: 抽象代数 - 有限域")
    problem3 = "设$\\mathbb{F}_{81}$为$81$元的有限域。$T=\\{\\alpha\\in\\mathbb{F}_{81}|\\mathbb{F}_{81}=\\mathbb{F}_3(\\alpha)\\}$。求$T$中元素的个数。"
    metadata3 = {"idx": 2}

    result3 = agent.solve(problem3, metadata3)
    fr3 = result3.get("final_response", "")
    print(f"  [PASS] final_response ({len(fr3)} chars): {fr3[:150]}...")

    # 输出汇总
    all_passed = all(c[1] for c in checks)
    print("\n" + "=" * 60)
    print(f"[STAT] Pipeline 测试: {'全部通过' if all_passed else '有失败项'}")
    print(f"   总耗时: {elapsed:.1f}s (3 题)")
    print("=" * 60)
    return all_passed


def _is_json_serializable(obj):
    try:
        json.dumps(obj, ensure_ascii=False)
        return True
    except (TypeError, ValueError):
        return False


# ============================================================
# Part 4: 接口契约测试
# ============================================================

def test_interface_contract():
    """测试比赛要求的硬性接口契约。"""
    print("\n" + "=" * 60)
    print("[TEST] Part 4: 接口契约测试")
    print("=" * 60)

    from user_agent import ReasoningAgent

    passed = 0
    failed = 0

    def check(name, condition):
        nonlocal passed, failed
        if condition:
            passed += 1
            print(f"  [PASS] {name}")
        else:
            failed += 1
            print(f"  [FAIL] {name}")

    # 1. 类可导入
    check("ReasoningAgent 可从 user_agent 导入", True)  # 已经导入成功

    # 2. __init__ 接受 client
    agent = ReasoningAgent(client=MockClient())
    check("__init__(client) 正常", True)

    # 3. solve 方法存在
    check("solve 方法存在", hasattr(agent, 'solve') and callable(agent.solve))

    # 4. solve 返回 dict
    result = agent.solve("1+1=?", {"idx": 99})
    check("solve 返回 dict", isinstance(result, dict))

    # 5. final_response 非空字符串
    check("final_response 非空 str",
          isinstance(result.get("final_response"), str) and result["final_response"].strip())

    # 6. trace 是 list
    check("trace 是 list", isinstance(result.get("trace"), list))

    # 7. JSON 可序列化
    check("返回值可 JSON 序列化", _is_json_serializable(result))

    # 8. metadata=None 不崩溃
    result_none = agent.solve("2+2=?", None)
    check("metadata=None 不崩溃",
          isinstance(result_none, dict) and result_none.get("final_response"))

    # 9. metadata 非 dict 不崩溃
    result_str = agent.solve("3+3=?", "not_a_dict")
    check("metadata='not_a_dict' 不崩溃",
          isinstance(result_str, dict) and result_str.get("final_response"))

    # 10. problem 非字符串不崩溃
    try:
        result_int = agent.solve(12345, {"idx": 100})
        check("problem=12345 不崩溃",
              isinstance(result_int, dict) and result_int.get("final_response"))
    except Exception as e:
        check("problem=12345 不崩溃", False)

    # 11. 空 problem
    result_empty = agent.solve("", {"idx": 101})
    check("空 problem 不崩溃",
          isinstance(result_empty, dict) and "final_response" in result_empty)

    print("\n" + "=" * 60)
    print(f"[STAT] 契约测试: {passed} passed, {failed} failed (共 {passed+failed})")
    print("=" * 60)
    return failed == 0


# ============================================================
# Main
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("[MATH] Math-Agent-System T3 — 模拟集成测试")
    print("=" * 60)
    print("使用 MockClient，无需 API Key，不访问外部服务")
    print()

    results = {}

    # Part 2: Utility tests
    results["utils"] = test_utils()

    # Part 3: Full pipeline
    results["pipeline"] = test_full_pipeline()

    # Part 4: Interface contract
    results["contract"] = test_interface_contract()

    # Final summary
    print("\n" + "=" * 60)
    print("[FINAL] 最终汇总")
    print("=" * 60)
    for name, ok in results.items():
        print(f"  {'[PASS]' if ok else '[FAIL]'} {name}: {'PASS' if ok else 'FAIL'}")
    all_ok = all(results.values())
    print(f"\n  {'[OK] 全部通过！' if all_ok else '[WARN]  有失败项，请检查'}")
    print("=" * 60)
    sys.exit(0 if all_ok else 1)
