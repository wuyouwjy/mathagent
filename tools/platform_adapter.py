# ============================================================
# tools/platform_adapter.py — 平台客户端适配器
# 将比赛平台提供的简单 client (chat() -> str)
# 适配为系统内部期望的 InternS1Client 接口 (chat() -> dict)
# ============================================================

import json
import re
from typing import Dict, Any, List, Optional


class PlatformClientAdapter:
    """
    将比赛平台的 client.chat(messages) -> str 接口
    适配为系统内部期望的完整接口

    平台 client 接口:
        content: str = client.chat(
            messages=[{"role": "user", "content": "..."}],
            temperature=0.2,
            max_tokens=4096,
        )

    适配后提供与 InternS1Client 一致的接口:
        response = adapter.chat(messages, system_prompt="...")
        response["content"]  # str
        response["parsed_json"]  # dict (for chat_with_json_output)

    用法:
        # 比赛模式
        from llm_client import InternChatClient
        platform_client = InternChatClient()
        adapter = PlatformClientAdapter(platform_client)

        # 注入到系统
        set_platform_adapter(adapter)

        # 之后所有 LLM 调用都通过适配器
    """

    def __init__(self, platform_client):
        """
        参数:
            platform_client: 比赛平台提供的 client（有 chat(messages, temperature, max_tokens) 方法）
        """
        self._client = platform_client
        self.total_calls = 0
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0

    def chat(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        stop_sequences: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        同步 Chat Completion（适配后接口）

        参数:
            messages: 消息列表 [{"role": "user", "content": "..."}]
            system_prompt: 系统提示词（自动插入 messages 首位）
            temperature: 温度参数
            max_tokens: 最大输出 token
            stop_sequences: 停止序列（暂未使用）

        返回:
            Dict: {"content": str, "role": "assistant", "model": str, "usage": dict, "finish_reason": str}
        """
        # 构建完整消息列表
        full_messages = []
        if system_prompt:
            full_messages.append({"role": "system", "content": system_prompt})
        full_messages.extend(messages)

        # 调用平台 client
        content = self._client.chat(
            messages=full_messages,
            temperature=temperature if temperature is not None else 0.1,
            max_tokens=max_tokens if max_tokens is not None else 16384,
        )

        self.total_calls += 1

        return {
            "content": content or "",
            "role": "assistant",
            "model": getattr(self._client, 'model', 'unknown'),
            "usage": {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
            },
            "finish_reason": "stop",
        }

    def chat_with_json_output(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        json_schema_hint: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        请求结构化 JSON 输出

        在 system_prompt 中注入 JSON 格式约束，
        并自动从返回内容中提取 JSON。

        参数:
            messages: 消息列表
            system_prompt: 系统提示词
            json_schema_hint: JSON 格式提示

        返回:
            Dict: 与 chat() 相同格式，额外包含 parsed_json 字段
        """
        # 增强 system prompt
        enhanced_system = system_prompt or ""
        if json_schema_hint:
            enhanced_system += (
                f"\n\n【重要指令】你必须严格以 JSON 格式返回结果，不要添加任何额外的解释文字。"
                f"\nJSON 格式要求：\n{json_schema_hint}"
                f"\n请确保 JSON 是有效的、可直接解析的。"
            )
        else:
            enhanced_system += "\n\n【重要指令】请以有效的 JSON 格式返回结果。"

        # 第一次调用
        temperature = kwargs.pop("temperature", 0.0)
        max_tokens = kwargs.pop("max_tokens", 16384)

        response = self.chat(
            messages=messages,
            system_prompt=enhanced_system,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        content = response["content"].strip()
        parsed = self._extract_json(content)

        # 确保 parsed_json 始终是 dict（不是 None），避免后续代码 None.get() 报错
        response["parsed_json"] = parsed if parsed is not None else {}

        return response

    def _extract_json(self, content: str) -> Optional[Dict[str, Any]]:
        """从 LLM 返回内容中提取 JSON 对象"""
        if not content:
            return None

        strategies = []

        # 策略1: 直接解析
        strategies.append(content)

        # 策略2: 去除 markdown 代码块包裹
        if content.startswith("```"):
            lines = content.split("\n")
            inner = lines[1:] if len(lines) > 1 else lines
            if inner and inner[-1].strip() == "```":
                inner = inner[:-1]
            strategies.append("\n".join(inner).strip())

        # 策略3: 正则提取第一个完整 { ... } 对象
        brace_start = content.find("{")
        if brace_start >= 0:
            depth = 0
            for i in range(brace_start, len(content)):
                if content[i] == "{":
                    depth += 1
                elif content[i] == "}":
                    depth -= 1
                    if depth == 0:
                        strategies.append(content[brace_start:i + 1])
                        break

        # 策略4: 正则提取最后一个 { ... } 对象
        brace_end = content.rfind("}")
        if brace_end >= 0:
            depth = 0
            for i in range(brace_end, -1, -1):
                if content[i] == "}":
                    depth += 1
                elif content[i] == "{":
                    depth -= 1
                    if depth == 0:
                        strategies.append(content[i:brace_end + 1])
                        break

        for s in strategies:
            try:
                return json.loads(s)
            except (json.JSONDecodeError, ValueError):
                continue

        return None

    def get_usage_stats(self) -> Dict[str, Any]:
        """获取 API 用量统计"""
        return {
            "total_calls": self.total_calls,
            "total_prompt_tokens": self.total_prompt_tokens,
            "total_completion_tokens": self.total_completion_tokens,
            "total_tokens": self.total_prompt_tokens + self.total_completion_tokens,
            "model_name": getattr(self._client, 'model', 'unknown'),
            "estimated_cost_usd": None,
        }

    def close(self) -> None:
        """关闭客户端"""
        if hasattr(self._client, 'close'):
            self._client.close()


# ============================================================
# 全局适配器管理
# ============================================================

_global_adapter: Optional[PlatformClientAdapter] = None


def set_platform_adapter(adapter: PlatformClientAdapter) -> None:
    """设置全局平台适配器（比赛模式）"""
    global _global_adapter
    _global_adapter = adapter


def get_platform_adapter() -> Optional[PlatformClientAdapter]:
    """获取全局平台适配器"""
    return _global_adapter


def is_using_platform_client() -> bool:
    """是否使用平台提供的客户端"""
    return _global_adapter is not None
