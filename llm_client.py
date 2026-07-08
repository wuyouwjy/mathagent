# ============================================================
# llm_client.py — 本地测试用 LLM 客户端
# 与比赛平台提供的 InternChatClient 接口一致
# 用于本地调试，正式评测时平台会注入官方 client
# ============================================================

import json
import os
import time
from typing import Dict, List

import requests


DEFAULT_API_BASE = "https://chat.intern-ai.org.cn/api/v1/chat/completions"
DEFAULT_MODEL = "intern-s2-preview"


class InternChatClient:
    """OpenAI-compatible chat client for competition local testing.

    接口与比赛平台提供的官方 client 一致：
        client.chat(messages, temperature, max_tokens) -> str

    本地使用通过环境变量配置：
        export INTERN_API_KEY="sk-..."
        export INTERN_MODEL="intern-s2-preview"      # 可选
        export INTERN_API_BASE="https://..."          # 可选
    """

    def __init__(self, timeout: int = 120, retry: int = 3) -> None:
        raw_api_key = os.environ.get("INTERN_API_KEY")
        if not raw_api_key:
            raise RuntimeError(
                "Missing API key. Set INTERN_API_KEY environment variable.\n"
                "Example: export INTERN_API_KEY='sk-...'"
            )
        self.authorization = (
            raw_api_key if raw_api_key.startswith("Bearer ") else f"Bearer {raw_api_key}"
        )
        self.api_base = os.environ.get("INTERN_API_BASE", DEFAULT_API_BASE)
        self.model = os.environ.get("INTERN_MODEL", DEFAULT_MODEL)
        self.timeout = timeout
        self.retry = retry

    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.2,
        max_tokens: int = 4096,
    ) -> str:
        """发送聊天请求，返回模型回复文本。

        参数:
            messages: 消息列表 [{"role": "user", "content": "..."}]
            temperature: 温度参数
            max_tokens: 最大输出 token

        返回:
            str: 模型回复内容
        """
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": self.authorization,
        }

        last_error = None
        for attempt in range(self.retry):
            try:
                response = requests.post(
                    self.api_base,
                    headers=headers,
                    data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                    timeout=self.timeout,
                )
                response.raise_for_status()
                data = response.json()
                return data["choices"][0]["message"]["content"]
            except Exception as exc:
                last_error = exc
                if attempt + 1 < self.retry:
                    time.sleep(2 ** attempt)

        raise RuntimeError(
            f"Chat completion failed after {self.retry} attempts: {last_error}"
        )
