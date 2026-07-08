# ============================================================
# api/benchmark.py — Benchmark 评测接口
# ============================================================
import os
import json
import time
import uuid
import glob
import threading
from datetime import datetime
from typing import Dict, Any, List
from fastapi import APIRouter, HTTPException
from loguru import logger

from .schemas import (
    BenchmarkStartRequest, BenchmarkStatus, BenchmarkResult,
    BenchmarkRunSummary, BenchmarkRunRecord, WrongQuestion, DomainStat,
)
from schemas.math_domains import list_all_domains

router = APIRouter()

# 记录输出目录
RUNS_DIR = "./database/outputs/benchmark_runs"

# Benchmark 运行状态 (全局)
_benchmark_state: Dict[str, Any] = {
    "running": False,
    "run_id": None,
    "started_at": None,
    "progress": 0,
    "total": 112,
    "solved": 0,
    "failed": 0,
    "elapsed_seconds": 0.0,
    "estimated_remaining_seconds": None,
    "domain_accuracy": {},
    "current_question": None,
    "current_trace": [],
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
        current_trace=_benchmark_state.get("current_trace", []),
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

    run_id = f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    # 重置状态
    _benchmark_state.update({
        "running": True,
        "run_id": run_id,
        "started_at": datetime.now().isoformat(),
        "progress": 0,
        "total": 0,
        "solved": 0,
        "failed": 0,
        "elapsed_seconds": 0.0,
        "estimated_remaining_seconds": None,
        "domain_accuracy": {},
        "current_question": None,
        "current_trace": [],
        "results": [],
        "error": None,
    })

    # 后台线程运行
    skip_cache = not body.use_answer_db
    thread = threading.Thread(
        target=_run_benchmark,
        args=(dataset_path, body.max_retries, body.enable_rag, skip_cache, run_id, body.max_reflection_count),
        daemon=True,
    )
    thread.start()
    _benchmark_state["thread"] = thread

    return {"message": "Benchmark 已启动", "run_id": run_id, "dataset": dataset_path}


@router.post("/benchmark/stop")
async def stop_benchmark():
    """停止 Benchmark"""
    if not _benchmark_state["running"]:
        return {"message": "没有正在运行的 Benchmark"}
    _benchmark_state["running"] = False
    return {"message": "Benchmark 已停止"}


@router.post("/benchmark/clear-db")
async def clear_answer_db():
    """清空正确答案库"""
    try:
        from rag.cache.problem_cache import get_cache, reset_cache
        cache = get_cache()
        stats_before = cache.get_stats()
        cache.clear()
        reset_cache()
        return {
            "message": "正确答案库已清空",
            "cleared_exact": stats_before.get("exact_cache_size", 0),
            "cleared_vector": stats_before.get("vector_cache_size", 0),
        }
    except Exception as e:
        return {"message": f"清空失败: {e}"}


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


# ============================================================
# 历史记录 API
# ============================================================

@router.get("/benchmark/runs", response_model=List[BenchmarkRunSummary])
async def list_benchmark_runs():
    """列出所有历史评测记录（摘要）"""
    os.makedirs(RUNS_DIR, exist_ok=True)
    files = sorted(glob.glob(os.path.join(RUNS_DIR, "run_*.json")), reverse=True)
    summaries = []
    for fpath in files:
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)
            summaries.append(BenchmarkRunSummary(
                run_id=data.get("run_id", ""),
                status=data.get("status", ""),
                started_at=data.get("started_at", ""),
                completed_at=data.get("completed_at"),
                total=data.get("total", 0),
                solved=data.get("solved", 0),
                accuracy=data.get("accuracy", 0.0),
                total_time_ms=data.get("total_time_ms", 0.0),
            ))
        except Exception as e:
            logger.warning(f"[Benchmark] 读取记录失败: {fpath} - {e}")
    return summaries


@router.get("/benchmark/runs/{run_id}", response_model=BenchmarkRunRecord)
async def get_benchmark_run(run_id: str):
    """获取某次评测的完整记录"""
    fpath = os.path.join(RUNS_DIR, f"{run_id}.json")
    if not os.path.exists(fpath):
        raise HTTPException(status_code=404, detail=f"记录不存在: {run_id}")
    with open(fpath, "r", encoding="utf-8") as f:
        data = json.load(f)
    return BenchmarkRunRecord(**data)


@router.delete("/benchmark/runs/{run_id}")
async def delete_benchmark_run(run_id: str):
    """删除某次评测记录"""
    fpath = os.path.join(RUNS_DIR, f"{run_id}.json")
    if not os.path.exists(fpath):
        raise HTTPException(status_code=404, detail=f"记录不存在: {run_id}")
    os.remove(fpath)
    return {"message": f"记录已删除: {run_id}"}


# ============================================================
# 后台 Benchmark 运行
# ============================================================

def _run_benchmark(dataset_path: str, max_retries: int, enable_rag: bool, skip_cache: bool, run_id: str, max_reflection_count: int):
    """后台 Benchmark：流水线并发（分类→求解→答案验证）"""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    import threading as th

    _lock = th.Lock()

    try:
        # 1. 加载数据集
        with open(dataset_path, "r", encoding="utf-8") as f:
            raw = f.read().strip()
        if raw.startswith("["):
            questions = json.loads(raw)
        else:
            questions = [json.loads(line) for line in raw.split("\n") if line.strip()]
        if not isinstance(questions, list):
            questions = [questions] if isinstance(questions, dict) else questions

        total = len(questions)
        _benchmark_state["total"] = total
        _benchmark_state["results"] = [None] * total
        _benchmark_state["solved"] = 0
        _benchmark_state["failed"] = 0
        _benchmark_state["progress"] = 0

        start_time = time.time()
        max_workers = min(8, total)

        def solve_one(i: int, q: dict):
            """流水线：分类→求解→答案验证"""
            if not _benchmark_state["running"]:
                return i, None

            from graph.workflow import MathAgentWorkflow

            qid = str(q.get("question_id") or q.get("id") or q.get("idx", f"q_{i:04d}"))
            qtext = str(q.get("question_text") or q.get("problem") or q.get("question", ""))
            ground_truth = str(q.get("answer", ""))

            # 更新当前追踪
            with _lock:
                _benchmark_state["current_question"] = qid
                _benchmark_state["current_trace"] = [f"🔍 开始求解 {qid}", "🏷️ 分类中..."]

            # Stage 1+2: 分类 + 求解
            workflow = MathAgentWorkflow(enable_rag=False, max_reflection_count=max_reflection_count, skip_cache=skip_cache)

            with _lock:
                _benchmark_state["current_trace"].append("🧠 LLM 求解中...")

            try:
                result = workflow.solve(question_text=qtext, question_id=qid, verbose=False)
            except Exception as e:
                result = {
                    "question_id": qid, "domain": q.get("domain", q.get("subject", "")),
                    "final_answer": f"求解异常: {e}", "reasoning_steps": [],
                    "methods_used": [], "verification": {"is_correct": False, "confidence": 0},
                    "educational_hint": "", "computation_time_ms": 0, "retry_count": 0,
                }

            with _lock:
                _benchmark_state["current_trace"].append("✅ 答案验证中...")

            # Stage 3: 答案验证（用 ground_truth 精确比对）
            pred = str(result.get("final_answer", ""))
            if ground_truth:
                ok = _fuzzy_match(pred, ground_truth)
                result["verification"] = {
                    "is_correct": ok, "confidence": 1.0 if ok else 0.0,
                    "check_method": "ground_truth_match",
                    "error_details": "" if ok else f"pred={pred[:80]}, gt={ground_truth[:80]}",
                }
                result["ground_truth"] = ground_truth
                result["answer_match"] = ok

                # 只有 ground_truth 验证通过的答案才写入正确答案库
                if ok:
                    try:
                        from rag.cache.problem_cache import get_cache
                        cache = get_cache()
                        cache.save(qtext, result)
                        logger.debug(f"[Benchmark] 正确结果已缓存: {qid}")
                    except Exception as e:
                        logger.warning(f"[Benchmark] 缓存写入失败: {e}")

            with _lock:
                _benchmark_state["results"][i] = result
                if result.get("verification", {}).get("is_correct"):
                    _benchmark_state["solved"] += 1
                    _benchmark_state["current_trace"].append(f"✅ {qid} 正确")
                else:
                    _benchmark_state["failed"] += 1
                    _benchmark_state["current_trace"].append(f"❌ {qid} 错误")
                _benchmark_state["progress"] += 1
                elapsed = time.time() - start_time
                _benchmark_state["elapsed_seconds"] = elapsed
                done = _benchmark_state["progress"]
                if done > 0:
                    _benchmark_state["estimated_remaining_seconds"] = (elapsed / done) * (total - done)

            return i, result

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(solve_one, i, q): i for i, q in enumerate(questions)}
            for _ in as_completed(futures):
                if not _benchmark_state["running"]:
                    executor.shutdown(wait=False, cancel_futures=True)
                    break

        was_interrupted = not _benchmark_state["running"]
        _benchmark_state["running"] = False
        _benchmark_state["current_question"] = None
        _benchmark_state["current_trace"] = []
        logger.info(f"[Benchmark] 完成: {_benchmark_state['solved']}/{_benchmark_state['total']}")

        # 保存评测记录
        _save_benchmark_record(run_id, dataset_path, interrupted=was_interrupted)

    except Exception as e:
        logger.error(f"[Benchmark] 运行异常: {e}")
        _benchmark_state["running"] = False
        _benchmark_state["error"] = str(e)
        # 异常也尝试保存记录
        try:
            _save_benchmark_record(run_id, dataset_path, interrupted=True)
        except Exception:
            pass


# ============================================================
# 记录保存
# ============================================================

def _save_benchmark_record(run_id: str, dataset_path: str, interrupted: bool = False):
    """将本次评测结果保存为 JSON 记录"""
    results = [r for r in _benchmark_state.get("results", []) if r is not None]
    if not results:
        logger.warning("[Benchmark] 没有结果可保存")
        return

    total = len(results)
    solved = sum(1 for r in results if r.get("verification", {}).get("is_correct"))
    failed = total - solved
    total_time = sum(r.get("computation_time_ms", 0) for r in results)

    # 领域统计
    domain_data: Dict[str, Dict[str, Any]] = {}
    for r in results:
        domain = r.get("domain", "unknown")
        if domain not in domain_data:
            domain_data[domain] = {"total": 0, "solved": 0}
        domain_data[domain]["total"] += 1
        if r.get("verification", {}).get("is_correct"):
            domain_data[domain]["solved"] += 1

    domain_stats = {}
    for d, s in domain_data.items():
        domain_stats[d] = DomainStat(
            total=s["total"],
            solved=s["solved"],
            accuracy=round(s["solved"] / max(s["total"], 1) * 100, 2),
        )

    # 错题列表
    wrong_questions = []
    for r in results:
        if not r.get("verification", {}).get("is_correct"):
            wrong_questions.append(WrongQuestion(
                question_id=r.get("question_id", ""),
                domain=r.get("domain", ""),
                predicted=str(r.get("final_answer", ""))[:120],
                ground_truth=str(r.get("ground_truth", "")),
                time_ms=r.get("computation_time_ms", 0),
            ))

    record = {
        "run_id": run_id,
        "status": "interrupted" if interrupted else "completed",
        "started_at": _benchmark_state.get("started_at", ""),
        "completed_at": datetime.now().isoformat(),
        "dataset": dataset_path,
        "total": total,
        "solved": solved,
        "failed": failed,
        "accuracy": round(solved / max(total, 1) * 100, 2),
        "avg_time_per_question_ms": round(total_time / max(total, 1), 2),
        "total_time_ms": round(total_time, 2),
        "domain_stats": {d: s.model_dump() for d, s in domain_stats.items()},
        "wrong_questions": [w.model_dump() for w in wrong_questions],
        "results": results,
    }

    os.makedirs(RUNS_DIR, exist_ok=True)
    fpath = os.path.join(RUNS_DIR, f"{run_id}.json")
    with open(fpath, "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)

    logger.info(f"[Benchmark] 评测记录已保存: {fpath} (solved={solved}/{total}, accuracy={record['accuracy']}%)")


# ============================================================
# 答案模糊匹配
# ============================================================

def _fuzzy_match(predicted: str, ground_truth: str) -> bool:
    """模糊比对答案，委托给共享模块"""
    import sys, os
    _proj = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if _proj not in sys.path:
        sys.path.insert(0, _proj)
    from utils.math_match import fuzzy_match
    return fuzzy_match(predicted, ground_truth)
