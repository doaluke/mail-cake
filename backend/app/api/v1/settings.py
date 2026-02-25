"""
設定 API - LLM 模型切換、摘要風格、Digest 排程
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import User
from app.models.digest import DigestSchedule
from app.api.v1.auth import get_current_user
from app.services.llm_service import LLMService

router = APIRouter(prefix="/settings")

AVAILABLE_MODELS = [
    {"id": "claude-haiku",    "name": "Claude Haiku",    "provider": "Anthropic", "tier": "fast",      "cost": "低",  "best_for": ["電子報", "廣告信", "通知"]},
    {"id": "claude-sonnet",   "name": "Claude Sonnet",   "provider": "Anthropic", "tier": "balanced",  "cost": "中",  "best_for": ["工作信", "一般摘要"]},
    {"id": "gpt-4o-mini",     "name": "GPT-4o mini",     "provider": "OpenAI",    "tier": "fast",      "cost": "低",  "best_for": ["多語言", "帳單"]},
    {"id": "gpt-4o",          "name": "GPT-4o",          "provider": "OpenAI",    "tier": "powerful",  "cost": "高",  "best_for": ["複雜分析", "法律合約"]},
    {"id": "gemini-flash",    "name": "Gemini Flash",    "provider": "Google",    "tier": "fast",      "cost": "低",  "best_for": ["快速處理"]},
    {"id": "llama3.2-local",  "name": "Llama 3.2（本地）", "provider": "Ollama",  "tier": "private",   "cost": "免費", "best_for": ["隱私優先", "敏感信件"]},
    {"id": "mistral-local",   "name": "Mistral（本地）",  "provider": "Ollama",   "tier": "private",   "cost": "免費", "best_for": ["本地執行"]},
]

SUMMARY_STYLES = [
    {"id": "bullet_points", "name": "重點條列",  "icon": "list",      "description": "5-7 個重點，快速掌握"},
    {"id": "executive",     "name": "主管摘要",  "icon": "briefcase", "description": "100-150 字專業摘要"},
    {"id": "action_items",  "name": "待辦清單",  "icon": "check",     "description": "只列出需要行動的項目"},
    {"id": "detailed",      "name": "詳細筆記",  "icon": "document",  "description": "完整保留所有重要細節"},
    {"id": "one_liner",     "name": "一句話",    "icon": "flash",     "description": "30 字以內核心摘要"},
]


class LLMPreferenceUpdate(BaseModel):
    default_model: str | None = None
    default_summary_style: str | None = None
    summary_language: str | None = None


class DigestScheduleUpdate(BaseModel):
    is_enabled: bool | None = None
    frequency: str | None = None
    send_at_hour: int | None = None
    timezone: str | None = None
    recipient_email: str | None = None


@router.get("/models")
async def get_available_models():
    """取得可用 LLM 模型清單"""
    return {"models": AVAILABLE_MODELS}


@router.get("/styles")
async def get_summary_styles():
    """取得摘要風格清單"""
    return {"styles": SUMMARY_STYLES}


@router.put("/llm")
async def update_llm_preference(
    body: LLMPreferenceUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新 LLM 偏好設定"""
    if body.default_model:
        valid_ids = [m["id"] for m in AVAILABLE_MODELS]
        if body.default_model not in valid_ids:
            raise HTTPException(status_code=400, detail="不支援的模型")
        current_user.default_model = body.default_model

    if body.default_summary_style:
        valid_styles = [s["id"] for s in SUMMARY_STYLES]
        if body.default_summary_style not in valid_styles:
            raise HTTPException(status_code=400, detail="不支援的摘要風格")
        current_user.default_summary_style = body.default_summary_style

    if body.summary_language:
        current_user.summary_language = body.summary_language

    await db.commit()
    return {"message": "設定已更新", "model": current_user.default_model}


@router.get("/digest")
async def get_digest_schedule(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """取得 Digest 排程設定"""
    result = await db.execute(
        select(DigestSchedule).where(DigestSchedule.user_id == current_user.id)
    )
    schedule = result.scalar_one_or_none()

    if not schedule:
        return {
            "is_enabled": False,
            "frequency": "daily",
            "send_at_hour": 8,
            "timezone": "Asia/Taipei",
            "recipient_email": current_user.email,
        }

    return {
        "is_enabled": schedule.is_enabled,
        "frequency": schedule.frequency,
        "send_at_hour": schedule.send_at_hour,
        "timezone": schedule.timezone,
        "recipient_email": schedule.recipient_email or current_user.email,
    }


@router.put("/digest")
async def update_digest_schedule(
    body: DigestScheduleUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新 Digest 排程設定"""
    result = await db.execute(
        select(DigestSchedule).where(DigestSchedule.user_id == current_user.id)
    )
    schedule = result.scalar_one_or_none()

    if not schedule:
        schedule = DigestSchedule(user_id=current_user.id)
        db.add(schedule)

    if body.is_enabled is not None:
        schedule.is_enabled = body.is_enabled
    if body.frequency:
        schedule.frequency = body.frequency
    if body.send_at_hour is not None:
        schedule.send_at_hour = body.send_at_hour
    if body.timezone:
        schedule.timezone = body.timezone
    if body.recipient_email:
        schedule.recipient_email = body.recipient_email

    await db.commit()
    return {"message": "Digest 排程已更新"}
