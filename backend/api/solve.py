# ============================================================
# api/solve.py — 求解接口
# ============================================================
import json
import uuid
import time
from typing import Optional, List
from fastapi import APIRouter, UploadFile, File, HTTPException
from loguru import logger

from .schemas import SolveRequest, SolveResponse, BatchSolveRequest
from services.problem_service import (
    create_problem, update_solve_result, create_task, update_task,
)

router = APIRouter()


@router.post("/solve", response_model=SolveResponse)
async def solve_question(body: SolveRequest):
    """单题求解"""
    logger.info(f"[API] 收到求解请求: question={body.question[:80]}...")

    question_id = body.question_id or f"q_{uuid.uuid4().hex[:8]}"

    # 先创建问题记录
    try:
        create_problem({
            "id": question_id,
            "question_text": body.question,
            "domain": "",
            "difficulty": "medium",
        })
    except Exception:
        pass  # 可能已存在

    # 执行求解
    try:
        from graph.workflow import MathAgentWorkflow

        workflow = MathAgentWorkflow(
            enable_rag=body.enable_rag,
            max_reflection_count=body.max_retries,
        )

        result = workflow.solve(
            question_text=body.question,
            question_id=question_id,
            verbose=False,
        )

        # 更新问题记录
        update_solve_result(question_id, result)

        return SolveResponse(
            question_id=result.get("question_id", question_id),
            domain=result.get("domain", ""),
            final_answer=result.get("final_answer", ""),
            reasoning_steps=result.get("reasoning_steps", []),
            methods_used=result.get("methods_used", []),
            verification=result.get("verification", {}),
            educational_hint=result.get("educational_hint", ""),
            computation_time_ms=result.get("computation_time_ms", 0),
            retry_count=result.get("retry_count", 0),
            model_version=result.get("model_version"),
            node_trace=result.get("node_trace", []),
        )
    except Exception as e:
        logger.error(f"[API] 求解失败: {e}")
        raise HTTPException(status_code=500, detail=f"求解失败: {str(e)}")


@router.post("/solve/upload")
async def solve_from_file(file: UploadFile = File(...)):
    """从上传文件读取题目并求解 (支持 .txt / .json)"""
    content = await file.read()
    text = content.decode("utf-8")

    # 如果是 JSON，提取 question_text
    if file.filename.endswith(".json"):
        try:
            data = json.loads(text)
            question = data.get("question_text") or data.get("question") or text
        except json.JSONDecodeError:
            question = text
    else:
        question = text.strip()

    if not question:
        raise HTTPException(status_code=400, detail="文件内容为空")

    body = SolveRequest(question=question)
    return await solve_question(body)


@router.post("/solve/batch")
async def solve_batch(body: BatchSolveRequest):
    """批量求解"""
    task_id = create_task({
        "task_id": f"task_{uuid.uuid4().hex[:8]}",
        "question_count": len(body.questions),
        "model_name": "intern-latest",
    })

    results = []
    start_time = time.time()

    for i, q in enumerate(body.questions):
        try:
            result = await solve_question(q)
            results.append(result.model_dump())
        except Exception as e:
            results.append({
                "question_id": q.question_id or f"q_{i:04d}",
                "domain": "",
                "final_answer": f"错误: {str(e)}",
                "reasoning_steps": [],
                "methods_used": [],
                "verification": {"is_correct": False, "confidence": 0},
                "educational_hint": "",
                "computation_time_ms": 0,
                "retry_count": 0,
            })

    total_time = (time.time() - start_time) * 1000
    solved = sum(1 for r in results if r.get("verification", {}).get("is_correct"))
    avg_conf = sum(r.get("verification", {}).get("confidence", 0) for r in results) / max(len(results), 1)

    update_task(task_id, {
        "status": "completed",
        "solved_count": solved,
        "failed_count": len(results) - solved,
        "avg_confidence": round(avg_conf, 4),
        "total_time_ms": total_time,
        "completed_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "results": results,
    })

    return {
        "task_id": task_id,
        "total": len(results),
        "solved": solved,
        "failed": len(results) - solved,
        "avg_confidence": round(avg_conf, 4),
        "total_time_ms": total_time,
        "results": results,
    }
