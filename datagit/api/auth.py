from datetime import datetime, timedelta, timezone
from typing import Optional
import bcrypt
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from datagit.config import settings
from datagit.storage.database import get_db
from datagit.storage.models import User

COOKIE_NAME = "datagit_access_token"
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/signin", auto_error=False)

def hash_password(password: str) -> str:
    pwd_bytes = password.encode("utf-8")[:72]
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        pwd_bytes = plain_password.encode("utf-8")[:72]
        hash_bytes = hashed_password.encode("utf-8")
        return bcrypt.checkpw(pwd_bytes, hash_bytes)
    except Exception:
        return False

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=settings.jwt_expiration_minutes))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.jwt_secret, algorithm=settings.jwt_algorithm)

import secrets
import hashlib
from datagit.storage.models import User, ApiKey

def hash_api_key(plain_key: str) -> str:
    return hashlib.sha256(plain_key.strip().encode("utf-8")).hexdigest()

def generate_api_key() -> tuple[str, str, str]:
    """Generates (full_key, key_prefix, key_hash) per Epic P2.2."""
    random_part = secrets.token_urlsafe(28)
    full_key = f"dg_live_{random_part}"
    prefix = full_key[:12]
    key_hash = hash_api_key(full_key)
    return full_key, prefix, key_hash

def get_current_user(
    request: Request,
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> Optional[User]:
    # 1. Check API Key header (X-API-Key or Bearer dg_...) per Epic P2.2
    api_key_header = request.headers.get("X-API-Key")
    candidate_key = api_key_header or (token if token and token.startswith("dg_") else None)
    if candidate_key:
        key_hash = hash_api_key(candidate_key)
        api_key_record = db.query(ApiKey).filter(
            ApiKey.key_hash == key_hash,
            ApiKey.is_revoked.isnot(True)
        ).first()
        if api_key_record:
            api_key_record.last_used_at = datetime.now(timezone.utc)
            try:
                db.commit()
            except Exception:
                db.rollback()
            return api_key_record.user

    # 2. Check Bearer authorization header or httpOnly cookie
    auth_token = token or request.cookies.get(COOKIE_NAME)
    if not auth_token:
        return None
    try:
        payload = jwt.decode(auth_token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        email: str = payload.get("sub")
        if email is None:
            return None
    except JWTError:
        return None
    return db.query(User).filter(User.email == email).first()

def require_current_user(user: Optional[User] = Depends(get_current_user)) -> User:
    """Enforces authentication dependency per Constitution Principle 1."""
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please sign in or provide a valid Bearer token.",
            headers={"WWW-Authenticate": "Bearer"}
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive account."
        )
    return user
