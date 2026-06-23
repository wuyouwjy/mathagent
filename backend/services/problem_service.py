# ============================================================
# services/problem_service.py — 问题管理服务
# ============================================================
import os
import json
import uuid
import time
from typing import List, Dict, Any, Optional
from loguru import logger


# 内存存储 (生产环境应替换为数据库)
_problems_store: Dict[str, Dict[str, Any]] = {}
_tasks_store: Dict[str, Dict[str, Any]] = {}


def _get_store_path() -> str:
    """获取存储文件路径"""
    store_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
    os.makedirs(store_dir, exist_ok=True)
    return os.path.join(store_dir, "problems.json")


def _load_store() -> None:
    """从文件加载数据"""
    global _problems_store
    store_path = _get_store_path()
    if os.path.exists(store_path):
        try:
            with open(store_path, "r", encoding="utf-8") as f:
                _problems_store = json.load(f)
            logger.info(f"[ProblemService] 加载了 {len(_problems_store)} 条问题记录")
        except Exception as e:
            logger.warning(f"[ProblemService] 加载存储失败: {e}")


def _save_store() -> None:
    """保存数据到文件"""
    store_path = _get_store_path()
    try:
        with open(store_path, "w", encoding="utf-8") as f:
            json.dump(_problems_store, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning(f"[ProblemService] 保存存储失败: {e}")


# 初始化加载
_load_store()


def list_problems(
    page: int = 1,
    page_size: int = 20,
    keyword: Optional[str] = None,
    domain: Optional[str] = None,
    status: Optional[str] = None,
    difficulty: Optional[str] = None,
) -> Dict[str, Any]:
    """获取问题列表 (分页、搜索、筛选)"""
    items = list(_problems_store.values())

    # 筛选
    if keyword:
        keyword_lower = keyword.lower()
        items = [
            p for p in items
            if keyword_lower in p.get("question_text", "").lower()
            or keyword_lower in p.get("id", "").lower()
        ]
    if domain:
        items = [p for p in items if p.get("domain") == domain]
    if status:
        items = [p for p in items if p.get("status") == status]
    if difficulty:
        items = [p for p in items if p.get("difficulty") == difficulty]

    # 排序 (按创建时间倒序)
    items.sort(key=lambda x: x.get("created_at", ""), reverse=True)

    total = len(items)

    # 分页
    start = (page - 1) * page_size
    end = start + page_size
    page_items = items[start:end]

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": page_items,
    }


def get_problem(problem_id: str) -> Optional[Dict[str, Any]]:
    """获取单个问题详情"""
    return _problems_store.get(problem_id)


def create_problem(problem_data: Dict[str, Any]) -> Dict[str, Any]:
    """创建新问题"""
    problem_id = problem_data.get("id") or f"p_{uuid.uuid4().hex[:8]}"
    now = datetime_now_str()

    problem = {
        "id": problem_id,
        "question_text": problem_data["question_text"],
        "domain": problem_data.get("domain", ""),
        "difficulty": problem_data.get("difficulty", "medium"),
        "status": "pending",
        "tags": problem_data.get("tags", []),
        "created_at": now,
        "updated_at": now,
        "final_answer": None,
        "reasoning_steps": [],
        "methods_used": [],
        "verification": None,
        "educational_hint": None,
        "computation_time_ms": None,
        "raw_output": None,
    }
    _problems_store[problem_id] = problem
    _save_store()
    logger.info(f"[ProblemService] 创建问题: {problem_id}")
    return problem


def update_problem(problem_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """更新问题"""
    if problem_id not in _problems_store:
        return None
    problem = _problems_store[problem_id]
    problem.update({k: v for k, v in updates.items() if v is not None})
    problem["updated_at"] = datetime_now_str()
    _save_store()
    return problem


def delete_problem(problem_id: str) -> bool:
    """删除问题"""
    if problem_id not in _problems_store:
        return False
    del _problems_store[problem_id]
    _save_store()
    return True


def update_solve_result(problem_id: str, result: Dict[str, Any]) -> None:
    """根据求解结果更新问题状态"""
    if problem_id in _problems_store:
        verification = result.get("verification", {})
        _problems_store[problem_id].update({
            "status": "solved" if verification.get("is_correct") else "failed",
            "domain": result.get("domain", _problems_store[problem_id].get("domain", "")),
            "final_answer": result.get("final_answer"),
            "reasoning_steps": result.get("reasoning_steps", []),
            "methods_used": result.get("methods_used", []),
            "verification": verification,
            "educational_hint": result.get("educational_hint"),
            "computation_time_ms": result.get("computation_time_ms"),
            "raw_output": result,
            "updated_at": datetime_now_str(),
        })
        _save_store()


def import_problems(questions: List[Dict[str, Any]]) -> int:
    """批量导入问题"""
    count = 0
    for q in questions:
        qid = q.get("question_id") or q.get("id") or f"p_{uuid.uuid4().hex[:8]}"
        if qid in _problems_store:
            continue  # 跳过已存在的
        problem = {
            "id": qid,
            "question_text": q.get("question_text") or q.get("problem") or q.get("question", ""),
            "domain": q.get("domain", ""),
            "difficulty": q.get("difficulty", "medium"),
            "status": "pending",
            "tags": q.get("tags", []),
            "created_at": datetime_now_str(),
            "updated_at": datetime_now_str(),
            "final_answer": None,
            "reasoning_steps": [],
            "methods_used": [],
            "verification": None,
            "educational_hint": None,
            "computation_time_ms": None,
            "raw_output": None,
        }
        _problems_store[qid] = problem
        count += 1
    if count > 0:
        _save_store()
    logger.info(f"[ProblemService] 批量导入 {count} 题")
    return count


def get_domain_distribution() -> Dict[str, int]:
    """获取领域分布统计"""
    distribution: Dict[str, int] = {}
    for p in _problems_store.values():
        domain = p.get("domain", "未分类")
        distribution[domain] = distribution.get(domain, 0) + 1
    return distribution


# ============================================================
# 任务记录
# ============================================================
def create_task(task_data: Dict[str, Any]) -> str:
    """创建任务记录"""
    task_id = task_data.get("task_id") or f"task_{uuid.uuid4().hex[:8]}"
    now = datetime_now_str()
    _tasks_store[task_id] = {
        "task_id": task_id,
        "question_count": task_data.get("question_count", 0),
        "status": "running",
        "solved_count": 0,
        "failed_count": 0,
        "avg_confidence": 0.0,
        "total_time_ms": 0.0,
        "model_name": task_data.get("model_name", ""),
        "created_at": now,
        "completed_at": None,
        "domain_distribution": {},
        "results": [],
        "logs": [],
    }
    return task_id


def update_task(task_id: str, updates: Dict[str, Any]) -> None:
    """更新任务"""
    if task_id in _tasks_store:
        _tasks_store[task_id].update(updates)


def get_task(task_id: str) -> Optional[Dict[str, Any]]:
    """获取任务详情"""
    return _tasks_store.get(task_id)


def list_tasks(page: int = 1, page_size: int = 20) -> Dict[str, Any]:
    """获取任务列表"""
    items = list(_tasks_store.values())
    items.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    total = len(items)
    start = (page - 1) * page_size
    end = start + page_size
    return {"total": total, "items": items[start:end]}


def datetime_now_str() -> str:
    """获取当前时间字符串"""
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
