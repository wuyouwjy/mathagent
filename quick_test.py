#!/usr/bin/env python3
"""Quick smoke-test for the v5 ReasoningAgent.

Usage:
    export INTERN_API_KEY="sk-..."
    python quick_test.py
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from user_agent import ReasoningAgent
from llm_client import InternChatClient


def main() -> None:
    print("=" * 60)
    print("Math-Agent-System v5 — Quick Smoke Test")
    print("=" * 60)

    # 1. Create agent
    print("\n[1/3] Creating ReasoningAgent...")
    try:
        client = InternChatClient()
        agent = ReasoningAgent(client=client)
        print(f"  ✓ Agent created (model: {client.model})")
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        sys.exit(1)

    # 2. Simple test
    print("\n[2/3] Testing solve on simple problem...")
    result = agent.solve("计算 1 + 2 + 3 + ... + 100 的和", {"idx": 0})

    final = result.get("final_response", "")
    trace = result.get("trace", [])

    if final:
        print(f"  ✓ final_response: {final[:120]}")
    else:
        print("  ✗ Empty final_response")

    print(f"  trace steps: {len(trace)}")
    for t in trace:
        content = str(t.get("content", ""))[:100]
        print(f"    [{t.get('step', '?')}] {content}")

    # 3. JSON serialization check
    print("\n[3/3] Checking JSON serialization...")
    try:
        json.dumps(result, ensure_ascii=False)
        print("  ✓ Result is JSON-serializable")
    except (TypeError, ValueError) as e:
        print(f"  ✗ JSON serialization failed: {e}")

    print("\n" + "=" * 60)
    print("Smoke test complete.")


if __name__ == "__main__":
    main()
