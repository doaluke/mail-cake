"""
Gmail OAuth 2.0 整合服務

只要求 readonly 權限，不修改用戶信件
"""
import base64
import email
from datetime import datetime, timezone
from typing import Optional

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.core.config import get_settings

settings = get_settings()

GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/userinfo.email",
    "openid",
]

GMAIL_READONLY_SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


def get_auth_url(state: str) -> str:
    """產生 Gmail OAuth 授權 URL"""
    from google_auth_oauthlib.flow import Flow

    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "redirect_uris": [settings.google_redirect_uri],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        },
        scopes=GMAIL_SCOPES,
    )
    flow.redirect_uri = settings.google_redirect_uri

    auth_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        state=state,
        prompt="consent",  # 確保取得 refresh_token
    )
    return auth_url


def exchange_code_for_tokens(code: str) -> dict:
    """用授權碼換取 access_token 和 refresh_token"""
    from google_auth_oauthlib.flow import Flow

    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "redirect_uris": [settings.google_redirect_uri],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        },
        scopes=GMAIL_SCOPES,
    )
    flow.redirect_uri = settings.google_redirect_uri
    flow.fetch_token(code=code)

    creds = flow.credentials
    return {
        "access_token": creds.token,
        "refresh_token": creds.refresh_token,
        "expires_at": creds.expiry,
        "email": _get_user_email(creds),
    }


def _get_user_email(creds: Credentials) -> str:
    """取得用戶 Gmail 地址"""
    from googleapiclient.discovery import build

    service = build("oauth2", "v2", credentials=creds)
    user_info = service.userinfo().get().execute()
    return user_info.get("email", "")


def build_gmail_service(access_token: str, refresh_token: str | None = None):
    """建立 Gmail API Service"""
    creds = Credentials(
        token=access_token,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
    )

    # 自動更新 Token
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())

    return build("gmail", "v1", credentials=creds)


def fetch_new_messages(
    service,
    max_results: int = 50,
    after_history_id: Optional[int] = None,
) -> list[dict]:
    """
    取得新信件清單
    首次同步：取最近 max_results 封
    增量同步：用 history_id 取得新增的信件
    """
    messages = []

    if after_history_id:
        # 增量同步
        try:
            history = (
                service.users()
                .history()
                .list(
                    userId="me",
                    startHistoryId=after_history_id,
                    historyTypes=["messageAdded"],
                )
                .execute()
            )
            for record in history.get("history", []):
                for msg in record.get("messagesAdded", []):
                    messages.append({"id": msg["message"]["id"]})
        except HttpError as e:
            if e.resp.status == 404:
                # history_id 過期，退回全量同步
                pass
            else:
                raise
    else:
        # 首次全量同步
        result = (
            service.users()
            .messages()
            .list(userId="me", maxResults=max_results, q="in:inbox")
            .execute()
        )
        messages = result.get("messages", [])

    return messages


def get_message_detail(service, message_id: str) -> dict:
    """取得信件完整內容"""
    msg = service.users().messages().get(
        userId="me",
        id=message_id,
        format="full"
    ).execute()

    headers = {h["name"].lower(): h["value"] for h in msg["payload"].get("headers", [])}

    body_plain, body_html = _extract_body(msg["payload"])

    return {
        "provider_message_id": msg["id"],
        "thread_id": msg.get("threadId"),
        "subject": headers.get("subject", "(無主旨)"),
        "sender": headers.get("from", ""),
        "recipients": _parse_email_list(headers.get("to", "")),
        "cc": _parse_email_list(headers.get("cc", "")),
        "in_reply_to": headers.get("in-reply-to"),
        "body_plain": body_plain,
        "body_html": body_html,
        "snippet": msg.get("snippet", "")[:300],
        "has_attachments": _has_attachments(msg["payload"]),
        "labels": msg.get("labelIds", []),
        "is_read": "UNREAD" not in msg.get("labelIds", []),
        "is_starred": "STARRED" in msg.get("labelIds", []),
        "received_at": _parse_date(headers.get("date")),
    }


def get_latest_history_id(service) -> int:
    """取得最新的 history_id，用於下次增量同步"""
    profile = service.users().getProfile(userId="me").execute()
    return int(profile.get("historyId", 0))


def _extract_body(payload: dict) -> tuple[str, str]:
    """從 Gmail payload 提取純文字和 HTML 內容"""
    plain, html = "", ""

    def extract_recursive(part):
        nonlocal plain, html
        mime_type = part.get("mimeType", "")

        if mime_type == "text/plain":
            data = part.get("body", {}).get("data", "")
            if data:
                plain = base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
        elif mime_type == "text/html":
            data = part.get("body", {}).get("data", "")
            if data:
                html = base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
        elif "parts" in part:
            for sub in part["parts"]:
                extract_recursive(sub)

    extract_recursive(payload)
    return plain, html


def _has_attachments(payload: dict) -> bool:
    """檢查是否有附件"""
    def check_recursive(part) -> bool:
        if part.get("filename") and part["filename"] != "":
            return True
        for sub in part.get("parts", []):
            if check_recursive(sub):
                return True
        return False
    return check_recursive(payload)


def _parse_email_list(header_value: str) -> list[str]:
    """解析信件地址字串"""
    if not header_value:
        return []
    return [addr.strip() for addr in header_value.split(",") if addr.strip()]


def _parse_date(date_str: str | None) -> datetime | None:
    """解析信件日期"""
    if not date_str:
        return None
    try:
        from email.utils import parsedate_to_datetime
        return parsedate_to_datetime(date_str).replace(tzinfo=None)
    except Exception:
        return None
