import uuid
from datetime import datetime
from sqlalchemy import (
    String, DateTime, Boolean, Text, Integer, Float,
    ForeignKey, Index, BigInteger
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, ARRAY, TSVECTOR
from app.core.database import Base


class EmailAccount(Base):
    """連接的信箱帳號"""
    __tablename__ = "email_accounts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    provider: Mapped[str] = mapped_column(String(50), nullable=False)  # gmail, outlook, imap
    email_address: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(255))

    # 加密儲存的 OAuth Tokens
    encrypted_access_token: Mapped[str | None] = mapped_column(Text)
    encrypted_refresh_token: Mapped[str | None] = mapped_column(Text)
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime)

    # 同步設定
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sync_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime)
    sync_error: Mapped[str | None] = mapped_column(Text)

    # 模型覆寫（此帳號可指定不同模型）
    model_override: Mapped[str | None] = mapped_column(String(100))

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="email_accounts")
    sync_state: Mapped["EmailSyncState | None"] = relationship(
        "EmailSyncState", back_populates="account", uselist=False
    )
    messages: Mapped[list["EmailMessage"]] = relationship(
        "EmailMessage", back_populates="account"
    )

    __table_args__ = (
        Index("ix_email_accounts_user_id", "user_id"),
        Index("ix_email_accounts_email", "email_address"),
    )


class EmailSyncState(Base):
    """各 Provider 的增量同步狀態"""
    __tablename__ = "email_sync_states"

    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("email_accounts.id"), primary_key=True
    )
    # Gmail 專用
    last_history_id: Mapped[int | None] = mapped_column(BigInteger)
    # Outlook 專用
    last_delta_token: Mapped[str | None] = mapped_column(String(500))
    # IMAP 專用
    last_uidvalidity: Mapped[int | None] = mapped_column(BigInteger)
    last_uidnext: Mapped[int | None] = mapped_column(BigInteger)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    account: Mapped["EmailAccount"] = relationship("EmailAccount", back_populates="sync_state")


class EmailMessage(Base):
    """儲存的信件"""
    __tablename__ = "email_messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("email_accounts.id"), nullable=False
    )

    # Provider 原始 ID
    provider_message_id: Mapped[str] = mapped_column(String(500), nullable=False)

    # Thread 群組（Plan Agent 強調要從一開始就加）
    thread_id: Mapped[str | None] = mapped_column(String(500))
    position_in_thread: Mapped[int] = mapped_column(Integer, default=1)
    in_reply_to: Mapped[str | None] = mapped_column(String(500))

    # 基本欄位
    subject: Mapped[str | None] = mapped_column(Text)
    sender: Mapped[str | None] = mapped_column(String(500))
    sender_name: Mapped[str | None] = mapped_column(String(255))
    recipients: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    cc: Mapped[list[str] | None] = mapped_column(ARRAY(Text))

    # 信件內容
    body_plain: Mapped[str | None] = mapped_column(Text)
    body_html: Mapped[str | None] = mapped_column(Text)
    snippet: Mapped[str | None] = mapped_column(Text)  # 前 200 字

    # 元資料
    has_attachments: Mapped[bool] = mapped_column(Boolean, default=False)
    labels: Mapped[list[str] | None] = mapped_column(ARRAY(String(100)))
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    is_starred: Mapped[bool] = mapped_column(Boolean, default=False)

    # AI 分析結果（triage scoring）
    urgency_score: Mapped[int | None] = mapped_column(Integer)     # 1-5
    importance_score: Mapped[int | None] = mapped_column(Integer)  # 1-5
    action_required: Mapped[bool | None] = mapped_column(Boolean)
    ai_category: Mapped[str | None] = mapped_column(String(100))
    sentiment: Mapped[str | None] = mapped_column(String(20))      # positive/neutral/negative

    # 全文搜尋向量
    search_vector: Mapped[str | None] = mapped_column(TSVECTOR)

    # Workspace 預留
    workspace_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))

    received_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    account: Mapped["EmailAccount"] = relationship("EmailAccount", back_populates="messages")
    summary: Mapped["EmailSummary | None"] = relationship(
        "EmailSummary", back_populates="message", uselist=False
    )
    topics: Mapped[list["EmailTopic"]] = relationship("EmailTopic", back_populates="message")

    __table_args__ = (
        Index("ix_email_messages_account_received", "account_id", "received_at"),
        Index("ix_email_messages_thread_id", "thread_id"),
        Index("ix_email_messages_urgency", "urgency_score"),
        Index("ix_email_messages_search", "search_vector", postgresql_using="gin"),
        Index(
            "ix_email_messages_provider_unique",
            "account_id", "provider_message_id",
            unique=True
        ),
    )
