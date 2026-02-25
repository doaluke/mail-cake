"""
Email API - 取得信件清單、摘要、Thread
"""
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select, and_, or_, func, desc
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.email import EmailMessage, EmailAccount
from app.models.summary import EmailSummary
from app.models.user import User
from app.api.v1.auth import get_current_user
from app.services.llm_service import LLMService

router = APIRouter(prefix="/emails")


@router.get("")
async def list_emails(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    urgency_min: Optional[int] = Query(None, ge=1, le=5),
    category: Optional[str] = None,
    action_required: Optional[bool] = None,
    sender: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """取得信件清單（含摘要、支援搜尋與篩選）"""
    # 取得用戶的所有帳號 ID
    result = await db.execute(
        select(EmailAccount.id).where(EmailAccount.user_id == current_user.id)
    )
    account_ids = result.scalars().all()

    if not account_ids:
        return {"emails": [], "total": 0, "page": page, "page_size": page_size}

    # 建立查詢
    query = (
        select(EmailMessage)
        .where(EmailMessage.account_id.in_(account_ids))
        .options(selectinload(EmailMessage.summary))
    )

    # 搜尋條件
    if search:
        query = query.where(
            or_(
                EmailMessage.subject.ilike(f"%{search}%"),
                EmailMessage.sender.ilike(f"%{search}%"),
                EmailMessage.snippet.ilike(f"%{search}%"),
            )
        )
    if urgency_min:
        query = query.where(EmailMessage.urgency_score >= urgency_min)
    if category:
        query = query.where(EmailMessage.ai_category == category)
    if action_required is not None:
        query = query.where(EmailMessage.action_required == action_required)
    if sender:
        query = query.where(EmailMessage.sender.ilike(f"%{sender}%"))

    # 計算總數
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    # 分頁排序
    query = (
        query
        .order_by(desc(EmailMessage.received_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    result = await db.execute(query)
    messages = result.scalars().all()

    return {
        "emails": [_format_email(m) for m in messages],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/threads")
async def list_threads(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """取得 Thread 群組清單"""
    result = await db.execute(
        select(EmailAccount.id).where(EmailAccount.user_id == current_user.id)
    )
    account_ids = result.scalars().all()

    if not account_ids:
        return {"threads": [], "total": 0}

    # 每個 thread 取最新的一封信
    thread_query = (
        select(
            EmailMessage.thread_id,
            func.count(EmailMessage.id).label("message_count"),
            func.max(EmailMessage.received_at).label("latest_at"),
            func.max(EmailMessage.urgency_score).label("max_urgency"),
        )
        .where(
            EmailMessage.account_id.in_(account_ids),
            EmailMessage.thread_id.is_not(None),
        )
        .group_by(EmailMessage.thread_id)
        .order_by(desc("latest_at"))
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    result = await db.execute(thread_query)
    threads_data = result.all()

    threads = []
    for row in threads_data:
        # 取此 thread 最新的一封信
        latest_msg_result = await db.execute(
            select(EmailMessage)
            .where(EmailMessage.thread_id == row.thread_id)
            .options(selectinload(EmailMessage.summary))
            .order_by(desc(EmailMessage.received_at))
            .limit(1)
        )
        latest_msg = latest_msg_result.scalar_one_or_none()
        if not latest_msg:
            continue

        threads.append({
            "thread_id": row.thread_id,
            "message_count": row.message_count,
            "latest_at": row.latest_at.isoformat() if row.latest_at else None,
            "max_urgency": row.max_urgency,
            "subject": latest_msg.subject,
            "sender": latest_msg.sender,
            "snippet": latest_msg.snippet,
            "summary": latest_msg.summary.summary_text if latest_msg.summary else None,
        })

    return {"threads": threads, "total": len(threads)}


@router.get("/{email_id}")
async def get_email(
    email_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """取得單封信件詳情"""
    result = await db.execute(
        select(EmailMessage)
        .where(EmailMessage.id == email_id)
        .options(
            selectinload(EmailMessage.summary),
            selectinload(EmailMessage.account),
        )
    )
    msg = result.scalar_one_or_none()

    if not msg or msg.account.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="信件不存在")

    return _format_email(msg, include_body=True)


@router.post("/{email_id}/summarize")
async def summarize_email(
    email_id: uuid.UUID,
    style: str = "bullet_points",
    model: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """重新摘要（可切換風格/模型）"""
    result = await db.execute(
        select(EmailMessage)
        .where(EmailMessage.id == email_id)
        .options(selectinload(EmailMessage.account))
    )
    msg = result.scalar_one_or_none()

    if not msg or msg.account.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="信件不存在")

    content = msg.body_plain or msg.snippet or ""
    if not content:
        raise HTTPException(status_code=400, detail="信件內容為空")

    llm = LLMService()
    result_data = await llm.analyze_email(
        content,
        style=style,
        model=model or current_user.default_model,
        language=current_user.summary_language,
    )

    # 更新或建立摘要
    existing_result = await db.execute(
        select(EmailSummary).where(EmailSummary.message_id == email_id)
    )
    summary = existing_result.scalar_one_or_none()

    if summary:
        summary.summary_text = result_data["summary"]
        summary.style = style
        summary.model_used = result_data["model_used"]
        summary.tokens_used = result_data.get("tokens_used")
        summary.reply_suggestions = result_data.get("reply_suggestions", [])
    else:
        summary = EmailSummary(
            message_id=email_id,
            summary_text=result_data["summary"],
            style=style,
            model_used=result_data["model_used"],
            tokens_used=result_data.get("tokens_used"),
            reply_suggestions=result_data.get("reply_suggestions", []),
        )
        db.add(summary)

    await db.commit()
    return result_data


@router.get("/{email_id}/summarize/stream")
async def summarize_email_stream(
    email_id: uuid.UUID,
    style: str = "bullet_points",
    model: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Streaming 摘要 - 即時顯示生成過程"""
    result = await db.execute(
        select(EmailMessage)
        .where(EmailMessage.id == email_id)
        .options(selectinload(EmailMessage.account))
    )
    msg = result.scalar_one_or_none()

    if not msg or msg.account.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="信件不存在")

    content = msg.body_plain or msg.snippet or ""
    llm = LLMService()

    async def generate():
        async for chunk in llm.analyze_email_stream(
            content,
            style=style,
            model=model or current_user.default_model,
            language=current_user.summary_language,
        ):
            yield f"data: {chunk}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


def _format_email(msg: EmailMessage, include_body: bool = False) -> dict:
    data = {
        "id": str(msg.id),
        "thread_id": msg.thread_id,
        "subject": msg.subject,
        "sender": msg.sender,
        "sender_name": msg.sender_name,
        "recipients": msg.recipients,
        "snippet": msg.snippet,
        "has_attachments": msg.has_attachments,
        "labels": msg.labels,
        "is_read": msg.is_read,
        "is_starred": msg.is_starred,
        "urgency_score": msg.urgency_score,
        "importance_score": msg.importance_score,
        "action_required": msg.action_required,
        "ai_category": msg.ai_category,
        "sentiment": msg.sentiment,
        "received_at": msg.received_at.isoformat() if msg.received_at else None,
        "summary": {
            "text": msg.summary.summary_text,
            "style": msg.summary.style,
            "model_used": msg.summary.model_used,
            "reply_suggestions": msg.summary.reply_suggestions or [],
        } if msg.summary else None,
    }
    if include_body:
        data["body_plain"] = msg.body_plain
        data["body_html"] = msg.body_html
    return data
