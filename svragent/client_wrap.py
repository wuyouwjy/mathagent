# -*- coding: utf-8 -*-
"""Thin wrapper around the platform client for uniform error handling."""

from __future__ import annotations

from typing import Any, Dict, List


class LLMCaller:
    """Call the platform-injected client with consistent error semantics.

    The competition platform provides ``client.chat(messages, temperature,
    max_tokens)``.  This wrapper normalises the return to ``str`` and
    treats transport failures as empty responses (the pipeline will
    handle them downstream).
    """

    def __init__(self, client: Any) -> None:
        self._client = client

    def __call__(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.2,
        max_tokens: int = 131072,
    ) -> str:
        try:
            resp = self._client.chat(
                messages=messages,
                temperature=float(temperature),
                max_tokens=int(max_tokens),
            )
        except Exception:
            return ""

        # Normalise the response to str.
        if isinstance(resp, str):
            return resp

        if isinstance(resp, dict):
            for key in ("content", "message", "text", "response", "output"):
                val = resp.get(key)
                if isinstance(val, str) and val.strip():
                    return val
            choices = resp.get("choices", [])
            if choices:
                msg = (
                    choices[0].get("message", {})
                    if isinstance(choices[0], dict)
                    else {}
                )
                val = msg.get("content", "")
                if isinstance(val, str) and val.strip():
                    return val
            return str(resp)

        # Object (e.g. OpenAI SDK ChatCompletion)
        for path in (
            lambda o: o.content,
            lambda o: o.message.content,
            lambda o: o.choices[0].message.content,
            lambda o: o.text,
        ):
            try:
                val = path(resp)
                if isinstance(val, str) and val.strip():
                    return val
            except (AttributeError, IndexError, TypeError):
                pass

        s = str(resp)
        return s if not s.startswith("<") else ""
