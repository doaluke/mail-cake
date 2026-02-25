import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Text, Integer, Float, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from app.core.database import Base


class EmailSummary(Base):
    """AI 摘要結果"""
    __tablename__ = "email_summaries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("email_messages.id"), nullable=False, unique=True
    )

    # 摘要內容
    summary_text: Mapped[str] = mapped_column(Text, nullable=False)
    style: Mapped[str] = mapped_column(String(50), nullable=False)  # bullet_points, executive...

    # 分流評分（一次 LLM call 拿齊）
    urgency_score: Mapped[int | None] = mapped_column(Integer)    # 1-5
    importance_score: Mapped[int | None] = mapped_column(Integer) # 1-5
    action_required: Mapped[bool | None] = mapped_column(String(5))
    ai_category: Mapped[str | None] = mapped_column(String(100))
    sentiment: Mapped[str | None] = mapped_column(String(20))

    # Smart Reply 建議（3選項）
    reply_suggestions: Mapped[list | None] = mapped_column(JSON)

    # LLM 使用資訊
    model_used: Mapped[str] = mapped_column(String(100))
    tokens_used: Mapped[int | None] = mapped_column(Integer)
    generation_ms: Mapped[int | None] = mapped_column(Integer)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    message: Mapped["EmailMessage"] = relationship("EmailMessage", back_populates="summary")
