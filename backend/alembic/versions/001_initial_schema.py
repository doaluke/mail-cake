"""Initial schema

Revision ID: 001
Revises:
Create Date: 2026-02-24

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # users
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("avatar_url", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, default=True),
        sa.Column("default_model", sa.String(100), default="claude-haiku"),
        sa.Column("default_summary_style", sa.String(50), default="bullet_points"),
        sa.Column("summary_language", sa.String(10), default="zh-TW"),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )

    # email_accounts
    op.create_table(
        "email_accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("email_address", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=True),
        sa.Column("encrypted_access_token", sa.Text, nullable=True),
        sa.Column("encrypted_refresh_token", sa.Text, nullable=True),
        sa.Column("token_expires_at", sa.DateTime, nullable=True),
        sa.Column("is_active", sa.Boolean, default=True),
        sa.Column("sync_enabled", sa.Boolean, default=True),
        sa.Column("last_synced_at", sa.DateTime, nullable=True),
        sa.Column("sync_error", sa.Text, nullable=True),
        sa.Column("model_override", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_email_accounts_user_id", "email_accounts", ["user_id"])

    # email_sync_states
    op.create_table(
        "email_sync_states",
        sa.Column("account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("email_accounts.id"), primary_key=True),
        sa.Column("last_history_id", sa.BigInteger, nullable=True),
        sa.Column("last_delta_token", sa.String(500), nullable=True),
        sa.Column("last_uidvalidity", sa.BigInteger, nullable=True),
        sa.Column("last_uidnext", sa.BigInteger, nullable=True),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )

    # email_messages
    op.create_table(
        "email_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("email_accounts.id"), nullable=False),
        sa.Column("provider_message_id", sa.String(500), nullable=False),
        sa.Column("thread_id", sa.String(500), nullable=True),
        sa.Column("position_in_thread", sa.Integer, default=1),
        sa.Column("in_reply_to", sa.String(500), nullable=True),
        sa.Column("subject", sa.Text, nullable=True),
        sa.Column("sender", sa.String(500), nullable=True),
        sa.Column("sender_name", sa.String(255), nullable=True),
        sa.Column("recipients", postgresql.ARRAY(sa.Text), nullable=True),
        sa.Column("cc", postgresql.ARRAY(sa.Text), nullable=True),
        sa.Column("body_plain", sa.Text, nullable=True),
        sa.Column("body_html", sa.Text, nullable=True),
        sa.Column("snippet", sa.Text, nullable=True),
        sa.Column("has_attachments", sa.Boolean, default=False),
        sa.Column("labels", postgresql.ARRAY(sa.String(100)), nullable=True),
        sa.Column("is_read", sa.Boolean, default=False),
        sa.Column("is_starred", sa.Boolean, default=False),
        sa.Column("urgency_score", sa.Integer, nullable=True),
        sa.Column("importance_score", sa.Integer, nullable=True),
        sa.Column("action_required", sa.Boolean, nullable=True),
        sa.Column("ai_category", sa.String(100), nullable=True),
        sa.Column("sentiment", sa.String(20), nullable=True),
        sa.Column("search_vector", postgresql.TSVECTOR, nullable=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("received_at", sa.DateTime, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_email_messages_account_received", "email_messages", ["account_id", "received_at"])
    op.create_index("ix_email_messages_thread_id", "email_messages", ["thread_id"])
    op.create_index("ix_email_messages_urgency", "email_messages", ["urgency_score"])
    op.create_index("ix_email_messages_search", "email_messages", ["search_vector"], postgresql_using="gin")
    op.create_index("ix_email_messages_provider_unique", "email_messages", ["account_id", "provider_message_id"], unique=True)

    # email_summaries
    op.create_table(
        "email_summaries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("message_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("email_messages.id"), nullable=False, unique=True),
        sa.Column("summary_text", sa.Text, nullable=False),
        sa.Column("style", sa.String(50), nullable=False),
        sa.Column("urgency_score", sa.Integer, nullable=True),
        sa.Column("importance_score", sa.Integer, nullable=True),
        sa.Column("action_required", sa.String(5), nullable=True),
        sa.Column("ai_category", sa.String(100), nullable=True),
        sa.Column("sentiment", sa.String(20), nullable=True),
        sa.Column("reply_suggestions", postgresql.JSON, nullable=True),
        sa.Column("model_used", sa.String(100), nullable=False),
        sa.Column("tokens_used", sa.Integer, nullable=True),
        sa.Column("generation_ms", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )

    # topics
    op.create_table(
        "topics",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("color", sa.String(7), default="#6366f1"),
        sa.Column("icon", sa.String(50), default="folder"),
        sa.Column("model_override", sa.String(100), nullable=True),
        sa.Column("style_override", sa.String(50), nullable=True),
        sa.Column("auto_rules", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, default=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )

    # email_topics
    op.create_table(
        "email_topics",
        sa.Column("message_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("email_messages.id"), primary_key=True),
        sa.Column("topic_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("topics.id"), primary_key=True),
        sa.Column("confidence", sa.Float, nullable=True),
        sa.Column("is_manual", sa.Boolean, default=False),
    )

    # digest_schedules
    op.create_table(
        "digest_schedules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("is_enabled", sa.Boolean, default=True),
        sa.Column("frequency", sa.String(20), default="daily"),
        sa.Column("send_at_hour", sa.Integer, default=8),
        sa.Column("timezone", sa.String(50), default="Asia/Taipei"),
        sa.Column("recipient_email", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )

    # digest_logs
    op.create_table(
        "digest_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("schedule_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("digest_schedules.id"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("emails_included", sa.Integer, default=0),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("sent_at", sa.DateTime, nullable=False),
    )

    # 建立 search_vector 自動更新 trigger
    op.execute("""
        CREATE OR REPLACE FUNCTION update_email_search_vector()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.search_vector := to_tsvector('simple',
                coalesce(NEW.subject, '') || ' ' ||
                coalesce(NEW.sender, '') || ' ' ||
                coalesce(NEW.snippet, '')
            );
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE TRIGGER email_search_vector_update
        BEFORE INSERT OR UPDATE ON email_messages
        FOR EACH ROW EXECUTE FUNCTION update_email_search_vector();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS email_search_vector_update ON email_messages")
    op.execute("DROP FUNCTION IF EXISTS update_email_search_vector")
    op.drop_table("digest_logs")
    op.drop_table("digest_schedules")
    op.drop_table("email_topics")
    op.drop_table("topics")
    op.drop_table("email_summaries")
    op.drop_table("email_messages")
    op.drop_table("email_sync_states")
    op.drop_table("email_accounts")
    op.drop_table("users")
