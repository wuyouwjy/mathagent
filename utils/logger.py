# ============================================================
# utils/logger.py — 统一日志管理
# 基于 loguru 的日志配置，支持彩色终端输出 + 文件日志
# ============================================================

import sys
import os
from loguru import logger


def setup_logger(
    log_dir: str = "./outputs/logs",
    log_level: str = "INFO",
    rotation: str = "100 MB",
    retention: str = "7 days",
    enable_file: bool = True,
    enable_console: bool = True,
    experiment_name: str = "math-agent",
) -> None:
    """
    配置全局日志系统

    参数:
        log_dir: 日志文件目录
        log_level: 日志级别（DEBUG / INFO / WARNING / ERROR）
        rotation: 日志文件轮转策略
        retention: 日志保留时间
        enable_file: 是否启用文件日志
        enable_console: 是否启用终端日志
        experiment_name: 实验名称（用于日志文件名）
    """
    # --- 移除默认 handler ---
    logger.remove()

    # --- 终端输出（彩色） ---
    if enable_console:
        logger.add(
            sys.stderr,
            format=(
                "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
                "<level>{level: <8}</level> | "
                "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
                "<level>{message}</level>"
            ),
            level=log_level,
            colorize=True,
            enqueue=True,
        )

    # --- 文件输出 ---
    if enable_file:
        os.makedirs(log_dir, exist_ok=True)

        # 普通日志文件
        logger.add(
            os.path.join(log_dir, f"{experiment_name}.log"),
            format=(
                "{time:YYYY-MM-DD HH:mm:ss.SSS} | "
                "{level: <8} | "
                "{name}:{function}:{line} - "
                "{message}"
            ),
            level=log_level,
            rotation=rotation,
            retention=retention,
            encoding="utf-8",
            enqueue=True,
        )

        # 错误日志单独文件
        logger.add(
            os.path.join(log_dir, f"{experiment_name}_error.log"),
            format=(
                "{time:YYYY-MM-DD HH:mm:ss.SSS} | "
                "{level: <8} | "
                "{name}:{function}:{line} - "
                "{message}"
            ),
            level="ERROR",
            rotation=rotation,
            retention=retention,
            encoding="utf-8",
            enqueue=True,
        )

    logger.info(f"[日志系统] 已初始化: level={log_level}, dir={log_dir}")


def get_logger():
    """获取 loguru logger 实例"""
    return logger
