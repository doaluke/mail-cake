import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Boolean, Text, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base


class DigestSchedule(Base):
    """Digest 排程設定"""
    __tablename__ = "digest_schedules"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))

    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    frequency: Mapped[str] = mapped_column(String(20), default="daily")  # daily, weekly
    send_at_hour: Mapped[int] = mapped_column(Integer, default=8)         # 08:00 發送
    timezone: Mapped[str] = mapped_column(String(50), default="Asia/Taipei")
    recipient_email: Mapped[str | None] = mapped_column(String(255))      # 預設用帳號 email

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    user: Mapped["User"] = relationship("User", back_populates="digest_schedules")
    logs: Mapped[list["DigestLog"]] = relationship(
        "DigestLog", back_populates="schedule", cascade="all, delete-orphan"
    )


class DigestLog(Base):
    """Digest 發送記錄"""
    __tablename__ = "digest_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    schedule_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("digest_schedules.id")
    )

    status: Mapped[str] = mapped_column(String(20))  # sent, failed, skipped
    emails_included: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)
    sent_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    schedule: Mapped["DigestSchedule"] = relationship("DigestSchedule", back_populates="logs")
