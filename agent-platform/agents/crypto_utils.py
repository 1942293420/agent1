"""
Agent 配置加密工具 — 使用 AES-256-GCM 加密敏感配置
+ 密码加密 — Fernet（管理员解密查看）
"""
import json, os, base64, hashlib
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.fernet import Fernet
from django.conf import settings


# ═══════════════════════════════════════════
# 配置加密（AES-GCM，原有）
# ═══════════════════════════════════════════

def _get_key():
    seed = os.environ.get('AGENT_CONFIG_KEY', 'agent-platform-secret-key-v1-32b')
    return hashlib.sha256(seed.encode()).digest()

def encrypt_config(data: dict) -> str:
    key = _get_key()
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    plaintext = json.dumps(data, ensure_ascii=False).encode('utf-8')
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)
    return base64.b64encode(nonce + ciphertext).decode('ascii')

def decrypt_config(encrypted: str) -> dict:
    if not encrypted:
        return {}
    key = _get_key()
    aesgcm = AESGCM(key)
    raw = base64.b64decode(encrypted)
    nonce, ciphertext = raw[:12], raw[12:]
    plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    return json.loads(plaintext.decode('utf-8'))

def mask_value(value: str, show: int = 4) -> str:
    if not value:
        return ''
    if len(value) <= show * 2 + 4:
        return value[:show] + '****'
    return value[:show] + '****' + value[-show:]

def mask_config(config: dict) -> dict:
    masked = {}
    for k, v in config.items():
        if isinstance(v, str) and len(v) > 10:
            masked[k] = mask_value(v)
        elif isinstance(v, dict):
            masked[k] = mask_config(v)
        else:
            masked[k] = v
    return masked


# ═══════════════════════════════════════════
# 密码加密（Fernet，管理员解密查看）
# ═══════════════════════════════════════════

def _get_fernet():
    key = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))

def encrypt_password(plaintext: str) -> str:
    f = _get_fernet()
    return f.encrypt(plaintext.encode()).decode()

def decrypt_password(ciphertext: str) -> str:
    f = _get_fernet()
    return f.decrypt(ciphertext.encode()).decode()
