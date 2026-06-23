# ============================================================
# api/dashboard.py — 首页 Dashboard 接口
# ============================================================
from fastapi import APIRouter
from .schemas import DashboardStats
from services.problem_service import list_problems, _problems_store
from configs.settings import get_config

router = APIRouter()


@router.get("/dashboard", response_model=DashboardStats)
async def get_dashboard():
    """获取首页统计数据"""
    config = get_config()

    problems = list(_problems_store.values())
    total = len(problems)
    solved = sum(1 for p in problems if p.get("status") == "solved")
    failed = sum(1 for p in problems if p.get("status") == "failed")
    avg_time = (
        sum(p.get("computation_time_ms", 0) or 0 for p in problems if p.get("computation_time_ms"))
        / max(solved + failed, 1)
    )
    accuracies = [
        p.get("verification", {}).get("confidence", 0)
        for p in problems
        if p.get("verification")
    ]
    avg_acc = sum(accuracies) / max(len(accuracies), 1) if accuracies else 0.0

    try:
        from tools.intern_client import get_intern_client
        client = get_intern_client()
        stats = client.get_usage_stats()
        api_calls = stats.get("total_calls", 0)
        tokens = stats.get("total_tokens", 0)
    except Exception:
        api_calls = 0
        tokens = 0

    return DashboardStats(
        total_problems=total,
        solved_count=solved,
        failed_count=failed,
        avg_time_ms=round(avg_time, 2),
        avg_accuracy=round(avg_acc, 4),
        current_model=config.intern_s1.model_name,
        api_calls_today=api_calls,
        tokens_used_today=tokens,
    )
