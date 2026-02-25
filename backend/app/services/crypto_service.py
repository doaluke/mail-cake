"""加密服務 - 用於安全儲存 OAuth Token"""
import base64
from cryptography.fernet import Fernet
from app.core.config import get_settings

settings = get_settings()


def _get_fernet() -> Fernet:
    # 從 SECRET_KEY 派生固定長度的加密 Key
    key = settings.secret_key.encode()[:32].ljust(32, b"0")
    encoded_key = base64.urlsafe_b64encode(key)
    return Fernet(encoded_key)


def encrypt(text: str) -> str:
    """加密字串"""
    if not text:
        return ""
    f = _get_fernet()
    return f.encrypt(text.encode()).decode()


def decrypt(encrypted_text: str) -> str:
    """解密字串"""
    if not encrypted_text:
        return ""
    f = _get_fernet()
    return f.decrypt(encrypted_text.encode()).decode()
