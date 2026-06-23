# ============================================================
# api/benchmark.py — Benchmark 评测接口
# ============================================================
import os
import json
import time
import uuid
import threading
from typing import Dict, Any
from fastapi import APIRouter, HTTPException
from loguru import logger

from .schemas import BenchmarkStartRequest, BenchmarkStatus, BenchmarkResult
from schemas.math_domains import list_all_domains

router = APIRouter()

# Benchmark 运行状态 (全局)
_benchmark_state: Dict[str, Any] = {
    "running": False,
    "progress": 0,
    "total": 112,
    "solved": 0,
    "failed": 0,
    "elapsed_seconds": 0.0,
    "estimated_remaining_seconds": None,
    "domain_accuracy": {},
    "current_question": None,
    "results": [],
    "thread": None,
}


@router.get("/benchmark/status", response_model=BenchmarkStatus)
async def get_benchmark_status():
    """获取当前 Benchmark 运行状态"""
    return BenchmarkStatus(
        running=_benchmark_state["running"],
        progress=_benchmark_state["progress"],
        total=_benchmark_state["total"],
        solved=_benchmark_state["solved"],
        failed=_benchmark_state["failed"],
        elapsed_seconds=_benchmark_state["elapsed_seconds"],
        estimated_remaining_seconds=_benchmark_state["estimated_remaining_seconds"],
        domain_accuracy=_benchmark_state["domain_accuracy"],
        current_question=_benchmark_state["current_question"],
    )


@router.post("/benchmark/start")
async def start_benchmark(body: BenchmarkStartRequest):
    """启动 Benchmark 评测"""
    if _benchmark_state["running"]:
        raise HTTPException(status_code=400, detail="Benchmark 正在运行中")

    dataset_path = body.dataset_path
    # 解析相对路径
    if not os.path.isabs(dataset_path):
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        dataset_path = os.path.join(project_root, dataset_path.lstrip("./"))

    if not os.path.exists(dataset_path):
        raise HTTPException(status_code=404, detail=f"数据集不存在: {dataset_path}")

    # 重置状态
    _benchmark_state.update({
        "running": True,
        "progress": 0,
        "total": 0,
        "solved": 0,
        "failed": 0,
        "elapsed_seconds": 0.0,
        "estimated_remaining_seconds": None,
        "domain_accuracy": {},
        "current_question": None,
        "results": [],
    })

    # 后台线程运行
    thread = threading.Thread(
        target=_run_benchmark,
        args=(dataset_path, body.max_retries, body.enable_rag),
        daemon=True,
    )
    thread.start()
    _benchmark_state["thread"] = thread

    return {"message": "Benchmark 已启动", "dataset": dataset_path}


@router.post("/benchmark/stop")
async def stop_benchmark():
    """停止 Benchmark"""
    if not _benchmark_state["running"]:
        return {"message": "没有正在运行的 Benchmark"}
    _benchmark_state["running"] = False
    return {"message": "Benchmark 已停止"}


@router.get("/benchmark/results", response_model=BenchmarkResult)
async def get_benchmark_results():
    """获取最近一次 Benchmark 结果"""
    results = _benchmark_state.get("results", [])
    if not results:
        raise HTTPException(status_code=404, detail="没有可用的 Benchmark 结果")

    total = len(results)
    solved = sum(1 for r in results if r.get("verification", {}).get("is_correct"))
    failed = total - solved
    avg_conf = sum(
        r.get("verification", {}).get("confidence", 0) for r in results
    ) / max(total, 1)
    total_time = sum(r.get("computation_time_ms", 0) for r in results)

    # 领域准确率
    domain_stats: Dict[str, list] = {}
    for r in results:
        domain = r.get("domain", "unknown")
        conf = r.get("verification", {}).get("confidence", 0)
        if domain not in domain_stats:
            domain_stats[domain] = []
        domain_stats[domain].append(conf)

    domain_accuracy = {d: sum(cs) / len(cs) for d, cs in domain_stats.items()}

    return BenchmarkResult(
        total=total,
        solved=solved,
        failed=failed,
        accuracy=round(solved / max(total, 1) * 100, 2),
        avg_confidence=round(avg_conf, 4),
        total_time_ms=total_time,
        avg_time_per_question_ms=round(total_time / max(total, 1), 2),
        domain_accuracy=domain_accuracy,
        results=results,
    )


def _run_benchmark(dataset_path: str, max_retries: int, enable_rag: bool):
    """后台运行 Benchmark"""
    try:
        # 加载数据集
        with open(dataset_path, "r", encoding="utf-8") as f:
            questions = json.load(f)
        if not isinstance(questions, list):
            if "questions" in questions:
                questions = questions["questions"]
            else:
                questions = [questions]

        _benchmark_state["total"] = len(questions)
        _benchmark_state["results"] = []

        from graph.workflow import MathAgentWorkflow
        workflow = MathAgentWorkflow(
            enable_rag=enable_rag,
            max_reflection_count=max_retries,
        )

        start_time = time.time()

        for i, q in enumerate(questions):
            if not _benchmark_state["running"]:
                break

            qid = q.get("question_id") or q.get("id", f"q_{i:04d}")
            qtext = q.get("question_text") or q.get("problem") or q.get("question", "")

            _benchmark_state["current_question"] = qid
            _benchmark_state["progress"] = i

            try:
                result = workflow.solve(
                    question_text=qtext,
                    question_id=qid,
                    verbose=False,
                )
            except Exception as e:
                result = {
                    "question_id": qid,
                    "domain": q.get("domain", ""),
                    "final_answer": f"求解异常: {e}",
                    "reasoning_steps": [],
                    "methods_used": [],
                    "verification": {"is_correct": False, "confidence": 0},
                    "educational_hint": "",
                    "computation_time_ms": 0,
                    "retry_count": 0,
                }

            _benchmark_state["results"].append(result)

            if result.get("verification", {}).get("is_correct"):
                _benchmark_state["solved"] += 1
            else:
                _benchmark_state["failed"] += 1

            elapsed = time.time() - start_time
            _benchmark_state["elapsed_seconds"] = elapsed
            _benchmark_state["progress"] = i + 1

            # 预估剩余时间
            if i > 0:
                avg_time_per_q = elapsed / (i + 1)
                remaining = avg_time_per_q * (len(questions) - i - 1)
                _benchmark_state["estimated_remaining_seconds"] = remaining

        _benchmark_state["running"] = False
        _benchmark_state["current_question"] = None
        logger.info(f"[Benchmark] 完成: {_benchmark_state['solved']}/{_benchmark_state['total']}")

    except Exception as e:
        logger.error(f"[Benchmark] 运行异常: {e}")
        _benchmark_state["running"] = False
        _benchmark_state["error"] = str(e)
