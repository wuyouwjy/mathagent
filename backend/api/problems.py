# ============================================================
# api/problems.py — 问题库接口
# ============================================================
import json
from typing import Optional, List
from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from loguru import logger

from .schemas import (
    ProblemCreate, ProblemUpdate, ProblemItem, ProblemDetail,
    ProblemListResponse,
)
from services.problem_service import (
    list_problems, get_problem, create_problem, update_problem,
    delete_problem, import_problems,
)

router = APIRouter()


@router.get("/problems", response_model=ProblemListResponse)
async def get_problems(
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=200, description="每页数量"),
    keyword: Optional[str] = Query(default=None, description="搜索关键词"),
    domain: Optional[str] = Query(default=None, description="领域筛选"),
    status: Optional[str] = Query(default=None, description="状态筛选"),
    difficulty: Optional[str] = Query(default=None, description="难度筛选"),
):
    """获取问题列表 (分页 + 搜索 + 筛选)"""
    return list_problems(
        page=page,
        page_size=page_size,
        keyword=keyword,
        domain=domain,
        status=status,
        difficulty=difficulty,
    )


@router.get("/problems/{problem_id}", response_model=ProblemDetail)
async def get_problem_detail(problem_id: str):
    """获取单个问题详情"""
    problem = get_problem(problem_id)
    if not problem:
        raise HTTPException(status_code=404, detail=f"问题不存在: {problem_id}")
    return problem


@router.post("/problems", response_model=ProblemItem)
async def create_new_problem(body: ProblemCreate):
    """创建新问题"""
    problem = create_problem(body.model_dump())
    return problem


@router.put("/problems/{problem_id}")
async def update_problem_by_id(problem_id: str, body: ProblemUpdate):
    """更新问题"""
    problem = update_problem(problem_id, body.model_dump(exclude_none=True))
    if not problem:
        raise HTTPException(status_code=404, detail=f"问题不存在: {problem_id}")
    return problem


@router.delete("/problems/{problem_id}")
async def delete_problem_by_id(problem_id: str):
    """删除问题"""
    ok = delete_problem(problem_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"问题不存在: {problem_id}")
    return {"message": "删除成功", "problem_id": problem_id}


@router.post("/problems/import")
async def import_problems_file(file: UploadFile = File(...)):
    """从 JSON 文件批量导入问题"""
    if not file.filename.endswith(".json"):
        raise HTTPException(status_code=400, detail="仅支持 JSON 文件")

    try:
        content = await file.read()
        data = json.loads(content.decode("utf-8"))

        if isinstance(data, list):
            questions = data
        elif isinstance(data, dict) and "questions" in data:
            questions = data["questions"]
        else:
            questions = [data]

        count = import_problems(questions)
        return {"message": f"成功导入 {count} 道题目", "count": count}
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"JSON 解析失败: {str(e)}")
    except Exception as e:
        logger.error(f"[API] 导入失败: {e}")
        raise HTTPException(status_code=500, detail=f"导入失败: {str(e)}")


@router.get("/problems/domains/list")
async def list_domains():
    """获取所有支持的数学领域列表"""
    from schemas.math_domains import list_all_domains
    return {"domains": list_all_domains()}
