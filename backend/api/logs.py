# ============================================================
# api/logs.py — 日志中心接口
# ============================================================
import os
import glob
from typing import Optional, List
from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import PlainTextResponse
from loguru import logger

from .schemas import LogsResponse, LogEntry

router = APIRouter()


@router.get("/logs", response_model=LogsResponse)
async def get_logs(
    lines: int = Query(default=200, ge=1, le=5000, description="返回行数"),
    level: Optional[str] = Query(default=None, description="过滤日志级别"),
    keyword: Optional[str] = Query(default=None, description="搜索关键词"),
):
    """获取最近的日志"""
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    log_dir = os.path.join(project_root, "outputs", "logs")

    log_entries: List[LogEntry] = []

    # 查找最新的日志文件
    log_files = []
    if os.path.exists(log_dir):
        log_files = sorted(
            glob.glob(os.path.join(log_dir, "*.log")),
            key=os.path.getmtime,
            reverse=True,
        )

    if log_files:
        latest_log = log_files[0]
        try:
            with open(latest_log, "r", encoding="utf-8") as f:
                all_lines = f.readlines()
                # 取最后 N 行
                recent_lines = all_lines[-lines:]

                for line in recent_lines:
                    entry = _parse_log_line(line)
                    if entry:
                        # 按级别过滤
                        if level and entry["level"].upper() != level.upper():
                            continue
                        # 按关键词过滤
                        if keyword and keyword.lower() not in entry["message"].lower():
                            continue
                        log_entries.append(LogEntry(**entry))
        except Exception as e:
            logger.warning(f"[API] 读取日志失败: {e}")

    return LogsResponse(
        total_lines=len(log_entries),
        lines=log_entries[-lines:],
    )


@router.get("/logs/download")
async def download_logs():
    """下载完整日志文件"""
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    log_dir = os.path.join(project_root, "outputs", "logs")

    log_files = []
    if os.path.exists(log_dir):
        log_files = sorted(
            glob.glob(os.path.join(log_dir, "*.log")),
            key=os.path.getmtime,
            reverse=True,
        )

    if not log_files:
        raise HTTPException(status_code=404, detail="没有找到日志文件")

    latest_log = log_files[0]
    with open(latest_log, "r", encoding="utf-8") as f:
        content = f.read()

    return PlainTextResponse(
        content=content,
        media_type="text/plain",
        headers={"Content-Disposition": f"attachment; filename={os.path.basename(latest_log)}"},
    )


@router.delete("/logs")
async def clear_logs():
    """清空日志"""
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    log_dir = os.path.join(project_root, "outputs", "logs")

    if os.path.exists(log_dir):
        for log_file in glob.glob(os.path.join(log_dir, "*.log")):
            try:
                open(log_file, "w").close()
            except Exception as e:
                logger.warning(f"[API] 清空日志失败: {log_file} - {e}")

    return {"message": "日志已清空"}


def _parse_log_line(line: str) -> Optional[dict]:
    """解析单行日志"""
    import re
    # 匹配 loguru 默认格式: 2024-01-01 12:00:00.000 | LEVEL | module:func:line - message
    pattern = r'^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d+)\s*\|\s*(\w+)\s*\|\s*(.+?)\s*-\s*(.+)$'
    match = re.match(pattern, line.strip())
    if match:
        return {
            "timestamp": match.group(1),
            "level": match.group(2),
            "source": match.group(3),
            "message": match.group(4),
        }

    # 简单回退
    return {
        "timestamp": "",
        "level": "INFO",
        "source": "",
        "message": line.strip(),
    }
