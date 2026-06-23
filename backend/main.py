#!/usr/bin/env python3
# ============================================================
# backend/main.py — FastAPI 服务入口
# 启动: uvicorn main:app --host 0.0.0.0 --port 8000 --reload
# ============================================================
import sys
import os

# 将 Math-Agent-System 根目录加入 sys.path (因为 backend 是其子目录)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from api.problems import router as problems_router
from api.solve import router as solve_router
from api.tasks import router as tasks_router
from api.benchmark import router as benchmark_router
from api.logs import router as logs_router
from api.config import router as config_router
from api.dashboard import router as dashboard_router

# ============================================================
# 创建 FastAPI 应用
# ============================================================
app = FastAPI(
    title="Math-Agent-System API",
    description="基于 LangGraph + Intern-S1 的多领域数学自动求解智能体系统",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# ============================================================
# CORS 配置 (允许前端跨域)
# ============================================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
# 注册路由
# ============================================================
app.include_router(dashboard_router, prefix="/api", tags=["Dashboard"])
app.include_router(problems_router, prefix="/api", tags=["Problems"])
app.include_router(solve_router, prefix="/api", tags=["Solve"])
app.include_router(tasks_router, prefix="/api", tags=["Tasks"])
app.include_router(benchmark_router, prefix="/api", tags=["Benchmark"])
app.include_router(logs_router, prefix="/api", tags=["Logs"])
app.include_router(config_router, prefix="/api", tags=["Config"])


# ============================================================
# 根路径
# ============================================================
@app.get("/")
def root():
    return {
        "service": "Math-Agent-System API",
        "version": "1.0.0",
        "docs": "/api/docs",
    }


@app.get("/api/health")
def health_check():
    """健康检查"""
    return {"status": "ok", "service": "Math-Agent-System"}


# ============================================================
# 启动入口
# ============================================================
if __name__ == "__main__":
    import uvicorn

    logger.info("Starting Math-Agent-System API Server...")
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
