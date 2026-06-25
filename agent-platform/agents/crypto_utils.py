"""
AES 加密工具 — 密码明文加密存储，仅管理员可解密

使用 Fernet（AES-128-CBC + HMAC），密钥从 Django SECRET_KEY 派生。
"""
import base64
import hashlib
from cryptography.fernet import Fernet
from django.conf import settings


def _get_fernet():
    """从 SECRET_KEY 派生 32 字节 Fernet 密钥"""
    key = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def encrypt_password(plaintext: str) -> str:
    """加密密码明文，返回 base64 字符串"""
    f = _get_fernet()
    return f.encrypt(plaintext.encode()).decode()


def decrypt_password(ciphertext: str) -> str:
    """解密，返回明文。失败抛异常。"""
    f = _get_fernet()
    return f.decrypt(ciphertext.encode()).decode()
