"""官方 client 响应归一化（平台防线，移植自第三名 VeritasMath）。

平台注入的 client.chat 返回值不一定是 str——可能是 OpenAI choices dict、
content blocks 数组、bytes、嵌套 message 或带 content 属性的对象。基线方案
默认按 str 处理，一旦形态不符，下游所有解析静默失败 → 整批 0 分。

本模块在 LLMRetryWrapper 单点收口：任何 client 返回值先归一化为 str 再进图。
"""

from __future__ import annotations


def _blocks_text(blocks) -> str:
    """content blocks 数组 → 纯文本（{"type":"text","text":...} 形态）。"""
    if isinstance(blocks, str):
        return blocks
    if isinstance(blocks, bytes):
        try:
            return blocks.decode("utf-8", "ignore")
        except Exception:  # noqa: BLE001
            return ""
    if not isinstance(blocks, list):
        return ""
    parts = []
    for block in blocks:
        if isinstance(block, str):
            parts.append(block)
        elif isinstance(block, bytes):
            try:
                parts.append(block.decode("utf-8", "ignore"))
            except Exception:  # noqa: BLE001
                pass
        elif isinstance(block, dict):
            text = block.get("text") or block.get("content") or ""
            if isinstance(text, str):
                parts.append(text)
            elif isinstance(text, bytes):
                try:
                    parts.append(text.decode("utf-8", "ignore"))
                except Exception:  # noqa: BLE001
                    pass
    return "".join(parts)


def normalize_chat_response(resp) -> str:
    """把任意形态的 client.chat 返回值归一化为纯文本。永不抛异常。"""
    if resp is None:
        return ""
    if isinstance(resp, str):
        return resp
    if isinstance(resp, bytes):
        try:
            return resp.decode("utf-8", "ignore")
        except Exception:  # noqa: BLE001
            return ""
    if isinstance(resp, list):
        return _blocks_text(resp)
    if isinstance(resp, dict):
        try:
            choices = resp.get("choices") or []
            if choices and isinstance(choices[0], dict):
                message = choices[0].get("message") or choices[0]
                text = _blocks_text(message.get("content"))
                if text:
                    return text
        except Exception:  # noqa: BLE001
            pass
        for key in ("content", "text", "answer"):
            text = _blocks_text(resp.get(key))
            if text.strip():
                return text
            value = resp.get(key)
            if isinstance(value, dict):  # 嵌套 message 形态
                nested = _blocks_text(value.get("content") or value.get("text"))
                if nested.strip():
                    return nested
        if "tool_calls" in resp:  # 工具调用形态：序列化供下游提取层兜底
            try:
                import json
                return json.dumps(resp, ensure_ascii=False)[:2000]
            except Exception:  # noqa: BLE001
                return ""
        return ""
    content = getattr(resp, "content", None)  # AgentMessage 等对象形态
    text = _blocks_text(content)
    if text:
        return text
    try:
        return str(resp)
    except Exception:  # noqa: BLE001
        return ""


def chat_compatible(client, messages, temperature, max_tokens):
    """签名探测调用（平台防线）。

    平台 client 的 chat 签名未知：可能只接受 messages，或不接受关键字参数。
    按 关键字三参 → 位置三参 → 仅 messages 三级降级探测；探测结果缓存在
    client 对象上（`_veritas_chat_mode`），避免每次调用都付一次 TypeError。
    """
    mode = getattr(client, "_veritas_chat_mode", None)
    attempts = {
        "kwargs": lambda: client.chat(
            messages=messages, temperature=temperature, max_tokens=max_tokens),
        "positional": lambda: client.chat(messages, temperature, max_tokens),
        "messages_only": lambda: client.chat(messages),
    }
    if mode in attempts:
        try:
            return attempts[mode]()
        except TypeError:
            pass  # 缓存模式失效（平台热更新等），重新全量探测
    last_error = None
    for name in ("kwargs", "positional", "messages_only"):
        try:
            result = attempts[name]()
            try:
                setattr(client, "_veritas_chat_mode", name)
            except Exception:  # noqa: BLE001 - 只读对象不设缓存
                pass
            return result
        except TypeError as exc:
            last_error = exc
            continue
    # 三种形态都 TypeError：不是签名问题，是 client 内部故障，原样抛出
    raise last_error  # type: ignore[misc]
