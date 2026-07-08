# ============================================================
# user_agent.py — 比赛入口文件（Challenge Cup 2026）
#
# 必须暴露 ReasoningAgent 类，平台通过以下方式调用：
#   from user_agent import ReasoningAgent
#   agent = ReasoningAgent(client=official_client)
#   result = agent.solve(problem="...", metadata={"idx": 0})
#
# 返回格式（严格按比赛规范）：
#   成功: {"final_response": "答案", "trace": [...]}
#   失败: {"final_response": "", "error": {"type": "...", "message": "..."}, "trace": []}
# ============================================================

import sys
import os
import re
import traceback
from typing import Dict, List, Optional, Any

# 确保项目根目录在 sys.path 中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from loguru import logger


class ReasoningAgent:
    """
    数学推理智能体 — 比赛入口

    封装完整的 Math-Agent-System：
    - 多领域分类（18 个数学领域）
    - 6 个 Solver 专家 + 领域 Skills
    - LangGraph 工作流编排（解析→分类→RAG→求解→验证→反思）
    - 两层缓存（精确 + 语义）
    - 反思重试机制

    用法:
        # 比赛模式（平台注入 client）
        agent = ReasoningAgent(client=platform_client)
        result = agent.solve(problem="求解 x^2 - 5x + 6 = 0", metadata={"idx": 0})
    """

    def __init__(self, client=None, config=None, *args, **kwargs):
        """
        初始化推理智能体

        参数:
            client: 平台提供的 LLM 客户端（可选）
                   需实现 chat(messages, temperature, max_tokens) -> str
            config: Agent 配置字典（可选）
        """
        self._client = client
        self._config = config or {}
        self._workflow = None
        self._initialized = False
        self._last_raw_result = None  # 最近一次求解的原始内部结果

        # 如果提供了平台 client，注入为适配器
        if client is not None:
            self._setup_platform_client(client)

        logger.info("[ReasoningAgent] 智能体已初始化")

    def _setup_platform_client(self, client) -> None:
        """将平台 client 注入系统"""
        try:
            from tools.platform_adapter import PlatformClientAdapter, set_platform_adapter
            adapter = PlatformClientAdapter(client)
            set_platform_adapter(adapter)
            logger.info("[ReasoningAgent] 平台 client 已注入")
        except Exception as e:
            logger.warning(f"[ReasoningAgent] 平台 client 注入失败: {e}")

    def _ensure_initialized(self) -> None:
        """延迟初始化工作流（首次调用 solve 时）"""
        if self._initialized:
            return

        from tools.platform_adapter import is_using_platform_client
        if not is_using_platform_client() and self._client is None:
            logger.info("[ReasoningAgent] 尝试本地模式（从环境变量创建 client）")
            try:
                from llm_client import InternChatClient as LocalClient
                local = LocalClient()
                self._setup_platform_client(local)
            except RuntimeError as e:
                logger.warning(f"[ReasoningAgent] 本地模式不可用: {e}，尝试内置 client")
            except ImportError:
                logger.info("[ReasoningAgent] 使用内置 InternS1Client")

        from graph.workflow import MathAgentWorkflow

        max_retries = self._config.get("max_reflection_count", 3)
        enable_rag = self._config.get("enable_rag", True)

        self._workflow = MathAgentWorkflow(
            enable_rag=enable_rag,
            max_reflection_count=max_retries,
        )
        self._initialized = True
        logger.info("[ReasoningAgent] 工作流已就绪")

    # ============================================================
    # 比赛标准接口
    # ============================================================

    def get_last_detail(self) -> Optional[Dict]:
        """获取最近一次求解的原始内部结果（含 reasoning_steps, methods_used 等详情）"""
        return self._last_raw_result

    @staticmethod
    def normalize_input(user_input: str) -> Dict:
        """
        将用户输入标准化为比赛格式

        支持两种输入：
        1. 普通人读的中文问题："求解 x^2 - 5x + 6 = 0"
           → {"problem": "求解 x^2 - 5x + 6 = 0", "idx": 0}
        2. 已经是 JSON 格式的字符串
           → 解析为 dict

        参数:
            user_input: 用户输入的文本

        返回:
            Dict: {"problem": "...", "idx": N}
        """
        import json
        user_input = user_input.strip()

        # 尝试解析为 JSON
        if user_input.startswith("{"):
            try:
                data = json.loads(user_input)
                return {
                    "problem": data.get("problem", data.get("question_text", "")),
                    "idx": data.get("idx", 0),
                    "subject": data.get("subject", ""),
                }
            except json.JSONDecodeError:
                pass

        # 普通文本 → 比赛格式
        return {
            "problem": user_input,
            "idx": 0,
        }

    def solve(self, problem: str, metadata: Dict) -> Dict:
        """
        求解数学问题 — 比赛标准接口

        参数:
            problem: 数学题题面文本
            metadata: 题目元信息字典（至少包含 idx）

        返回（成功）:
            {
                "final_response": "最终答案（非空字符串）",
                "trace": [
                    {"step": "plan", "content": "分析题意..."},
                    {"step": "model_call", "content": "模型调用摘要..."},
                    {"step": "finalize", "content": "最终答案提取..."}
                ]
            }

        返回（失败）:
            {
                "final_response": "",
                "error": {"type": "RuntimeError", "message": "错误信息"},
                "trace": []
            }
        """
        idx = metadata.get("idx", 0)

        try:
            self._ensure_initialized()

            logger.info(f"[ReasoningAgent] 开始求解 idx={idx}: {problem[:100]}...")

            # ---- 阶段1: plan ----
            trace = []
            trace.append({
                "step": "plan",
                "content": self._build_plan_content(problem)
            })

            # ---- 阶段2: model_call ----
            # 调用工作流求解
            result = self._workflow.solve(
                question_text=problem,
                question_id=f"q_{idx}",
                verbose=False,
            )
            self._last_raw_result = result  # 保存原始结果供 get_last_detail() 使用

            # 检测工作流层面的失败（内部异常被捕获但返回了错误结果）
            error_msg = self._detect_workflow_error(result)
            if error_msg:
                logger.error(f"[ReasoningAgent] 工作流求解失败 idx={idx}: {error_msg}")
                return {
                    "final_response": "",
                    "error": {"type": "WorkflowError", "message": error_msg},
                    "trace": [],
                }

            # 记录模型调用摘要
            trace.append({
                "step": "model_call",
                "content": self._build_model_call_content(result)
            })

            # ---- 阶段3: finalize ----
            # 提取最终答案
            final_response = self._extract_final_response(result)

            trace.append({
                "step": "finalize",
                "content": f"领域: {result.get('domain', 'unknown')}, "
                           f"方法: {', '.join(result.get('methods_used', [])[:5]) or '无'}, "
                           f"验证: {'通过' if result.get('verification', {}).get('is_correct') else '未通过'}, "
                           f"缓存: {'是' if result.get('from_cache') else '否'}"
            })

            # 确保 final_response 非空
            if not final_response or not final_response.strip():
                final_response = self._extract_fallback_answer(result)

            logger.info(f"[ReasoningAgent] 求解完成 idx={idx}: {final_response[:100]}...")

            return {
                "final_response": final_response.strip(),
                "trace": trace,
            }

        except Exception as e:
            logger.error(f"[ReasoningAgent] 求解异常 idx={idx}: {e}")
            traceback.print_exc()

            # 比赛规范：失败时 final_response 为空字符串
            return {
                "final_response": "",
                "error": {
                    "type": type(e).__name__,
                    "message": str(e),
                },
                "trace": [],
            }

    def _detect_workflow_error(self, result: Dict) -> str:
        """
        检测工作流返回的结果是否包含错误

        工作流内部有 try/except，异常可能被捕获并转为错误结果。
        此方法检查结果是否表示实际失败。

        返回: 错误信息字符串，如果结果正常则返回空字符串
        """
        # 检查 final_answer 中的失败标记
        final_answer = result.get("final_answer", "")
        solver_output = result.get("solver_output", {})
        solver_answer = solver_output.get("final_answer", "") if solver_output else ""

        error_markers = ["求解失败", "异常", "错误:", "Error:", "工作流异常"]

        for text in [final_answer, solver_answer]:
            for marker in error_markers:
                if marker in str(text):
                    # 提取错误消息
                    return str(text)[:500]

        # 检查 verification 中的错误
        verification = result.get("verification", {})
        if verification.get("check_method") == "workflow_exception":
            return verification.get("error_details", "工作流执行异常")

        # 检查 solver 错误
        if solver_output and solver_output.get("error"):
            return str(solver_output["error"])[:500]

        return ""

    # ============================================================
    # 答案提取
    # ============================================================

    def _extract_final_response(self, result: Dict) -> str:
        """
        从求解结果中提取最终答案

        优先级：
        1. 缓存命中 → 直接从缓存的 final_answer 提取
        2. solver_output.final_answer
        3. final_answer 顶层字段
        4. reasoning_steps 最后一步的 result/description
        """
        # 缓存命中的结果
        if result.get("from_cache"):
            cached_final = result.get("final_answer", "")
            if cached_final and cached_final != "无答案":
                return self._strip_reasoning(cached_final)

        # solver_output 中的答案
        solver_output = result.get("solver_output", {})
        if solver_output:
            answer = solver_output.get("final_answer", "")
            if answer and answer != "无答案" and "求解失败" not in answer:
                return self._strip_reasoning(answer)

        # 顶层 final_answer
        answer = result.get("final_answer", "")
        if answer and answer != "无答案":
            return self._strip_reasoning(answer)

        # 从推理步骤中提取
        steps = result.get("reasoning_steps", [])
        if not steps:
            steps = solver_output.get("reasoning_steps", [])

        for step in reversed(steps):
            if isinstance(step, dict):
                ans = step.get("result") or step.get("formula") or ""
                if ans and len(ans) > 1:
                    return self._strip_reasoning(str(ans))

        return ""

    def _extract_fallback_answer(self, result: Dict) -> str:
        """最后的兜底提取"""
        # 尝试 raw_llm_response
        raw = result.get("solver_output", {}).get("raw_llm_response", "")
        if raw:
            return raw[:2000]
        # 尝试 educational_hint
        hint = result.get("educational_hint", "")
        if hint:
            return hint[:2000]
        return "求解完成但无法提取答案"

    def _strip_reasoning(self, text: str) -> str:
        """
        从包含推理过程的文本中提取纯答案

        策略：
        1. 如果文本较短（≤500字符），直接返回
        2. 查找"答案"/"最终"/"answer"/"final"等关键字，取之后的内容
        3. 取最后几行
        """
        if not text:
            return ""
        text = text.strip()
        if len(text) <= 500:
            return text

        # 按关键字切分
        patterns = [
            r'(?:最终答案|答案[：:为是]|final answer[：: is]|因此[，,]|所以[，,]|综上[，,]|故[：:])',
        ]
        for pat in patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                after = text[m.start():].strip()
                # 去掉关键字本身
                after = re.sub(r'^(?:最终答案|答案[：:为是]?|final answer[：: is]?|因此[，,]?|所以[，,]?|综上[，,]?|故[：:]?)\s*', '', after)
                if 10 <= len(after) <= 1000:
                    return after.strip()

        # 取最后 5 行
        lines = text.split("\n")
        if len(lines) > 5:
            return "\n".join(lines[-5:]).strip()

        return text[:1000]

    # ============================================================
    # Trace 构建
    # ============================================================

    def _build_plan_content(self, problem: str) -> str:
        """构建 plan 阶段的 trace 内容"""
        return f"题目: {problem[:200]}"

    def _build_model_call_content(self, result: Dict) -> str:
        """构建 model_call 阶段的 trace 内容"""
        parts = []

        domain = result.get("domain", "unknown")
        parts.append(f"领域分类: {domain}")

        if result.get("from_cache"):
            sim = result.get("cache_similarity", 0)
            parts.append(f"缓存命中 (相似度={sim:.4f})")

        retry = result.get("retry_count", 0)
        if retry > 0:
            parts.append(f"反思重试: {retry} 次")

        methods = result.get("methods_used", [])
        if methods:
            parts.append(f"方法: {', '.join(methods[:5])}")

        steps = result.get("reasoning_steps", [])
        if not steps:
            steps = result.get("solver_output", {}).get("reasoning_steps", [])
        if steps:
            parts.append(f"推理步骤数: {len(steps)}")

        verification = result.get("verification", {})
        if verification:
            parts.append(
                f"验证: {'通过' if verification.get('is_correct') else '未通过'}"
                f"(置信度={verification.get('confidence', 0):.2f})"
            )

        return "; ".join(parts) if parts else "求解完成"


# ============================================================
# 本地测试入口
# ============================================================

if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Math Reasoning Agent - 本地测试")
    parser.add_argument("--problem", "-p", type=str, required=True, help="数学问题文本")
    parser.add_argument("--idx", type=int, default=0, help="题目编号")
    parser.add_argument("--json", action="store_true", help="以 JSON 格式输出")
    args = parser.parse_args()

    agent = ReasoningAgent()
    result = agent.solve(
        problem=args.problem,
        metadata={"idx": args.idx},
    )

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("\n" + "=" * 60)
        print(f"idx: {args.idx}")
        if result.get("error"):
            print(f"status: error")
            print(f"error: {result['error']['type']}: {result['error']['message']}")
        else:
            print(f"status: success")
            print(f"final_response: {result['final_response']}")
            print(f"trace: {len(result.get('trace', []))} 步")
            for t in result.get("trace", []):
                content = t.get("content", "")
                if isinstance(content, dict):
                    content = json.dumps(content, ensure_ascii=False)[:150]
                print(f"  [{t['step']}] {str(content)[:150]}")
        print("=" * 60)
