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
    "active_solves": {},   # {qid: {"question": str, "domain": str, "steps": [str, ...]}}
    "results": [],
    "thread": None,
    "correct_list": [],    # 本轮已答对的题目摘要
    "wrong_list": [],      # 本轮已答错的题目摘要
}


@router.get("/benchmark/datasets")
async def list_datasets():
    """列出 database/datasets 目录下所有可用的 JSONL 测试集"""
    import glob as glob_module
    datasets_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "database", "datasets"
    )
    files = sorted(glob_module.glob(os.path.join(datasets_dir, "*.jsonl")))
    result = []
    for fpath in files:
        fname = os.path.basename(fpath)
        # 统计题目数
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                count = sum(1 for line in f if line.strip())
        except Exception:
            count = 0
        # 相对路径（相对于项目根目录）
        rel_path = os.path.join("database", "datasets", fname).replace("\\", "/")
        result.append({
            "name": fname,
            "path": rel_path,
            "count": count,
        })
    return {"datasets": result}


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
        active_solves=_benchmark_state.get("active_solves", {}),
        correct_list=_benchmark_state.get("correct_list", []),
        wrong_list=_benchmark_state.get("wrong_list", []),
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
        "correct_list": [],
        "wrong_list": [],
        "active_solves": {},
    })

    # 后台线程运行
    skip_cache = not body.use_answer_db
    thread = threading.Thread(
        target=_run_benchmark,
        args=(dataset_path, body.max_retries, body.enable_rag, skip_cache, run_id, body.max_reflection_count, body.use_llm_verify),
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

    domain_stats: Dict[str, Dict[str, int]] = {}
    for r in results:
        domain = r.get("domain", "unknown")
        if domain not in domain_stats:
            domain_stats[domain] = {"total": 0, "solved": 0}
        domain_stats[domain]["total"] += 1
        if r.get("verification", {}).get("is_correct"):
            domain_stats[domain]["solved"] += 1

    domain_accuracy = {
        d: round(s["solved"] / max(s["total"], 1), 4)
        for d, s in domain_stats.items()
    }

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
                config=data.get("config"),
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

def _run_benchmark(dataset_path: str, max_retries: int, enable_rag: bool, skip_cache: bool, run_id: str, max_reflection_count: int, use_llm_verify: bool):
    """后台 Benchmark：流水线并发（分类→求解→答案验证）"""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    import threading as th

    # 保存配置参数供记录使用
    _benchmark_state["_max_reflection_count"] = max_reflection_count
    _benchmark_state["_use_answer_db"] = not skip_cache
    _benchmark_state["_use_llm_verify"] = use_llm_verify

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

            # 提前退出：所有题目已求解完毕，不再启动新的 LLM 调用
            if _benchmark_state["progress"] >= total:
                logger.debug(f"[Benchmark] 跳过 {i}: 所有题目已完成 (progress={_benchmark_state['progress']})")
                return i, None

            from graph.workflow import MathAgentWorkflow

            qid = str(q.get("question_id") or q.get("id") or q.get("idx", f"q_{i:04d}"))
            qtext_raw = str(q.get("question_text") or q.get("problem") or q.get("question", ""))
            ground_truth = str(q.get("answer", ""))
            is_choice = qtext_raw.startswith("选择题")
            is_fill = qtext_raw.startswith("填空题")

            # 选择题/填空题：在题目开头追加格式指令
            if is_choice:
                qtext = (
                    "【选择题·答题要求】你正在解答一道选择题。"
                    "请在 reasoning_steps 中逐步分析每个选项，"
                    "在 final_answer 字段中只填入正确选项的字母（A/B/C/D），不要填入任何其他文字。\n\n"
                    + qtext_raw
                )
            elif is_fill:
                qtext = (
                    "【填空题·答题要求】你正在解答一道填空题。"
                    "请在 reasoning_steps 中逐步推理求解，"
                    "在 final_answer 字段中只填入填空处的答案内容，简洁明了。\n\n"
                    + qtext_raw
                )
            else:
                qtext = qtext_raw

            # 更新活跃求解追踪
            with _lock:
                _benchmark_state["current_question"] = qid
                _benchmark_state["current_trace"] = [f"🔍 开始求解 {qid}", "🏷️ 分类中..."]
                _benchmark_state["active_solves"][qid] = {
                    "question": qtext_raw[:120].replace("\n", " "),
                    "domain": q.get("subject", ""),
                    "steps": [f"🔍 开始求解", "🏷️ 分类中..."],
                }

            # Stage 1+2: 分类 + 求解
            # skip_cache_save=True: 禁止 workflow 内部基于 LLM 自验保存缓存，
            # 改为由 benchmark 在 ground truth 验证通过后统一保存，防止自验假阳性污染缓存
            workflow = MathAgentWorkflow(
                enable_rag=False,
                max_reflection_count=max_reflection_count,
                skip_cache=skip_cache,
                skip_cache_save=True,
            )

            with _lock:
                _benchmark_state["current_trace"].append("🧠 LLM 求解中...")
                if qid in _benchmark_state["active_solves"]:
                    _benchmark_state["active_solves"][qid]["steps"].append("🧠 LLM 求解中...")

            try:
                result = workflow.solve(question_text=qtext, question_id=qid, verbose=False)
            except Exception as e:
                result = {
                    "question_id": qid, "domain": q.get("domain", q.get("subject", "")),
                    "final_answer": f"求解异常: {e}", "reasoning_steps": [],
                    "methods_used": [], "verification": {"is_correct": False, "confidence": 0},
                    "educational_hint": "", "computation_time_ms": 0, "retry_count": 0,
                }

            # 如果数据集提供了 subject 字段，用它覆盖分类器的领域结果
            # 确保统计图表与数据集领域分布一致
            dataset_subject = q.get("subject", "")
            if dataset_subject:
                result["domain"] = dataset_subject

            # 将 LLM 的实际推理步骤注入活跃求解追踪（替换占位的"🧠 LLM 求解中..."）
            solve_steps = result.get("reasoning_steps") or []
            with _lock:
                if qid in _benchmark_state["active_solves"]:
                    info = _benchmark_state["active_solves"][qid]
                    # 移除占位步骤
                    real_steps = [s for s in info["steps"] if "LLM 求解中" not in s]
                    # 加上题目原文
                    real_steps.append(f"📋 {qtext_raw[:100]}")
                    if solve_steps:
                        for s in solve_steps:
                            desc = str(s.get("description", "")) if isinstance(s, dict) else str(s)
                            if desc.strip():
                                real_steps.append(f"📝 {desc}"[:120])
                    else:
                        # 无推理步骤时，用可用信息合成
                        methods = result.get("methods_used", [])
                        if methods:
                            real_steps.append(f"🔧 方法: {', '.join(methods)}"[:120])
                        ans = result.get("final_answer", "")
                        if ans:
                            real_steps.append(f"💡 答案: {str(ans)[:100]}")
                    info["steps"] = real_steps

            with _lock:
                _benchmark_state["current_trace"].append("✅ 答案验证中...")
                if qid in _benchmark_state["active_solves"]:
                    _benchmark_state["active_solves"][qid]["steps"].append("✅ 答案验证中...")

            # Stage 3: 答案验证（fuzzy_match → LLM兜底）
            pred = str(result.get("final_answer", ""))

            # 选择题：从 LLM 输出中提取选项字母
            if is_choice and ground_truth and len(ground_truth.strip()) <= 2:
                extracted = _extract_choice_letter(pred, result)
                if extracted != pred:
                    result["final_answer"] = extracted
                    pred = extracted
                    logger.info(f"[Benchmark] 选择题答案提取: {pred!r} -> {extracted!r}")

            if ground_truth:
                ok = _fuzzy_match(pred, ground_truth)
                llm_verify_info = None

                # fuzzy_match 失败时，如果开启了 LLM 辅助验证，再试一次
                if not ok and use_llm_verify:
                    try:
                        from utils.math_match import llm_verify_match
                        llm_verify_info = llm_verify_match(pred, ground_truth, qtext)
                        if llm_verify_info.get("is_equivalent"):
                            ok = True
                        logger.debug(
                            f"[Benchmark] LLM验证 {qid}: equivalent={llm_verify_info.get('is_equivalent')}, "
                            f"confidence={llm_verify_info.get('confidence', 0):.2f}"
                        )
                    except Exception as e:
                        logger.warning(f"[Benchmark] LLM验证异常: {e}")

                result["verification"] = {
                    "is_correct": ok,
                    "confidence": 1.0 if ok else (llm_verify_info.get("confidence", 0) if llm_verify_info else 0.0),
                    "check_method": "ground_truth_match" if not llm_verify_info else
                        ("llm_verify_match" if ok else "llm_verify_mismatch"),
                    "error_details": "" if ok else f"pred={pred[:80]}, gt={ground_truth[:80]}",
                }
                # 错题分类：区分"真正错误"与"匹配失败"（证明题/长文本）
                if not ok:
                    if llm_verify_info and not llm_verify_info.get("is_equivalent"):
                        result["verification"]["error_type"] = "真正错误"
                    else:
                        result["verification"]["error_type"] = "匹配失败"
                if llm_verify_info:
                    result["verification"]["llm_verify"] = llm_verify_info
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
                # 防护：防止重复计数导致 progress > total
                if _benchmark_state["progress"] >= total:
                    logger.warning(f"[Benchmark] 重复计数被拦截: {qid} (progress={_benchmark_state['progress']}, total={total})")
                    return i, result
                # 防护：防止索引越界
                if i >= len(_benchmark_state["results"]):
                    logger.error(f"[Benchmark] 索引越界: i={i}, results_len={len(_benchmark_state['results'])}")
                    return i, result
                _benchmark_state["results"][i] = result
                if result.get("verification", {}).get("is_correct"):
                    _benchmark_state["solved"] += 1
                else:
                    _benchmark_state["failed"] += 1
                _benchmark_state["progress"] += 1
                elapsed = time.time() - start_time
                _benchmark_state["elapsed_seconds"] = elapsed
                done = _benchmark_state["progress"]
                if done > 0:
                    _benchmark_state["estimated_remaining_seconds"] = (elapsed / done) * (total - done)
                # 完成后从并发流程移除，追加到对题/错题列表
                _benchmark_state["active_solves"].pop(qid, None)
                ok = result.get("verification", {}).get("is_correct", False)

                # 追加到对题/错题列表（带完整信息，点击可查看）
                entry = {
                    "question_id": qid,
                    "domain": result.get("domain", ""),
                    "question": qtext_raw[:150],
                    "final_answer": str(result.get("final_answer", ""))[:120],
                    "ground_truth": ground_truth[:120],
                    "reasoning_steps": result.get("reasoning_steps", []),
                    "methods_used": result.get("methods_used", []),
                    "time_ms": result.get("computation_time_ms", 0),
                    "error_type": result.get("verification", {}).get("error_type", ""),
                }
                if ok:
                    _benchmark_state["correct_list"].append(entry)
                else:
                    _benchmark_state["wrong_list"].append(entry)

            return i, result

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(solve_one, i, q): i for i, q in enumerate(questions)}
            for _ in as_completed(futures):
                if not _benchmark_state["running"]:
                    executor.shutdown(wait=False, cancel_futures=True)
                    break
                # 提前终止：所有题目已求解完毕，取消剩余未开始的任务
                if _benchmark_state["progress"] >= total:
                    logger.info(f"[Benchmark] 所有 {total} 题已完成，取消剩余排队任务")
                    executor.shutdown(wait=False, cancel_futures=True)
                    break

        was_interrupted = not _benchmark_state["running"]
        _benchmark_state["running"] = False
        _benchmark_state["current_question"] = None
        _benchmark_state["current_trace"] = []
        _benchmark_state["active_solves"] = {}
        logger.info(f"[Benchmark] 完成: {_benchmark_state['solved']}/{_benchmark_state['total']}")

        # 保存评测记录
        logger.info(
            f"[Benchmark] 保存记录: answer_db={_benchmark_state.get('_use_answer_db')}, "
            f"llm_verify={_benchmark_state.get('_use_llm_verify')}, "
            f"reflection={_benchmark_state.get('_max_reflection_count')}"
        )
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
                error_type=r.get("verification", {}).get("error_type", ""),
            ))

    # 补齐所有18个领域（未出现的领域填0）
    all_domains = {
        "algebra": "代数", "number_theory": "数论", "group_theory": "群论",
        "real_analysis": "实分析", "complex_analysis": "复分析",
        "functional_analysis": "泛函分析", "topology": "拓扑学",
        "differential_geometry": "微分几何", "algebraic_geometry": "代数几何",
        "partial_differential_equations": "偏微分方程",
        "ordinary_differential_equations": "常微分方程",
        "calculus_of_variations": "变分法", "optimization": "最优化",
        "probability": "概率论", "statistics": "统计学",
        "numerical_analysis": "数值分析", "combinatorics": "组合数学",
        "mathematical_physics": "数学物理",
    }
    # 以实际结果中的领域统计为准，再补齐未出现的系统领域（兼容旧记录）
    full_domain_stats = {d: s.model_dump() for d, s in domain_stats.items()}
    for dk, _dn in all_domains.items():
        if dk not in full_domain_stats:
            full_domain_stats[dk] = {"total": 0, "solved": 0, "accuracy": 0.0}

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
        "config": {
            "max_reflection_count": _benchmark_state.get("_max_reflection_count", 1),
            "use_answer_db": _benchmark_state.get("_use_answer_db", True),
            "use_llm_verify": _benchmark_state.get("_use_llm_verify", True),
        },
        "domain_stats": full_domain_stats,
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

def _extract_choice_letter(pred: str, result: Dict[str, Any]) -> str:
    """从 LLM 输出中提取选择题的选项字母 (A/B/C/D)"""
    import re

    # 收集所有文本来源：raw_llm_response 最重要（LLM 原始输出）
    texts = [pred]
    raw = result.get("raw_llm_response", "")
    if raw:
        texts.insert(0, raw)  # 原始输出优先级最高
    for step in result.get("reasoning_steps", []):
        texts.append(str(step.get("description", "")))
        texts.append(str(step.get("result", "")))

    combined = "\n".join(texts)

    # 按优先级匹配：先精确后模糊
    patterns = [
        # 明确声明答案
        r'(?:正确)?答案[是为：:]\s*([A-D])',
        r'(?:正确)?选项[是为：:]\s*([A-D])',
        r'选[择]?\s*([A-D])\s*[项个]?',
        # JSON 中的 final_answer 字段 (检查 raw response 中)
        r'"final_answer"\s*:\s*"([A-D])"',
        # 行首的选项标记: C. xxx
        r'(?:^|\n)\s*([A-D])\.\s',
        # 引号包裹的字母: "D"
        r'"\s*([A-D])\s*"',
    ]

    for pat in patterns:
        m = re.search(pat, combined)
        if m:
            logger.debug(f"[Benchmark] 选择题提取: '{m.group(0)[:50]}' -> {m.group(1)}")
            return m.group(1)

    # 最后兜底：在 raw response 中查找 "答案：X" 等更宽泛的模式
    if raw:
        m = re.search(r'答案\s*[：:]\s*([A-D])', raw)
        if m:
            return m.group(1)

    # 无法提取
    return pred


def _fuzzy_match(predicted: str, ground_truth: str) -> bool:
    """模糊比对答案，委托给共享模块"""
    import sys, os
    _proj = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if _proj not in sys.path:
        sys.path.insert(0, _proj)
    from utils.math_match import fuzzy_match
    return fuzzy_match(predicted, ground_truth)
