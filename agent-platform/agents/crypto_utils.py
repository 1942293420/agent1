"""
Agent 配置加密工具 — 使用 AES-256-GCM 加密敏感配置
"""
import json, os, base64
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# 加密密钥（从环境变量或固定种子派生）
def _get_key():
    seed = os.environ.get('AGENT_CONFIG_KEY', 'agent-platform-secret-key-v1-32b')
    # 使用 SHA256 派生 32 字节密钥
    import hashlib
    return hashlib.sha256(seed.encode()).digest()

def encrypt_config(data: dict) -> str:
    """加密配置字典 → Base64 字符串"""
    key = _get_key()
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    plaintext = json.dumps(data, ensure_ascii=False).encode('utf-8')
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)
    return base64.b64encode(nonce + ciphertext).decode('ascii')

def decrypt_config(encrypted: str) -> dict:
    """解密 Base64 字符串 → 配置字典"""
    if not encrypted:
        return {}
    key = _get_key()
    aesgcm = AESGCM(key)
    raw = base64.b64decode(encrypted)
    nonce, ciphertext = raw[:12], raw[12:]
    plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    return json.loads(plaintext.decode('utf-8'))

def mask_value(value: str, show: int = 4) -> str:
    """脱敏显示：只保留前 show 和后 show 个字符"""
    if not value:
        return ''
    if len(value) <= show * 2 + 4:
        return value[:show] + '****'
    return value[:show] + '****' + value[-show:]

def mask_config(config: dict) -> dict:
    """对配置值做脱敏处理"""
    masked = {}
    for k, v in config.items():
        if isinstance(v, str) and len(v) > 10:
            masked[k] = mask_value(v)
        elif isinstance(v, dict):
            masked[k] = mask_config(v)
        else:
            masked[k] = v
    return masked
