import json
import os
import time
from typing import Dict, List

import requests

from config import CONFIG


DEFAULT_API_BASE = "https://chat.intern-ai.org.cn/api/v1/chat/completions"
DEFAULT_MODEL = CONFIG["model"]


class InternChatClient:
    """Small OpenAI-compatible chat client for the competition sample."""

    def __init__(
        self,
        timeout: int = 120,
        retry: int = 3,
    ) -> None:
        raw_api_key = os.environ.get("INTERN_API_KEY")
        if not raw_api_key:
            raise RuntimeError("Missing API key. Set INTERN_API_KEY.")
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
        thinking_mode: bool = True,
    ):
        """OpenAI-compatible chat，返回**完整 response dict**（不压成 str）。

        返回 dict 而非只取 ``choices[0].message.content``，是为了保住
        ``finish_reason`` 信号（'length' = 被 max_tokens 截断）。上游
        ``utils.llm.response_normalize.normalize_chat_response`` 负责把 dict 压成
        纯文本、``extract_finish_reason`` 负责提 finish_reason——两者都按 dict
        形态设计，这里退回 str 会让截断续写入口（reasoning 的
        ``finish_reason == 'length'`` 判断）永远拿不到信号变成死代码。
        """
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "thinking_mode": thinking_mode,
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
                return response.json()
            except Exception as exc:  # noqa: BLE001 - keep sample robust and simple.
                last_error = exc
                if attempt + 1 < self.retry:
                    time.sleep(2**attempt)

        raise RuntimeError(f"Chat completion failed after {self.retry} attempts: {last_error}")
