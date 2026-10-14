import base64
import hashlib
import os
from typing import Optional
from cryptography.fernet import Fernet
from datagit.config import settings

def _get_fernet_key() -> bytes:
    """Derives a deterministic 32-byte urlsafe base64 key for Fernet encryption."""
    custom_key = os.getenv("DATAGIT_ENCRYPTION_KEY")
    raw_secret = custom_key or settings.jwt_secret or "datagit-default-encryption-salt-2026"
    # Derive 32-byte key using SHA-256
    digest = hashlib.sha256(raw_secret.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)

def encrypt_token(plain_token: Optional[str]) -> Optional[str]:
    """Encrypts a GitHub token at rest per Constitution Principle 1 & Technical Plan P0.10."""
    if not plain_token or not plain_token.strip():
        return plain_token
    token_str = plain_token.strip()
    if token_str.startswith("enc:v1:"):
        return token_str # Already encrypted

    key = _get_fernet_key()
    f = Fernet(key)
    ciphertext = f.encrypt(token_str.encode("utf-8")).decode("utf-8")
    return f"enc:v1:{ciphertext}"

def decrypt_token(encrypted_token: Optional[str]) -> Optional[str]:
    """Decrypts a stored GitHub token for internal API use."""
    if not encrypted_token or not encrypted_token.strip():
        return encrypted_token
    token_str = encrypted_token.strip()
    if not token_str.startswith("enc:v1:"):
        # Backwards compatible with legacy plaintext
        return token_str

    raw_cipher = token_str[len("enc:v1:"):]
    key = _get_fernet_key()
    f = Fernet(key)
    try:
        decrypted = f.decrypt(raw_cipher.encode("utf-8")).decode("utf-8")
        return decrypted
    except Exception:
        # In case of decryption failure, return original
        return token_str

def mask_token(token: Optional[str]) -> str:
    """Safely masks a token for audit logs and API responses so secrets are never leaked."""
    if not token:
        return "Unauthenticated"
    # Decrypt first if encrypted
    plain = decrypt_token(token) if token.startswith("enc:v1:") else token
    thash = hashlib.sha256(plain.encode()).hexdigest()[:8]
    if len(plain) > 8:
        return f"{plain[:4]}..{thash}..{plain[-4:]}"
    return f"token_{thash}"
