"""OpenAI-compatible chat client for local testing.

Interface matches the competition platform's official client:
    client.chat(messages, temperature, max_tokens) -> str

Environment variables:
    INTERN_API_KEY      (required)  API key
    INTERN_MODEL         (optional) Model name, default intern-s2-preview
    INTERN_API_BASE      (optional) API base URL
"""

import json
import os
import time
from typing import Callable, Dict, List, Optional

import requests


DEFAULT_API_BASE = "https://chat.intern-ai.org.cn/api/v1/chat/completions"
DEFAULT_MODEL = "intern-s2-preview"


class StreamPrefixAbort(RuntimeError):
    """Raised when a streamed response is stopped by a caller-provided prefix guard."""

    def __init__(self, reason: str, partial_text: str, chat_mode: str = "streamed") -> None:
        super().__init__(reason)
        self.reason = reason
        self.partial_text = partial_text
        self.chat_mode = chat_mode


class InternChatClient:
    """OpenAI-compatible chat client for competition local testing."""

    def __init__(
        self,
        timeout: int = 1200,
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
        self.session = requests.Session()
        self.last_chat_mode = ""
        if os.environ.get("INTERN_DISABLE_PROXY", "").strip().lower() in {"1", "true", "yes"}:
            self.session.trust_env = False

    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.2,
        max_tokens: int = 12288,
        top_p: Optional[float] = None,
        stop: Optional[List[str]] = None,
        stream: bool = False,
        prefix_guard: Optional[Callable[[str], Optional[str]]] = None,
        prefix_guard_chars: int = 512,
    ) -> str:
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream,
        }
        if stop:
            payload["stop"] = stop
        if top_p is not None:
            payload["top_p"] = top_p
        headers = {
            "Content-Type": "application/json",
            "Authorization": self.authorization,
        }

        last_error = None
        for attempt in range(self.retry):
            try:
                if stream:
                    self.last_chat_mode = "streamed"
                    streamed = self._chat_stream(
                        payload=payload,
                        headers=headers,
                        prefix_guard=prefix_guard,
                        prefix_guard_chars=prefix_guard_chars,
                    )
                    if streamed:
                        self.last_chat_mode = "streamed"
                        return streamed

                    fallback_payload = dict(payload)
                    fallback_payload["stream"] = False
                    self.last_chat_mode = "empty_stream_fallback"
                    response = self._chat_once(payload=fallback_payload, headers=headers)
                    return response
                self.last_chat_mode = "non_stream"
                return self._chat_once(payload=payload, headers=headers)
            except StreamPrefixAbort as exc:
                self.last_chat_mode = exc.chat_mode
                raise
            except json.JSONDecodeError as exc:
                last_error = exc
                if attempt + 1 < self.retry:
                    time.sleep(2 ** attempt)
                    continue
                fallback_payload = dict(payload)
                fallback_payload["stream"] = False
                self.last_chat_mode = "json_error_fallback"
                response = self._chat_once(payload=fallback_payload, headers=headers)
                return response
            except Exception as exc:
                last_error = exc
                if attempt + 1 < self.retry:
                    time.sleep(2 ** attempt)

        raise RuntimeError(f"Chat completion failed after {self.retry} attempts: {last_error}")

    def _chat_once(self, payload: Dict, headers: Dict[str, str]) -> str:
        response = self.session.post(
            self.api_base,
            headers=headers,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            timeout=self.timeout,
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]

    def _chat_stream(
        self,
        payload: Dict,
        headers: Dict[str, str],
        prefix_guard: Optional[Callable[[str], Optional[str]]],
        prefix_guard_chars: int,
    ) -> str:
        chunks: List[str] = []
        guard_finished = False
        pending_json = b""
        with self.session.post(
            self.api_base,
            headers=headers,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            timeout=self.timeout,
            stream=True,
        ) as response:
            response.raise_for_status()
            for raw_line in response.iter_lines(decode_unicode=False):
                if not raw_line:
                    continue
                if isinstance(raw_line, str):
                    raw_line = raw_line.encode("utf-8")
                line = raw_line.strip()
                if line.startswith(b"data:"):
                    line = line[len(b"data:"):].strip()
                if not line or line == b"[DONE]":
                    continue
                if line.startswith(b":") or line.startswith(b"event:"):
                    continue

                candidate = pending_json + line if pending_json else line
                try:
                    data = json.loads(candidate)
                except json.JSONDecodeError:
                    pending_json = candidate
                    continue
                pending_json = b""
                choice = data.get("choices", [{}])[0]
                delta = choice.get("delta") or {}
                content = delta.get("content")
                if content is None:
                    message = choice.get("message") or {}
                    content = message.get("content")
                if not content:
                    continue

                chunks.append(content)
                partial = "".join(chunks)
                if prefix_guard and not guard_finished:
                    reason = prefix_guard(partial[:prefix_guard_chars])
                    if reason:
                        raise StreamPrefixAbort(reason, partial, "streamed")
                    if len(partial) >= prefix_guard_chars:
                        guard_finished = True

        if pending_json:
            pending_text = pending_json.decode("utf-8", errors="replace")
            raise json.JSONDecodeError("Incomplete streamed JSON event", pending_text, 0)

        return "".join(chunks)
