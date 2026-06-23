# ============================================================
# api/config.py — 系统配置接口
# ============================================================
from fastapi import APIRouter, HTTPException
from loguru import logger

from .schemas import SystemConfigModel, ConfigUpdateRequest
from configs.settings import get_config, reset_config

router = APIRouter()


@router.get("/config", response_model=SystemConfigModel)
async def get_config_endpoint():
    """获取当前系统配置"""
    config = get_config()
    return SystemConfigModel(
        api_base_url=config.intern_s1.api_base_url,
        api_key=config.intern_s1.api_key[:12] + "****" if config.intern_s1.api_key else "",
        model_name=config.intern_s1.model_name,
        temperature=config.intern_s1.temperature,
        max_tokens=config.intern_s1.max_tokens,
        max_reflection_count=config.workflow.max_reflection_count,
        enable_rag=config.rag.enabled,
        solver_timeout=config.workflow.node_timeout_seconds,
        top_p=config.intern_s1.top_p,
    )


@router.put("/config")
async def update_config_endpoint(body: ConfigUpdateRequest):
    """更新系统配置 (部分更新)"""
    config = get_config()
    updates = body.model_dump(exclude_none=True)

    for key, value in updates.items():
        if key in ["api_base_url", "api_key", "model_name", "temperature", "max_tokens", "top_p"]:
            setattr(config.intern_s1, key, value)
        elif key == "max_reflection_count":
            config.workflow.max_reflection_count = value
        elif key == "enable_rag":
            config.rag.enabled = value
        elif key == "solver_timeout":
            config.workflow.node_timeout_seconds = value

    logger.info(f"[Config] 配置已更新: {list(updates.keys())}")

    # 如果 API 配置变更，重置客户端
    if any(k in updates for k in ["api_base_url", "api_key", "model_name"]):
        try:
            from tools.intern_client import reset_intern_client
            reset_intern_client()
            logger.info("[Config] API 客户端已重置")
        except Exception as e:
            logger.warning(f"[Config] 重置客户端失败: {e}")

    return {"message": "配置已更新", "updated_fields": list(updates.keys())}


@router.post("/config/reset")
async def reset_config_endpoint():
    """重置系统配置"""
    reset_config()
    return {"message": "配置已重置为默认值"}
