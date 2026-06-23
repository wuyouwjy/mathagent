# ============================================================
# tools/intern_client.py — Intern-S1 API 客户端封装
# 负责与 Intern-S1 LLM 进行所有交互
# 兼容 OpenAI API 协议，支持同步/异步调用、重试、速率限制
# ============================================================

import time
import asyncio
from typing import List, Dict, Optional, Any, Union, Callable
from functools import wraps

from openai import OpenAI, AsyncOpenAI
from openai.types.chat import ChatCompletion, ChatCompletionMessageParam
from loguru import logger

from configs.settings import get_config


# ============================================================
# 速率限制器（Rate Limiter）
# 防止 API 调用超出频率限制
# ============================================================

class RateLimiter:
    """
    简单的令牌桶速率限制器

    用法:
        limiter = RateLimiter(max_calls=60, period=60.0)  # 每分钟60次
        with limiter:
            response = client.chat(...)
    """

    def __init__(self, max_calls: int = 60, period: float = 60.0):
        """
        参数:
            max_calls: 周期内最大调用次数
            period: 时间周期（秒），默认60秒
        """
        self.max_calls = max_calls
        self.period = period
        self._tokens = max_calls
        self._last_refill = time.monotonic()
        try:
            self._lock = asyncio.Lock() if asyncio.get_running_loop() else None
        except RuntimeError:
            self._lock = None

    def _refill(self) -> None:
        """补充令牌"""
        now = time.monotonic()
        elapsed = now - self._last_refill
        new_tokens = elapsed * (self.max_calls / self.period)
        self._tokens = min(self.max_calls, self._tokens + new_tokens)
        self._last_refill = now

    def acquire(self) -> bool:
        """获取一个令牌（同步），若无令牌则等待"""
        while True:
            self._refill()
            if self._tokens >= 1:
                self._tokens -= 1
                return True
            sleep_time = (1 - self._tokens) * (self.period / self.max_calls)
            time.sleep(max(sleep_time, 0.05))

    async def aacquire(self) -> None:
        """获取一个令牌（异步）"""
        while True:
            self._refill()
            if self._tokens >= 1:
                self._tokens -= 1
                return
            sleep_time = (1 - self._tokens) * (self.period / self.max_calls)
            await asyncio.sleep(max(sleep_time, 0.05))

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, *args):
        pass

    async def __aenter__(self):
        await self.aacquire()
        return self

    async def __aexit__(self, *args):
        pass


# ============================================================
# 重试装饰器
# ============================================================

def retry_on_failure(
    max_retries: int = 3,
    base_delay: float = 1.0,
    backoff_factor: float = 2.0,
    retryable_exceptions: tuple = (Exception,)
):
    """
    失败重试装饰器（指数退避）

    参数:
        max_retries: 最大重试次数
        base_delay: 基础等待时间（秒）
        backoff_factor: 退避因子
        retryable_exceptions: 可重试的异常类型
    """
    def _is_non_retryable(exc: Exception) -> bool:
        """判断异常是否不可重试（认证/权限错误）"""
        try:
            from openai import AuthenticationError, PermissionDeniedError
            if isinstance(exc, (AuthenticationError, PermissionDeniedError)):
                return True
        except ImportError:
            pass
        # 检查错误消息中是否包含 401/403
        msg = str(exc).lower()
        if '401' in msg or '403' in msg or 'token expired' in msg or 'authentication' in msg:
            return True
        return False

    def decorator(func: Callable):
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except retryable_exceptions as e:
                    last_exception = e
                    # 认证错误不重试
                    if _is_non_retryable(e):
                        logger.error(f"[Intern-S1] 认证失败，不重试: {e}")
                        raise
                    if attempt < max_retries:
                        delay = base_delay * (backoff_factor ** attempt)
                        logger.warning(
                            f"[Intern-S1] 调用失败 (尝试 {attempt+1}/{max_retries+1}): {e}. "
                            f"{delay:.1f}秒后重试..."
                        )
                        time.sleep(delay)
                    else:
                        logger.error(f"[Intern-S1] 已达最大重试次数 {max_retries}, 最终失败: {e}")
            raise last_exception

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except retryable_exceptions as e:
                    last_exception = e
                    if _is_non_retryable(e):
                        logger.error(f"[Intern-S1] 认证失败，不重试: {e}")
                        raise
                    if attempt < max_retries:
                        delay = base_delay * (backoff_factor ** attempt)
                        logger.warning(
                            f"[Intern-S1] 异步调用失败 (尝试 {attempt+1}/{max_retries+1}): {e}. "
                            f"{delay:.1f}秒后重试..."
                        )
                        await asyncio.sleep(delay)
                    else:
                        logger.error(f"[Intern-S1] 已达最大重试次数 {max_retries}, 最终失败: {e}")
            raise last_exception

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    return decorator


# ============================================================
# Intern-S1 API 客户端
# ============================================================

class InternS1Client:
    """
    Intern-S1 API 客户端

    封装与 Intern-S1 LLM 的所有交互，提供：
    - 同步 / 异步 chat completion
    - 自动重试 + 指数退避
    - 速率限制
    - 结构化日志
    - Token 用量统计

    用法:
        client = InternS1Client()
        response = client.chat([
            {"role": "system", "content": "你是一位数学专家"},
            {"role": "user", "content": "解这个方程: x^2 + 3x - 4 = 0"}
        ])
        print(response["content"])
    """

    def __init__(self):
        """
        初始化 Intern-S1 客户端

        从全局配置中读取 API 连接参数。
        """
        config = get_config()
        api_cfg = config.intern_s1

        self.api_key = api_cfg.api_key
        self.base_url = api_cfg.api_base_url
        self.model_name = api_cfg.model_name

        # --- 请求参数 ---
        self.temperature = api_cfg.temperature
        self.max_tokens = api_cfg.max_tokens
        self.top_p = api_cfg.top_p
        self.timeout = api_cfg.timeout
        self.max_retries = api_cfg.max_retries

        # --- 速率限制器 ---
        self.rate_limiter = RateLimiter(
            max_calls=api_cfg.requests_per_minute,
            period=60.0
        )

        # --- 初始化 OpenAI 兼容客户端 ---
        self._sync_client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=self.timeout,
            max_retries=0,  # 我们自己管理重试
        )

        self._async_client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=self.timeout,
            max_retries=0,
        )

        # --- Token 用量统计 ---
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.total_calls = 0

        logger.info(
            f"[Intern-S1] 客户端已初始化: model={self.model_name}, "
            f"base_url={self.base_url}, temperature={self.temperature}"
        )

    # ============================================================
    # 同步 Chat Completion
    # ============================================================

    @retry_on_failure(
        max_retries=3,
        base_delay=1.0,
        backoff_factor=2.0,
        retryable_exceptions=(Exception,)
    )
    def chat(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        stop_sequences: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        同步 Chat Completion 调用

        参数:
            messages: 消息列表，格式 [{"role": "user", "content": "..."}]
            system_prompt: 系统提示词（可选，自动插入messages首位）
            temperature: 温度参数（可选，覆盖默认值）
            max_tokens: 最大输出token（可选，覆盖默认值）
            stop_sequences: 停止序列（可选）

        返回:
            Dict: {
                "content": str,              # 模型回复文本
                "role": "assistant",
                "model": str,                # 模型名称
                "usage": {                   # Token 用量
                    "prompt_tokens": int,
                    "completion_tokens": int,
                    "total_tokens": int,
                },
                "finish_reason": str,        # 停止原因
            }

        异常:
            TimeoutError: 请求超时
            ConnectionError: 连接失败
            Exception: 其他错误（自动重试后仍失败则抛出）
        """
        # --- 构建完整消息列表 ---
        full_messages: List[ChatCompletionMessageParam] = []

        if system_prompt:
            full_messages.append({"role": "system", "content": system_prompt})

        for msg in messages:
            full_messages.append({
                "role": msg.get("role", "user"),
                "content": msg.get("content", ""),
            })

        # --- 速率限制 ---
        with self.rate_limiter:
            logger.debug(f"[Intern-S1] 发送请求, 消息数={len(full_messages)}")

            # --- 调用 API ---
            response: ChatCompletion = self._sync_client.chat.completions.create(
                model=self.model_name,
                messages=full_messages,
                temperature=temperature if temperature is not None else self.temperature,
                max_tokens=max_tokens if max_tokens is not None else self.max_tokens,
                top_p=self.top_p,
                stop=stop_sequences,
            )

        # --- 解析响应 ---
        choice = response.choices[0]
        usage = response.usage

        # --- 更新统计 ---
        self.total_calls += 1
        if usage:
            self.total_prompt_tokens += usage.prompt_tokens
            self.total_completion_tokens += usage.completion_tokens

        logger.debug(
            f"[Intern-S1] 响应成功: "
            f"tokens(prompt={usage.prompt_tokens if usage else 'N/A'}, "
            f"completion={usage.completion_tokens if usage else 'N/A'}), "
            f"finish_reason={choice.finish_reason}"
        )

        return {
            "content": choice.message.content or "",
            "role": choice.message.role,
            "model": response.model,
            "usage": {
                "prompt_tokens": usage.prompt_tokens if usage else 0,
                "completion_tokens": usage.completion_tokens if usage else 0,
                "total_tokens": usage.total_tokens if usage else 0,
            },
            "finish_reason": choice.finish_reason,
        }

    # ============================================================
    # 异步 Chat Completion
    # ============================================================

    async def achat(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        stop_sequences: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        异步 Chat Completion 调用

        参数与同步版本 chat() 完全相同。

        返回:
            Dict: 与 chat() 相同格式的响应字典
        """
        # --- 构建完整消息列表 ---
        full_messages: List[ChatCompletionMessageParam] = []

        if system_prompt:
            full_messages.append({"role": "system", "content": system_prompt})

        for msg in messages:
            full_messages.append({
                "role": msg.get("role", "user"),
                "content": msg.get("content", ""),
            })

        # --- 速率限制 ---
        async with self.rate_limiter:
            logger.debug(f"[Intern-S1] 发送异步请求, 消息数={len(full_messages)}")

            response: ChatCompletion = await self._async_client.chat.completions.create(
                model=self.model_name,
                messages=full_messages,
                temperature=temperature if temperature is not None else self.temperature,
                max_tokens=max_tokens if max_tokens is not None else self.max_tokens,
                top_p=self.top_p,
                stop=stop_sequences,
            )

        # --- 解析响应 ---
        choice = response.choices[0]
        usage = response.usage

        self.total_calls += 1
        if usage:
            self.total_prompt_tokens += usage.prompt_tokens
            self.total_completion_tokens += usage.completion_tokens

        logger.debug(
            f"[Intern-S1] 异步响应成功: "
            f"tokens(prompt={usage.prompt_tokens if usage else 'N/A'}, "
            f"completion={usage.completion_tokens if usage else 'N/A'})"
        )

        return {
            "content": choice.message.content or "",
            "role": choice.message.role,
            "model": response.model,
            "usage": {
                "prompt_tokens": usage.prompt_tokens if usage else 0,
                "completion_tokens": usage.completion_tokens if usage else 0,
                "total_tokens": usage.total_tokens if usage else 0,
            },
            "finish_reason": choice.finish_reason,
        }

    # ============================================================
    # 结构化 JSON 输出（用于需要强格式约束的场景）
    # ============================================================

    def chat_with_json_output(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        json_schema_hint: Optional[str] = None,
        **kwargs  # 支持透传 temperature, max_tokens 等参数
    ) -> Dict[str, Any]:
        """
        请求结构化 JSON 输出

        在 system_prompt 中注入 JSON 格式约束，
        要求模型返回严格 JSON 格式。

        参数:
            messages: 消息列表
            system_prompt: 系统提示词
            json_schema_hint: JSON 格式提示（如 '请返回 {"domain": "...", "confidence": 0.95}'）

        返回:
            Dict: 与 chat() 相同格式的响应字典
        """
        import json

        # --- 增强 system prompt ---
        enhanced_system = system_prompt or ""
        if json_schema_hint:
            enhanced_system += (
                f"\n\n【重要指令】你必须严格以 JSON 格式返回结果，不要添加任何额外的解释文字。"
                f"\nJSON 格式要求：\n{json_schema_hint}"
                f"\n请确保 JSON 是有效的、可直接解析的。"
            )
        else:
            enhanced_system += (
                "\n\n【重要指令】请以有效的 JSON 格式返回结果。"
            )

        # --- 调用 API（带截断自动重试）---
        chat_kwargs = {"temperature": 0.0, **kwargs}

        # 第一次尝试
        response = self.chat(
            messages=messages,
            system_prompt=enhanced_system,
            **chat_kwargs,
        )

        # 如果输出被截断且 JSON 解析失败，翻倍 max_tokens 重试一次
        content = response["content"].strip()
        parsed = self._extract_json(content)

        if parsed is None and response.get("finish_reason") == "length":
            retry_tokens = min(chat_kwargs.get("max_tokens", self.max_tokens) * 2, 65536)
            logger.warning(
                f"[Intern-S1] 输出被截断( finish_reason=length )，"
                f"自动重试: max_tokens {chat_kwargs.get('max_tokens', self.max_tokens)} → {retry_tokens}"
            )
            chat_kwargs["max_tokens"] = retry_tokens
            response = self.chat(
                messages=messages,
                system_prompt=enhanced_system,
                **chat_kwargs,
            )
            content = response["content"].strip()
            parsed = self._extract_json(content)

        if parsed is not None:
            response["parsed_json"] = parsed
        else:
            logger.warning(
                f"[Intern-S1] JSON 解析失败, "
                f"finish_reason={response.get('finish_reason', '?')}, "
                f"原始内容前200字符: {content[:200]}"
            )
            response["parsed_json"] = None

        return response

    def _extract_json(self, content: str) -> Optional[Dict[str, Any]]:
        """
        从 LLM 返回内容中提取 JSON 对象

        按优先级尝试多种策略：
        1. 直接解析整个内容
        2. 去除 ```json ... ``` 代码块包裹后解析
        3. 正则提取第一个完整 {...} 对象
        4. 正则提取最后一个完整 {...} 对象（某些模型在JSON后加注释）

        参数:
            content: LLM 返回的原始文本

        返回:
            Optional[Dict]: 解析成功的 JSON 字典，失败返回 None
        """
        import json
        import re

        if not content:
            return None

        strategies = []

        # 策略1: 直接解析
        strategies.append(content)

        # 策略2: 去除 markdown 代码块包裹
        if content.startswith("```"):
            lines = content.split("\n")
            # 去掉第一行 (```json 或 ```)
            inner = lines[1:] if len(lines) > 1 else lines
            # 去掉最后一行 (```) 如果存在
            if inner and inner[-1].strip() == "```":
                inner = inner[:-1]
            strategies.append("\n".join(inner).strip())

        # 策略3: 正则提取第一个完整 { ... } 对象
        # 使用贪婪匹配找到从第一个 { 到对应的 }
        brace_start = content.find("{")
        if brace_start >= 0:
            depth = 0
            for i in range(brace_start, len(content)):
                if content[i] == "{":
                    depth += 1
                elif content[i] == "}":
                    depth -= 1
                    if depth == 0:
                        strategies.append(content[brace_start:i+1])
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
                        strategies.append(content[i:brace_end+1])
                        break

        # 依次尝试每种策略
        for s in strategies:
            try:
                return json.loads(s)
            except (json.JSONDecodeError, ValueError):
                continue

        return None

    # ============================================================
    # 批量并发调用
    # ============================================================

    async def batch_chat(
        self,
        batch_messages: List[List[Dict[str, str]]],
        system_prompts: Optional[List[Optional[str]]] = None,
        max_concurrency: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        批量并发 Chat Completion 调用

        参数:
            batch_messages: 批量消息列表，每个元素是一个完整的消息列表
            system_prompts: 对应的系统提示词列表（可选，长度需与batch_messages一致）
            max_concurrency: 最大并发数

        返回:
            List[Dict]: 响应列表，与输入顺序一致
        """
        if system_prompts is None:
            system_prompts = [None] * len(batch_messages)

        if len(system_prompts) != len(batch_messages):
            raise ValueError(
                f"system_prompts 长度({len(system_prompts)})与 "
                f"batch_messages 长度({len(batch_messages)})不一致"
            )

        # --- 使用信号量控制并发 ---
        semaphore = asyncio.Semaphore(max_concurrency)

        async def bounded_achat(idx: int, messages: List[Dict[str, str]], sys_prompt: Optional[str]):
            """带并发控制的异步调用"""
            async with semaphore:
                try:
                    return await self.achat(messages=messages, system_prompt=sys_prompt)
                except Exception as e:
                    logger.error(f"[Intern-S1] 批量调用 [{idx}] 失败: {e}")
                    return {
                        "content": "",
                        "role": "assistant",
                        "model": self.model_name,
                        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                        "finish_reason": "error",
                        "error": str(e),
                    }

        # --- 创建所有并发任务 ---
        tasks = [
            bounded_achat(i, msgs, sys_prompt)
            for i, (msgs, sys_prompt) in enumerate(zip(batch_messages, system_prompts))
        ]

        logger.info(
            f"[Intern-S1] 开始批量并发调用: "
            f"总数={len(tasks)}, 最大并发={max_concurrency}"
        )

        results = await asyncio.gather(*tasks, return_exceptions=False)

        success_count = sum(1 for r in results if "error" not in r)
        logger.info(
            f"[Intern-S1] 批量调用完成: "
            f"成功={success_count}/{len(results)}, "
            f"总调用次数={self.total_calls}"
        )

        return results

    # ============================================================
    # 工具方法
    # ============================================================

    def get_usage_stats(self) -> Dict[str, Any]:
        """
        获取 API 用量统计

        返回:
            Dict: 包含总调用次数、Token 用量等信息
        """
        return {
            "total_calls": self.total_calls,
            "total_prompt_tokens": self.total_prompt_tokens,
            "total_completion_tokens": self.total_completion_tokens,
            "total_tokens": self.total_prompt_tokens + self.total_completion_tokens,
            "model_name": self.model_name,
            "estimated_cost_usd": None,  # Intern-S1 定价未知时留空
        }

    def reset_usage_stats(self) -> None:
        """重置用量统计"""
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.total_calls = 0

    def close(self) -> None:
        """关闭客户端，释放连接"""
        self._sync_client.close()
        self._async_client.close()
        logger.info("[Intern-S1] 客户端已关闭")


# ============================================================
# 全局客户端单例
# ============================================================

_global_client: Optional[InternS1Client] = None


def get_intern_client() -> InternS1Client:
    """
    获取全局 InternS1 客户端单例

    返回:
        InternS1Client: 全局客户端实例
    """
    global _global_client
    if _global_client is None:
        _global_client = InternS1Client()
    return _global_client


def reset_intern_client() -> None:
    """重置全局客户端（测试用）"""
    global _global_client
    if _global_client:
        _global_client.close()
    _global_client = None


# ============================================================
# 快速调用函数（便捷接口）
# ============================================================

def intern_chat(
    user_message: str,
    system_prompt: Optional[str] = None,
    temperature: Optional[float] = None,
) -> Dict[str, Any]:
    """
    便捷函数：发送单条用户消息并获取回复

    用法:
        response = intern_chat("求解 x^2 + 2x + 1 = 0", system_prompt="你是数学专家")
        print(response["content"])

    参数:
        user_message: 用户消息文本
        system_prompt: 系统提示词（可选）
        temperature: 温度参数（可选）

    返回:
        Dict: 与 InternS1Client.chat() 相同格式
    """
    client = get_intern_client()
    return client.chat(
        messages=[{"role": "user", "content": user_message}],
        system_prompt=system_prompt,
        temperature=temperature,
    )
