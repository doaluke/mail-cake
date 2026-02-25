import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Text, Float, ForeignKey, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base


class Topic(Base):
    """用戶定義的主題（可設定不同模型/風格）"""
    __tablename__ = "topics"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    color: Mapped[str] = mapped_column(String(7), default="#6366f1")  # hex color
    icon: Mapped[str] = mapped_column(String(50), default="folder")

    # 此主題覆寫設定
    model_override: Mapped[str | None] = mapped_column(String(100))
    style_override: Mapped[str | None] = mapped_column(String(50))

    # 自動分類規則（JSON 格式）
    # {"senders": ["@company.com"], "subject_contains": ["invoice"], "labels": ["work"]}
    auto_rules: Mapped[str | None] = mapped_column(Text)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    emails: Mapped[list["EmailTopic"]] = relationship("EmailTopic", back_populates="topic")


class EmailTopic(Base):
    """信件和主題的多對多關聯"""
    __tablename__ = "email_topics"

    message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("email_messages.id"), primary_key=True
    )
    topic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("topics.id"), primary_key=True
    )
    confidence: Mapped[float | None] = mapped_column(Float)
    is_manual: Mapped[bool] = mapped_column(Boolean, default=False)  # 手動覆寫

    message: Mapped["EmailMessage"] = relationship("EmailMessage", back_populates="topics")
    topic: Mapped["Topic"] = relationship("Topic", back_populates="emails")
