# ============================================================
# api/tasks.py — 任务记录接口
# ============================================================
from fastapi import APIRouter, HTTPException, Query
from .schemas import TaskListResponse, TaskDetail
from services.problem_service import list_tasks, get_task

router = APIRouter()


@router.get("/tasks", response_model=TaskListResponse)
async def get_tasks(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    """获取任务列表"""
    return list_tasks(page=page, page_size=page_size)


@router.get("/tasks/{task_id}", response_model=TaskDetail)
async def get_task_detail(task_id: str):
    """获取任务详情 (含每道题的完整结果)"""
    task = get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"任务不存在: {task_id}")
    return task
