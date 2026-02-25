"""
Email 同步 Worker
- 定時從 Gmail/IMAP 同步新信件
- 觸發 LLM 摘要分析
"""
import asyncio
import logging
from datetime import datetime
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import AsyncSessionLocal
from app.models.email import EmailAccount, EmailMessage, EmailSyncState
from app.models.summary import EmailSummary
from app.services import gmail_service, crypto_service
from app.services.llm_service import LLMService

logger = logging.getLogger(__name__)

# ── 本地模型前綴：Ollama 沒有啟動時自動降級到雲端模型 ─────────────
_LOCAL_MODEL_PREFIXES = ("llama", "mistral", "ollama", "phi", "gemma", "qwen")
_CLOUD_FALLBACK_MODEL = "claude-haiku"


def _resolve_model(model: str) -> str:
    """若 model 是本地模型（Ollama）名稱，改用雲端備援模型。"""
    if model.endswith("-local") or model.lower().startswith(_LOCAL_MODEL_PREFIXES):
        logger.warning(
            f"模型 '{model}' 是本地模型，Ollama 可能未啟動，"
            f"自動改用 '{_CLOUD_FALLBACK_MODEL}'"
        )
        return _CLOUD_FALLBACK_MODEL
    return model


async def sync_all_accounts():
    """同步所有啟用中的帳號"""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(EmailAccount).where(
                EmailAccount.is_active == True,
                EmailAccount.sync_enabled == True,
            )
        )
        accounts = result.scalars().all()
        account_ids = [a.id for a in accounts]
        logger.info(f"開始同步 {len(account_ids)} 個帳號")

    for account_id in account_ids:
        try:
            await sync_account(account_id)
        except Exception as e:
            logger.error(f"帳號同步失敗 (id={account_id})", exc_info=True)


async def sync_account(account_id):
    """同步單一帳號的信件"""
    async with AsyncSessionLocal() as db:
        # eager load sync_state 和 user，避免 async lazy loading 問題
        result = await db.execute(
            select(EmailAccount)
            .where(EmailAccount.id == account_id)
            .options(
                selectinload(EmailAccount.sync_state),
                selectinload(EmailAccount.user),
            )
        )
        account = result.scalar_one_or_none()
        if not account:
            return

        if account.provider == "gmail":
            new_messages = await _sync_gmail(db, account)
        else:
            logger.warning(f"尚不支援 provider: {account.provider}")
            return

        # 更新同步時間
        account.last_synced_at = datetime.utcnow()
        account.sync_error = None
        await db.commit()

        logger.info(f"帳號 {account.email_address} 同步了 {len(new_messages)} 封新信")

        # 傳出 message id 清單，在外部另開 session 做 LLM 分析
        if new_messages:
            message_ids = [m.id for m in new_messages]

    # ── 補跑：找出還沒有摘要的舊信件（每次最多 20 封） ──────────────
    # 解決「信件已在 DB 但摘要分析失敗過」的情況
    async with AsyncSessionLocal() as db:
        backfill_result = await db.execute(
            select(EmailMessage.id)
            .outerjoin(EmailSummary, EmailSummary.message_id == EmailMessage.id)
            .where(
                EmailMessage.account_id == account_id,
                EmailSummary.message_id == None,   # noqa: E711 — SQLAlchemy 需要 ==
            )
            .order_by(desc(EmailMessage.received_at))
            .limit(20)
        )
        backfill_ids = backfill_result.scalars().all()

    if backfill_ids:
        logger.info(f"補跑 {len(backfill_ids)} 封未分析信件")

    # 合併新信 + 補跑清單（去重）
    new_ids = list(message_ids) if new_messages else []
    all_ids = new_ids + [i for i in backfill_ids if i not in set(new_ids)]

    if all_ids:
        await analyze_new_messages(all_ids)


async def _sync_gmail(db: AsyncSession, account: EmailAccount) -> list[EmailMessage]:
    """Gmail 增量同步"""
    # 解密 Token
    access_token = crypto_service.decrypt(account.encrypted_access_token or "")
    refresh_token = crypto_service.decrypt(account.encrypted_refresh_token or "")

    if not access_token:
        logger.warning(f"帳號 {account.email_address} 沒有 access token")
        return []

    # 建立 Gmail Service
    service = gmail_service.build_gmail_service(access_token, refresh_token)

    # 取得同步狀態（已 eager load）
    sync_state = account.sync_state
    after_history_id = sync_state.last_history_id if sync_state else None

    # 取得新信件清單
    message_refs = gmail_service.fetch_new_messages(
        service,
        max_results=50,
        after_history_id=after_history_id,
    )

    # workspace_id 從已 eager load 的 user 取得
    workspace_id = account.user.workspace_id if account.user else None

    new_messages = []
    for msg_ref in message_refs:
        try:
            # 取得信件詳細內容
            detail = gmail_service.get_message_detail(service, msg_ref["id"])

            # 檢查是否已存在
            existing = await db.execute(
                select(EmailMessage).where(
                    EmailMessage.account_id == account.id,
                    EmailMessage.provider_message_id == detail["provider_message_id"],
                )
            )
            if existing.scalar_one_or_none():
                continue

            # 建立新信件記錄
            msg = EmailMessage(
                account_id=account.id,
                workspace_id=workspace_id,
                **detail,
            )
            db.add(msg)
            new_messages.append(msg)

        except Exception:
            logger.error(f"取得信件 {msg_ref['id']} 失敗", exc_info=True)

    await db.flush()

    # 更新同步狀態
    latest_history_id = gmail_service.get_latest_history_id(service)
    if sync_state:
        sync_state.last_history_id = latest_history_id
        sync_state.last_synced_at = datetime.utcnow()
    else:
        sync_state = EmailSyncState(
            account_id=account.id,
            last_history_id=latest_history_id,
        )
        db.add(sync_state)

    await db.commit()
    return new_messages


async def _analyze_single_message(msg_id, llm: LLMService, semaphore: asyncio.Semaphore):
    """分析單封信件（獨立 session，由 semaphore 控制並行數量）"""
    async with semaphore:
        async with AsyncSessionLocal() as db:
            try:
                # 重新 load 信件（含帳號和 user）
                result = await db.execute(
                    select(EmailMessage)
                    .where(EmailMessage.id == msg_id)
                    .options(
                        selectinload(EmailMessage.account).selectinload(EmailAccount.user)
                    )
                )
                msg = result.scalar_one_or_none()
                if not msg:
                    logger.warning(f"找不到信件 {msg_id}，跳過")
                    return

                content = msg.body_plain or msg.snippet or msg.subject or ""
                if not content:
                    logger.warning(f"信件 {msg_id} 內容為空，跳過")
                    return

                account = msg.account
                user = account.user if account else None

                raw_model = (
                    account.model_override
                    or (user.default_model if user else None)
                    or "claude-haiku"
                )
                model = _resolve_model(raw_model)   # 本地模型自動降級
                style = (user.default_summary_style if user else None) or "bullet_points"
                language = (user.summary_language if user else None) or "zh-TW"

                # 一次 LLM call 拿齊所有資料（llm_service 已正規化型別）
                result_data = await llm.analyze_email(
                    content,
                    style=style,
                    model=model,
                    language=language,
                )

                # 更新信件 triage 評分（EmailMessage.action_required 是 Boolean）
                action_req_bool = bool(result_data.get("action_required", False))
                msg.urgency_score = result_data.get("urgency_score")
                msg.importance_score = result_data.get("importance_score")
                msg.action_required = action_req_bool
                msg.ai_category = result_data.get("category")
                msg.sentiment = result_data.get("sentiment")

                # 儲存摘要（EmailSummary.action_required 是 String(5)，需轉字串）
                summary = EmailSummary(
                    message_id=msg.id,
                    summary_text=result_data.get("summary", ""),
                    style=style,
                    urgency_score=result_data.get("urgency_score"),
                    importance_score=result_data.get("importance_score"),
                    action_required=str(action_req_bool),
                    ai_category=result_data.get("category"),
                    sentiment=result_data.get("sentiment"),
                    reply_suggestions=result_data.get("reply_suggestions", []),
                    model_used=result_data.get("model_used", model),
                    tokens_used=result_data.get("tokens_used"),
                    generation_ms=result_data.get("generation_ms"),
                )
                db.add(summary)
                await db.commit()

                logger.info(f"信件 {msg.id} 分析完成（urgency={msg.urgency_score}，"
                            f"model={model}，ms={result_data.get('generation_ms')}）")

            except Exception:
                await db.rollback()
                logger.error(f"信件 {msg_id} 分析失敗", exc_info=True)


async def analyze_new_messages(message_ids: list):
    """對新信件執行 LLM 分析（並行，最多 5 封同時進行）"""
    if not message_ids:
        return

    llm = LLMService()
    # Semaphore 限制最多同時 5 個 LLM 請求，避免超過 rate limit
    semaphore = asyncio.Semaphore(5)

    logger.info(f"開始並行分析 {len(message_ids)} 封信件（concurrency=5）")
    await asyncio.gather(
        *[_analyze_single_message(msg_id, llm, semaphore) for msg_id in message_ids],
        return_exceptions=True,  # 單封失敗不中斷其他封
    )
    logger.info(f"批次分析完成，共 {len(message_ids)} 封")
