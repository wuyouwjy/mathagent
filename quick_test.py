#!/usr/bin/env python3
"""Quick smoke-test for the T2 ReasoningAgent.

Usage:
    export INTERN_API_KEY="sk-..."
    python quick_test.py

Or dry-run without API key (mock client, interface-only check):
    python quick_test.py --mock
"""

import json
import os
import sys
from typing import Any, Dict, List

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from user_agent import ReasoningAgent


# ---------------------------------------------------------------------------
# Mock client — validates the interface without a real API call
# ---------------------------------------------------------------------------
class MockChatClient:
    """Simulates the competition platform's official client.

    Returns a plausible Intern-S style response with FINAL marker.
    """

    def __init__(self, model: str = "intern-s2-preview-mock") -> None:
        self.model = model

    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.2,
        max_tokens: int = 131072,
    ) -> str:
        problem = ""
        for m in messages:
            if m.get("role") == "user":
                problem = m.get("content", "")
        # Return a well-formed response that the T2 pipeline can extract from
        return (
            "解答：根据题目条件逐步推导如下。\n\n"
            "第一步：分析题面结构……\n"
            "第二步：代入计算……\n"
            "最终得到结果。\n\n"
            "FINAL: 42\n"
            "CONFIDENCE: 0.85"
        )

    def __repr__(self) -> str:
        return f"MockChatClient(model={self.model})"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
def check_interface() -> None:
    """Validate that the ReasoningAgent satisfies the competition platform contract."""
    print("=" * 60)
    print("Math-Agent-System T2 — Interface Contract Check")
    print("=" * 60)

    client = MockChatClient()
    agent = ReasoningAgent(client=client)

    # 1. __init__ signature
    print("\n[1] ReasoningAgent(client=client) — constructor")
    assert agent is not None
    assert hasattr(agent, "solve")
    print("  [OK] Constructor accepts 'client' kwarg")

    # 2. solve(problem, metadata) returns dict
    print("\n[2] agent.solve(problem, metadata) — return type")
    result = agent.solve("计算 1+2+3+...+100 的和", {"idx": 0})
    assert isinstance(result, dict), f"Expected dict, got {type(result)}"
    print("  [OK] Returns dict")

    # 3. final_response is non-empty string
    print("\n[3] result['final_response'] — non-empty str")
    final = result.get("final_response", "")
    assert isinstance(final, str), f"Expected str, got {type(final)}"
    assert final.strip(), "final_response must not be empty"
    print(f"  [OK] final_response: {len(final)} chars")

    # 4. trace is a list
    print("\n[4] result['trace'] — list")
    trace = result.get("trace", [])
    assert isinstance(trace, list), f"Expected list, got {type(trace)}"
    print(f"  [OK] trace: {len(trace)} entries")
    for t in trace[:3]:
        print(f"    [{t.get('step', '?')}] elapsed={t.get('elapsed_s', '?')}s")

    # 5. stats (T2 new field)
    print("\n[5] result['stats'] — summary")
    stats = result.get("stats", {})
    if stats:
        print(f"  [OK] llm_calls={stats.get('llm_calls')}, "
              f"stage={stats.get('stage')}, "
              f"source={stats.get('final_source')}")
    else:
        print("  (no stats field — pre-T2 fallback)")

    # 6. JSON-serializable
    print("\n[6] JSON serialization")
    try:
        dumped = json.dumps(result, ensure_ascii=False)
        print(f"  [OK] Serializable ({len(dumped)} chars)")
    except (TypeError, ValueError) as e:
        print(f"  [FAIL] Failed: {e}")
        sys.exit(1)

    # 7. svragent package loads correctly
    print("\n[7] svragent package import")
    try:
        from svragent import WidePipeline, AnswerExtractor, answers_equal
        print(f"  [OK] svragent loaded: WidePipeline={WidePipeline is not None}, "
              f"answers_equal={answers_equal is not None}")
    except ImportError as e:
        print(f"  [FAIL] svragent import failed: {e}")
        sys.exit(1)

    # 8. answer equivalence works
    print("\n[8] answers_equal() — symbolic equivalence")
    from svragent.parser import answers_equal
    assert answers_equal("0.5", "1/2"), "0.5 should equal 1/2"
    assert answers_equal("50%", "1/2"), "50% should equal 1/2"
    assert answers_equal("2", "2.0"), "2 should equal 2.0"
    assert not answers_equal("0.5", "0.6"), "0.5 should not equal 0.6"
    print("  [OK] Fraction/decimal/percent aliases work")

    # 9. tools registry
    print("\n[9] Math tool registry")
    from svragent.tools import TOOL_REGISTRY, call_tool
    print(f"  [OK] {len(TOOL_REGISTRY)} tools registered: {', '.join(sorted(TOOL_REGISTRY.keys())[:10])}...")
    r = call_tool("add", "1,2,3")
    print(f"  [OK] add(1,2,3) = {r}")
    r = call_tool("is_prime", "17")
    print(f"  [OK] is_prime(17) = {r}")

    print("\n" + "=" * 60)
    print("All interface checks passed. [OK]")
    print("=" * 60)


# ---------------------------------------------------------------------------
# Live test (requires INTERN_API_KEY)
# ---------------------------------------------------------------------------
def check_live() -> None:
    print("=" * 60)
    print("Math-Agent-System T2 — Live Smoke Test")
    print("=" * 60)

    from llm_client import InternChatClient

    # 1. Create agent
    print("\n[1/3] Creating ReasoningAgent with real client...")
    try:
        client = InternChatClient()
        agent = ReasoningAgent(client=client)
        print(f"  [OK] Agent created (model: {client.model})")
    except Exception as e:
        print(f"  [FAIL] Failed: {e}")
        sys.exit(1)

    # 2. Solve a simple problem
    print("\n[2/3] Testing solve on simple problem...")
    result = agent.solve("计算 1 + 2 + 3 + ... + 100 的和", {"idx": 0})

    final = result.get("final_response", "")
    trace = result.get("trace", [])
    stats = result.get("stats", {})

    print(f"  final_response: {len(final)} chars")
    print(f"  trace steps: {len(trace)}")
    for t in trace:
        content_keys = list(t.get("content", {}).keys()) if isinstance(t.get("content"), dict) else "str"
        print(f"    [{t.get('step', '?')}] elapsed={t.get('elapsed_s', '?')}s  content={content_keys}")

    print(f"  stats: llm_calls={stats.get('llm_calls')}, "
          f"stage={stats.get('stage')}, "
          f"source={stats.get('final_source')}, "
          f"verification={stats.get('verification_status')}")

    # 3. JSON serialization
    print("\n[3/3] Checking JSON serialization...")
    try:
        json.dumps(result, ensure_ascii=False)
        print("  [OK] Result is JSON-serializable")
    except (TypeError, ValueError) as e:
        print(f"  [FAIL] JSON serialization failed: {e}")

    print("\n" + "=" * 60)
    print("Live smoke test complete.")


# ---------------------------------------------------------------------------
def main() -> None:
    if "--mock" in sys.argv or "--dry-run" in sys.argv:
        check_interface()
    else:
        api_key = os.environ.get("INTERN_API_KEY", "")
        if not api_key:
            print("No INTERN_API_KEY set. Running interface-only check (--mock mode).")
            print("To run live test: export INTERN_API_KEY=\"sk-...\" && python quick_test.py")
            print()
            check_interface()
        else:
            check_live()


if __name__ == "__main__":
    main()
