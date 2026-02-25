"""
Digest Worker - 定時發送摘要信件
"""
import logging
from datetime import datetime, timedelta
from jinja2 import Template
import aiosmtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.database import AsyncSessionLocal
from app.models.digest import DigestSchedule, DigestLog
from app.models.email import EmailMessage
from app.models.summary import EmailSummary

settings = get_settings()
logger = logging.getLogger(__name__)

DIGEST_HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body { font-family: -apple-system, sans-serif; max-width: 640px; margin: 0 auto; padding: 20px; color: #1a1a1a; }
    .header { background: #6366f1; color: white; padding: 20px; border-radius: 12px; margin-bottom: 24px; }
    .header h1 { margin: 0; font-size: 20px; }
    .header p { margin: 8px 0 0; opacity: 0.85; font-size: 14px; }
    .stats { display: flex; gap: 16px; margin-bottom: 24px; }
    .stat { background: #f5f5f5; border-radius: 8px; padding: 12px 16px; flex: 1; text-align: center; }
    .stat-num { font-size: 24px; font-weight: bold; color: #6366f1; }
    .stat-label { font-size: 12px; color: #666; margin-top: 4px; }
    .email-card { border: 1px solid #e5e7eb; border-radius: 8px; padding: 16px; margin-bottom: 12px; }
    .email-card.urgent { border-left: 4px solid #ef4444; }
    .email-card.important { border-left: 4px solid #f59e0b; }
    .email-subject { font-weight: 600; margin-bottom: 4px; }
    .email-sender { font-size: 13px; color: #666; margin-bottom: 8px; }
    .email-summary { font-size: 14px; line-height: 1.6; color: #374151; }
    .email-replies { margin-top: 12px; display: flex; gap: 8px; flex-wrap: wrap; }
    .reply-btn { background: #f3f4f6; border: 1px solid #d1d5db; border-radius: 6px; padding: 4px 10px; font-size: 12px; color: #374151; }
    .footer { margin-top: 32px; padding-top: 16px; border-top: 1px solid #e5e7eb; font-size: 12px; color: #9ca3af; text-align: center; }
  </style>
</head>
<body>
  <div class="header">
    <h1>📬 MailCake 每日摘要</h1>
    <p>{{ date_range }} · 由 AI 整理</p>
  </div>

  <div class="stats">
    <div class="stat">
      <div class="stat-num">{{ total_emails }}</div>
      <div class="stat-label">封信件</div>
    </div>
    <div class="stat">
      <div class="stat-num">{{ action_count }}</div>
      <div class="stat-label">需要行動</div>
    </div>
    <div class="stat">
      <div class="stat-num">{{ urgent_count }}</div>
      <div class="stat-label">緊急信件</div>
    </div>
  </div>

  {% if urgent_emails %}
  <h2 style="font-size: 16px; color: #ef4444;">⚡ 需要立即處理</h2>
  {% for item in urgent_emails %}
  <div class="email-card urgent">
    <div class="email-subject">{{ item.subject }}</div>
    <div class="email-sender">{{ item.sender }}</div>
    <div class="email-summary">{{ item.summary }}</div>
    {% if item.reply_suggestions %}
    <div class="email-replies">
      {% for reply in item.reply_suggestions[:2] %}
      <span class="reply-btn">{{ reply }}</span>
      {% endfor %}
    </div>
    {% endif %}
  </div>
  {% endfor %}
  {% endif %}

  {% if important_emails %}
  <h2 style="font-size: 16px; color: #f59e0b;">📌 重要信件</h2>
  {% for item in important_emails %}
  <div class="email-card important">
    <div class="email-subject">{{ item.subject }}</div>
    <div class="email-sender">{{ item.sender }}</div>
    <div class="email-summary">{{ item.summary }}</div>
  </div>
  {% endfor %}
  {% endif %}

  {% if other_emails %}
  <h2 style="font-size: 16px; color: #6b7280;">📋 其他信件</h2>
  {% for item in other_emails %}
  <div class="email-card">
    <div class="email-subject">{{ item.subject }}</div>
    <div class="email-sender">{{ item.sender }}</div>
    <div class="email-summary">{{ item.summary }}</div>
  </div>
  {% endfor %}
  {% endif %}

  <div class="footer">
    由 MailCake 生成 · <a href="{{ frontend_url }}/settings/digest">調整 Digest 設定</a>
  </div>
</body>
</html>
"""


async def send_digest_for_all_users():
    """檢查並發送所有需要發送的 Digest"""
    now = datetime.utcnow()
    current_hour = now.hour

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(DigestSchedule)
            .where(
                DigestSchedule.is_enabled == True,
                DigestSchedule.send_at_hour == current_hour,
            )
            .options(selectinload(DigestSchedule.user))
        )
        schedules = result.scalars().all()

    logger.info(f"準備發送 {len(schedules)} 個 Digest")

    for schedule in schedules:
        try:
            await send_digest(schedule.id)
        except Exception as e:
            logger.error(f"Digest 發送失敗 (user: {schedule.user_id}): {e}")
            async with AsyncSessionLocal() as db:
                log = DigestLog(
                    schedule_id=schedule.id,
                    status="failed",
                    error_message=str(e),
                )
                db.add(log)
                await db.commit()


async def send_digest(schedule_id):
    """發送單一用戶的 Digest"""
    async with AsyncSessionLocal() as db:
        schedule = await db.get(
            DigestSchedule, schedule_id,
            options=[selectinload(DigestSchedule.user)]
        )
        if not schedule or not schedule.user:
            return

        user = schedule.user

        # 取得過去 24 小時的信件
        since = datetime.utcnow() - timedelta(hours=24)

        result = await db.execute(
            select(EmailMessage)
            .join(EmailSummary, EmailSummary.message_id == EmailMessage.id)
            .where(
                EmailMessage.account_id.in_(
                    [a.id for a in user.email_accounts]
                ),
                EmailMessage.received_at >= since,
            )
            .options(selectinload(EmailMessage.summary))
            .order_by(EmailMessage.urgency_score.desc().nullslast())
        )
        messages = result.scalars().all()

        if not messages:
            logger.info(f"用戶 {user.email} 沒有新信件，跳過 Digest")
            return

        # 分類
        urgent = [m for m in messages if (m.urgency_score or 0) >= 4 and (m.action_required or False)]
        important = [m for m in messages if m not in urgent and (m.importance_score or 0) >= 4]
        others = [m for m in messages if m not in urgent and m not in important]

        def to_dict(m: EmailMessage):
            return {
                "subject": m.subject or "(無主旨)",
                "sender": m.sender or "",
                "summary": m.summary.summary_text if m.summary else "",
                "reply_suggestions": m.summary.reply_suggestions if m.summary else [],
            }

        # 渲染 HTML
        template = Template(DIGEST_HTML_TEMPLATE)
        html_content = template.render(
            date_range=f"{since.strftime('%m/%d')} - {datetime.utcnow().strftime('%m/%d')}",
            total_emails=len(messages),
            action_count=len([m for m in messages if m.action_required]),
            urgent_count=len(urgent),
            urgent_emails=[to_dict(m) for m in urgent[:5]],
            important_emails=[to_dict(m) for m in important[:5]],
            other_emails=[to_dict(m) for m in others[:10]],
            frontend_url=settings.frontend_url,
        )

        # 發送信件
        recipient = schedule.recipient_email or user.email
        await _send_email(
            to=recipient,
            subject=f"📬 MailCake 每日摘要 · {len(messages)} 封信件",
            html_content=html_content,
        )

        # 記錄發送
        log = DigestLog(
            schedule_id=schedule.id,
            status="sent",
            emails_included=len(messages),
        )
        db.add(log)
        await db.commit()

        logger.info(f"Digest 發送成功 → {recipient}（{len(messages)} 封信）")


async def _send_email(to: str, subject: str, html_content: str):
    """發送 Email（使用 SMTP）"""
    if not settings.smtp_user:
        logger.warning("SMTP 未設定，跳過發送")
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.smtp_user
    msg["To"] = to
    msg.attach(MIMEText(html_content, "html", "utf-8"))

    await aiosmtplib.send(
        msg,
        hostname=settings.smtp_host,
        port=settings.smtp_port,
        username=settings.smtp_user,
        password=settings.smtp_password,
        use_tls=False,
        start_tls=True,
    )
