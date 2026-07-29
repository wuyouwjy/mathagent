#!/usr/bin/env python3
"""快速测试新版三阶段智能体"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from user_agent import ReasoningAgent
from llm_client import InternChatClient

print("1. Creating agent...")
agent = ReasoningAgent(client=InternChatClient())

print("2. Testing solve...")
r = agent.solve("What is 1+1?", {"idx": 0})

if r.get("error"):
    print(f"FAIL: {r['error']}")
elif r["final_response"]:
    print(f"OK: final_response = {r['final_response'][:200]}")
    for t in r.get("trace", []):
        print(f"  [{t['step']}] {str(t['content'])[:80]}")
else:
    print("FAIL: empty final_response")
