"""
Topics API - 管理用戶自定義的信件主題
"""
import uuid
import json
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Body
from pydantic import BaseModel
from sqlalchemy import select, func, desc
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.topic import Topic, EmailTopic
from app.models.email import EmailMessage, EmailAccount
from app.models.user import User
from app.api.v1.auth import get_current_user

router = APIRouter(prefix="/topics")


# ─── Pydantic Schemas ────────────────────────────────────────────


class TopicCreate(BaseModel):
    name: str
    description: Optional[str] = None
    color: str = "#6366f1"
    icon: str = "folder"
    model_override: Optional[str] = None
    style_override: Optional[str] = None
    auto_rules: Optional[dict] = None  # {"senders": [], "subject_contains": [], "labels": []}


class TopicUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    color: Optional[str] = None
    icon: Optional[str] = None
    model_override: Optional[str] = None
    style_override: Optional[str] = None
    auto_rules: Optional[dict] = None
    is_active: Optional[bool] = None


# ─── Endpoints ───────────────────────────────────────────────────


@router.get("")
async def list_topics(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """取得用戶的所有主題（含每個主題的信件數）"""
    result = await db.execute(
        select(Topic).where(
            Topic.user_id == current_user.id,
            Topic.is_active == True,
        ).order_by(Topic.created_at)
    )
    topics = result.scalars().all()

    # 批次查詢每個主題的信件數
    if topics:
        topic_ids = [t.id for t in topics]
        count_result = await db.execute(
            select(EmailTopic.topic_id, func.count(EmailTopic.message_id).label("count"))
            .where(EmailTopic.topic_id.in_(topic_ids))
            .group_by(EmailTopic.topic_id)
        )
        count_map = {row.topic_id: row.count for row in count_result.all()}
    else:
        count_map = {}

    return {
        "topics": [
            _format_topic(t, email_count=count_map.get(t.id, 0))
            for t in topics
        ]
    }


@router.post("")
async def create_topic(
    data: TopicCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """建立新主題"""
    topic = Topic(
        user_id=current_user.id,
        name=data.name,
        description=data.description,
        color=data.color,
        icon=data.icon,
        model_override=data.model_override,
        style_override=data.style_override,
        auto_rules=json.dumps(data.auto_rules) if data.auto_rules else None,
    )
    db.add(topic)
    await db.commit()
    await db.refresh(topic)
    return _format_topic(topic, email_count=0)


@router.get("/{topic_id}")
async def get_topic(
    topic_id: uuid.UUID,
    page: int = 1,
    page_size: int = 20,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """取得主題詳情（含分頁信件清單）"""
    topic = await _get_topic_or_404(topic_id, current_user.id, db)

    # 取得該主題的信件（分頁）
    email_query = (
        select(EmailMessage)
        .join(EmailTopic, EmailTopic.message_id == EmailMessage.id)
        .where(EmailTopic.topic_id == topic_id)
        .options(selectinload(EmailMessage.summary))
        .order_by(desc(EmailMessage.received_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(email_query)
    messages = result.scalars().all()

    # 總數
    count_result = await db.execute(
        select(func.count())
        .select_from(EmailTopic)
        .where(EmailTopic.topic_id == topic_id)
    )
    total = count_result.scalar_one()

    return {
        **_format_topic(topic, email_count=total),
        "emails": [_format_email(m) for m in messages],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.put("/{topic_id}")
async def update_topic(
    topic_id: uuid.UUID,
    data: TopicUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新主題設定"""
    topic = await _get_topic_or_404(topic_id, current_user.id, db)

    if data.name is not None:
        topic.name = data.name
    if data.description is not None:
        topic.description = data.description
    if data.color is not None:
        topic.color = data.color
    if data.icon is not None:
        topic.icon = data.icon
    if data.model_override is not None:
        topic.model_override = data.model_override
    if data.style_override is not None:
        topic.style_override = data.style_override
    if data.auto_rules is not None:
        topic.auto_rules = json.dumps(data.auto_rules)
    if data.is_active is not None:
        topic.is_active = data.is_active

    await db.commit()
    await db.refresh(topic)
    return _format_topic(topic)


@router.delete("/{topic_id}")
async def delete_topic(
    topic_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """刪除主題（軟刪除）"""
    topic = await _get_topic_or_404(topic_id, current_user.id, db)
    topic.is_active = False
    await db.commit()
    return {"ok": True}


@router.post("/{topic_id}/emails/{email_id}")
async def add_email_to_topic(
    topic_id: uuid.UUID,
    email_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """手動將信件加入主題"""
    topic = await _get_topic_or_404(topic_id, current_user.id, db)

    # 確認信件屬於此用戶
    email_result = await db.execute(
        select(EmailMessage)
        .join(EmailAccount, EmailAccount.id == EmailMessage.account_id)
        .where(
            EmailMessage.id == email_id,
            EmailAccount.user_id == current_user.id,
        )
    )
    msg = email_result.scalar_one_or_none()
    if not msg:
        raise HTTPException(status_code=404, detail="信件不存在")

    # 檢查是否已存在
    existing_result = await db.execute(
        select(EmailTopic).where(
            EmailTopic.topic_id == topic_id,
            EmailTopic.message_id == email_id,
        )
    )
    if existing_result.scalar_one_or_none():
        return {"ok": True, "message": "已在此主題中"}

    email_topic = EmailTopic(
        topic_id=topic_id,
        message_id=email_id,
        is_manual=True,
        confidence=1.0,
    )
    db.add(email_topic)
    await db.commit()
    return {"ok": True}


@router.delete("/{topic_id}/emails/{email_id}")
async def remove_email_from_topic(
    topic_id: uuid.UUID,
    email_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """從主題移除信件"""
    await _get_topic_or_404(topic_id, current_user.id, db)

    result = await db.execute(
        select(EmailTopic).where(
            EmailTopic.topic_id == topic_id,
            EmailTopic.message_id == email_id,
        )
    )
    email_topic = result.scalar_one_or_none()
    if not email_topic:
        raise HTTPException(status_code=404, detail="關聯不存在")

    await db.delete(email_topic)
    await db.commit()
    return {"ok": True}


# ─── Helpers ─────────────────────────────────────────────────────


async def _get_topic_or_404(
    topic_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession
) -> Topic:
    result = await db.execute(
        select(Topic).where(Topic.id == topic_id, Topic.user_id == user_id)
    )
    topic = result.scalar_one_or_none()
    if not topic:
        raise HTTPException(status_code=404, detail="主題不存在")
    return topic


def _format_topic(topic: Topic, email_count: int = 0) -> dict:
    auto_rules = None
    if topic.auto_rules:
        try:
            auto_rules = json.loads(topic.auto_rules)
        except Exception:
            pass

    return {
        "id": str(topic.id),
        "name": topic.name,
        "description": topic.description,
        "color": topic.color,
        "icon": topic.icon,
        "model_override": topic.model_override,
        "style_override": topic.style_override,
        "auto_rules": auto_rules,
        "is_active": topic.is_active,
        "email_count": email_count,
        "created_at": topic.created_at.isoformat() if topic.created_at else None,
    }


def _format_email(msg: EmailMessage) -> dict:
    return {
        "id": str(msg.id),
        "subject": msg.subject,
        "sender": msg.sender,
        "snippet": msg.snippet,
        "received_at": msg.received_at.isoformat() if msg.received_at else None,
        "urgency_score": msg.urgency_score,
        "importance_score": msg.importance_score,
        "action_required": msg.action_required,
        "ai_category": msg.ai_category,
        "is_read": msg.is_read,
        "summary": {
            "text": msg.summary.summary_text,
            "reply_suggestions": msg.summary.reply_suggestions or [],
        } if msg.summary else None,
    }
