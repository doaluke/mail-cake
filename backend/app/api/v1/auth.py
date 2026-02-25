"""
認證 API - Gmail OAuth 流程
"""
import secrets
import uuid
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from jose import jwt, JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.models.user import User
from app.models.email import EmailAccount, EmailSyncState
from app.services import gmail_service, crypto_service

settings = get_settings()
router = APIRouter(prefix="/auth")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 天


def create_access_token(data: dict) -> str:
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode = {**data, "exp": expire}
    return jwt.encode(to_encode, settings.secret_key, algorithm=ALGORITHM)


async def get_current_user(request: Request, db: AsyncSession = Depends(get_db)) -> User:
    token = request.cookies.get("access_token") or request.headers.get(
        "Authorization", ""
    ).replace("Bearer ", "")

    if not token:
        raise HTTPException(status_code=401, detail="未登入")

    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Token 無效")
    except JWTError:
        raise HTTPException(status_code=401, detail="Token 無效")

    user = await db.get(User, uuid.UUID(user_id))
    if not user:
        raise HTTPException(status_code=401, detail="用戶不存在")
    return user


@router.get("/gmail")
async def gmail_login():
    """啟動 Gmail OAuth 流程"""
    state = secrets.token_urlsafe(32)
    auth_url = gmail_service.get_auth_url(state)
    return {"auth_url": auth_url, "state": state}


@router.get("/gmail/callback")
async def gmail_callback(
    code: str,
    state: str,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """Gmail OAuth Callback"""
    try:
        token_data = gmail_service.exchange_code_for_tokens(code)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"OAuth 失敗: {str(e)}")

    email_address = token_data["email"]

    # 找或建立用戶
    result = await db.execute(select(User).where(User.email == email_address))
    user = result.scalar_one_or_none()

    if not user:
        user = User(email=email_address, name=email_address.split("@")[0])
        db.add(user)
        await db.flush()

    # 找或建立 EmailAccount
    result = await db.execute(
        select(EmailAccount).where(
            EmailAccount.user_id == user.id,
            EmailAccount.email_address == email_address,
            EmailAccount.provider == "gmail",
        )
    )
    account = result.scalar_one_or_none()

    if not account:
        account = EmailAccount(
            user_id=user.id,
            provider="gmail",
            email_address=email_address,
            display_name=email_address,
        )
        db.add(account)
        await db.flush()

    # 加密儲存 Token
    account.encrypted_access_token = crypto_service.encrypt(token_data["access_token"])
    if token_data.get("refresh_token"):
        account.encrypted_refresh_token = crypto_service.encrypt(token_data["refresh_token"])
    account.token_expires_at = token_data.get("expires_at")
    account.is_active = True

    await db.commit()

    # 立即觸發一次同步
    from app.workers.email_sync import sync_account
    import asyncio
    asyncio.create_task(sync_account(account.id))

    # 設定 JWT Cookie
    access_token = create_access_token({"sub": str(user.id)})
    redirect = RedirectResponse(url=f"{settings.frontend_url}/dashboard")
    redirect.set_cookie(
        "access_token",
        access_token,
        httponly=True,
        samesite="lax",
        max_age=60 * 60 * 24 * 7,
    )
    return redirect


@router.get("/me")
async def get_me(current_user: User = Depends(get_current_user)):
    return {
        "id": str(current_user.id),
        "email": current_user.email,
        "name": current_user.name,
        "default_model": current_user.default_model,
        "default_summary_style": current_user.default_summary_style,
        "summary_language": current_user.summary_language,
    }


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie("access_token")
    return {"message": "已登出"}
