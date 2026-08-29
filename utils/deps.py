import logging
from dataclasses import dataclass, field
from typing import Any, Optional

@dataclass
class Deps:
    client: Any
    skills_loader: Any = None
    mcp_client: Any = None
    token_budget: Any = None
    #: Per-problem wall-clock budget (utils.time_budget.TimeBudget). Optional so
    #: unit tests can omit it; every consumer treats None as "unbounded".
    time_budget: Any = None
    #: 题库检索器（utils.retrieval.TfidfRetriever）。Optional 以便单测省略；
    #: 检索节点对 None 一律降级为"无参考示例"。
    retriever: Any = None
    logger: logging.Logger = field(default_factory=lambda: logging.getLogger("math_agent"))

def get_deps(config: dict) -> "Deps":
    return config["configurable"]["deps"]

class MockClient:
    """Test client that returns preset responses in order."""
    def __init__(self, responses=None):
        self.responses = list(responses) if responses else []
        self.calls = []
    def chat(self, messages, temperature=0.2, max_tokens=4096):
        self.calls.append({"messages": messages, "temperature": temperature, "max_tokens": max_tokens})
        if self.responses:
            return self.responses.pop(0)
        return "mock response"
