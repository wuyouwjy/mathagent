# ============================================================
# graph/workflow.py — 工作流运行器
# 提供同步/异步/批量三种运行模式
# 是外部调用系统的入口点
# ============================================================

import time
import json
import os
from typing import Dict, Any, Optional, List
from loguru import logger

from schemas.workflow_state import create_initial_state, get_state_summary
from graph.graph_builder import build_math_agent_graph


# ============================================================
# MathAgentWorkflow — 工作流运行器类
# ============================================================

class MathAgentWorkflow:
    """
    数学 Agent 工作流运行器

    封装 LangGraph 图的创建和执行，提供简洁的 API。

    用法:
        runner = MathAgentWorkflow()
        result = runner.solve("求解方程 x^2 + 3x - 4 = 0", question_id="q001")
        print(result["final_answer"])
    """

    def __init__(
        self,
        enable_rag: bool = True,
        enable_checkpoint: bool = False,
        max_reflection_count: int = 3,
    ):
        """
        初始化工作流运行器

        参数:
            enable_rag: 是否启用 RAG 检索
            enable_checkpoint: 是否启用检查点
            max_reflection_count: 最大反思重试次数
        """
        self.enable_rag = enable_rag
        self.enable_checkpoint = enable_checkpoint
        self.max_reflection_count = max_reflection_count

        # 构建并编译图
        logger.info("[Workflow] 初始化 MathAgentWorkflow...")
        self._graph = build_math_agent_graph(
            enable_rag=enable_rag,
            enable_checkpoint=enable_checkpoint,
        )
        logger.info("[Workflow] 工作流初始化完成")

    # ============================================================
    # 单题求解（同步）
    # ============================================================

    def solve(
        self,
        question_text: str,
        question_id: Optional[str] = None,
        verbose: bool = True,
    ) -> Dict[str, Any]:
        """
        求解单道数学题（同步）

        参数:
            question_text: 问题文本
            question_id: 题目ID（可选，不提供则自动生成）
            verbose: 是否打印详细日志

        返回:
            Dict: 完整的 MathSolutionOutput 字典
        """
        import uuid

        if question_id is None:
            question_id = f"q_{uuid.uuid4().hex[:8]}"

        logger.info(f"═══════════════════════════════════════════")
        logger.info(f"[Workflow] 开始求解: id={question_id}")
        logger.info(f"[Workflow] 问题: {question_text[:100]}...")
        logger.info(f"═══════════════════════════════════════════")

        total_start = time.time()

        # --- 创建初始状态 ---
        initial_state = create_initial_state(
            question_id=question_id,
            question_text=question_text,
            max_reflection_count=self.max_reflection_count,
        )

        # --- 运行图 ---
        try:
            if verbose:
                logger.info("[Workflow] 执行 LangGraph 工作流...")

            # LangGraph invoke — 执行整个图直到 END
            final_state = self._graph.invoke(
                initial_state,
                config={"configurable": {"thread_id": question_id}},
            )

            # 提取最终输出
            final_output = final_state.get("final_output", {})

        except Exception as e:
            logger.error(f"[Workflow] 工作流执行异常: {e}")
            import traceback
            traceback.print_exc()

            # 构建错误输出
            final_output = {
                "question_id": question_id,
                "domain": "unknown",
                "final_answer": f"工作流异常: {str(e)}",
                "reasoning_steps": [],
                "methods_used": [],
                "verification": {
                    "is_correct": False,
                    "confidence": 0.0,
                    "check_method": "workflow_exception",
                    "error_details": str(e),
                },
                "educational_hint": "系统运行异常，请检查日志。",
                "computation_time_ms": 0,
                "retry_count": 0,
            }

        # --- 记录耗时 ---
        total_elapsed = (time.time() - total_start) * 1000  # 转换为毫秒
        if "computation_time_ms" in final_output:
            final_output["computation_time_ms"] = total_elapsed

        # --- 保存结果到文件 ---
        self._save_result(final_output, question_id)

        # --- 打印摘要 ---
        if verbose:
            self._print_result_summary(final_output, total_elapsed)

        return final_output

    # ============================================================
    # 批量求解
    # ============================================================

    def solve_batch(
        self,
        questions: List[Dict[str, str]],
        verbose: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        批量求解多道数学题

        参数:
            questions: 问题列表，每项为 {"question_id": "...", "question_text": "..."}
            verbose: 是否打印进度

        返回:
            List[Dict]: 求解结果列表
        """
        total = len(questions)
        logger.info(f"[Workflow] 开始批量求解: 共 {total} 题")

        results = []
        total_start = time.time()

        for i, q in enumerate(questions):
            qid = q.get("question_id", f"batch_{i:04d}")
            qtext = q.get("question_text", "")

            if verbose:
                logger.info(f"\n{'='*50}")
                logger.info(f"[Batch] 进度: {i+1}/{total} — {qid}")
                logger.info(f"{'='*50}")

            result = self.solve(
                question_text=qtext,
                question_id=qid,
                verbose=False,  # 单题详细日志关闭
            )
            results.append(result)

            if verbose:
                verification = result.get("verification", {})
                logger.info(
                    f"[Batch] {qid}: domain={result.get('domain', '?')}, "
                    f"correct={verification.get('is_correct', '?')}, "
                    f"confidence={verification.get('confidence', 0):.2f}"
                )

        total_elapsed = (time.time() - total_start) * 1000

        # --- 汇总统计 ---
        solved_count = sum(
            1 for r in results
            if r.get("verification", {}).get("is_correct", False)
        )
        avg_conf = sum(
            r.get("verification", {}).get("confidence", 0)
            for r in results
        ) / max(total, 1)

        logger.info(f"\n{'='*60}")
        logger.info(f"[Batch] 批量求解完成!")
        logger.info(f"  总题数: {total}")
        logger.info(f"  通过验证: {solved_count}")
        logger.info(f"  未通过: {total - solved_count}")
        logger.info(f"  平均置信度: {avg_conf:.4f}")
        logger.info(f"  总耗时: {total_elapsed/1000:.1f}s")
        logger.info(f"  平均每题: {total_elapsed/total/1000:.2f}s")
        logger.info(f"{'='*60}")

        # --- 保存批量结果 ---
        self._save_batch_results(results, total_elapsed)

        return results

    # ============================================================
    # 异步求解（可选）
    # ============================================================

    async def solve_async(
        self,
        question_text: str,
        question_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        求解单道数学题（异步）

        参数:
            question_text: 问题文本
            question_id: 题目ID

        返回:
            Dict: 完整的 MathSolutionOutput 字典
        """
        import uuid
        import asyncio

        if question_id is None:
            question_id = f"q_{uuid.uuid4().hex[:8]}"

        # 在 executor 中运行同步图（LangGraph 的 ainvoke 也可用）
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None,
            lambda: self.solve(question_text, question_id, verbose=False)
        )
        return result

    # ============================================================
    # 辅助方法
    # ============================================================

    def _save_result(self, result: Dict[str, Any], question_id: str) -> None:
        """保存单题结果到文件"""
        try:
            output_dir = "./outputs/results"
            os.makedirs(output_dir, exist_ok=True)
            filepath = os.path.join(output_dir, f"{question_id}.json")
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            logger.debug(f"[Workflow] 结果已保存: {filepath}")
        except Exception as e:
            logger.warning(f"[Workflow] 保存结果失败: {e}")

    def _save_batch_results(
        self, results: List[Dict[str, Any]], total_time_ms: float
    ) -> None:
        """保存批量结果汇总"""
        try:
            output_dir = "./outputs/results"
            os.makedirs(output_dir, exist_ok=True)

            summary = {
                "total_questions": len(results),
                "solved_count": sum(
                    1 for r in results
                    if r.get("verification", {}).get("is_correct", False)
                ),
                "failed_count": sum(
                    1 for r in results
                    if not r.get("verification", {}).get("is_correct", False)
                ),
                "avg_confidence": sum(
                    r.get("verification", {}).get("confidence", 0)
                    for r in results
                ) / max(len(results), 1),
                "total_time_ms": total_time_ms,
                "avg_time_per_question_ms": total_time_ms / max(len(results), 1),
                "results": results,
            }

            filepath = os.path.join(output_dir, "batch_summary.json")
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(summary, f, ensure_ascii=False, indent=2)
            logger.info(f"[Workflow] 批量结果已保存: {filepath}")
        except Exception as e:
            logger.warning(f"[Workflow] 保存批量结果失败: {e}")

    def _print_result_summary(
        self, result: Dict[str, Any], elapsed_ms: float
    ) -> None:
        """打印求解结果摘要"""
        verification = result.get("verification", {})
        logger.info(f"\n{'─'*50}")
        logger.info(f"📋 求解结果摘要")
        logger.info(f"{'─'*50}")
        logger.info(f"  题目ID:    {result.get('question_id', '?')}")
        logger.info(f"  领域:      {result.get('domain', '?')}")
        logger.info(f"  最终答案:  {str(result.get('final_answer', ''))[:80]}")
        logger.info(f"  方法:      {result.get('methods_used', [])}")
        logger.info(f"  推理步骤:  {len(result.get('reasoning_steps', []))}步")
        logger.info(f"  验证通过:  {verification.get('is_correct', False)}")
        logger.info(f"  置信度:    {verification.get('confidence', 0):.4f}")
        logger.info(f"  重试次数:  {result.get('retry_count', 0)}")
        logger.info(f"  耗时:      {elapsed_ms:.0f}ms")
        logger.info(f"{'─'*50}\n")


# ============================================================
# 便捷函数
# ============================================================

def create_default_workflow() -> MathAgentWorkflow:
    """
    创建带有默认配置的工作流运行器

    返回:
        MathAgentWorkflow: 配置好的运行器
    """
    return MathAgentWorkflow(
        enable_rag=True,
        enable_checkpoint=False,
        max_reflection_count=3,
    )
