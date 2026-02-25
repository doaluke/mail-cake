import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Boolean, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    name: Mapped[str | None] = mapped_column(String(255))
    avatar_url: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # LLM 偏好設定
    default_model: Mapped[str] = mapped_column(String(100), default="claude-haiku")
    default_summary_style: Mapped[str] = mapped_column(String(50), default="bullet_points")
    summary_language: Mapped[str] = mapped_column(String(10), default="zh-TW")

    # Workspace（預留協作功能）
    workspace_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    email_accounts: Mapped[list["EmailAccount"]] = relationship(
        "EmailAccount", back_populates="user", cascade="all, delete-orphan"
    )
    digest_schedules: Mapped[list["DigestSchedule"]] = relationship(
        "DigestSchedule", back_populates="user", cascade="all, delete-orphan"
    )
