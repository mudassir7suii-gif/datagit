import time
import os
import json
import threading
import requests
from datetime import datetime, timezone
from typing import List, Dict, Optional, Any

from datagit.storage.models import RateLimitState
from datagit.storage.database import SessionLocal
from datagit.core.encryption import encrypt_token, decrypt_token, mask_token

class TokenStatus:
    """Encapsulates a GitHub API token status with at-rest encryption and safe masking."""
    
    def __init__(self, token: Optional[str]):
        if token and token.strip():
            plain = token.strip()
            self._encrypted_token: Optional[str] = encrypt_token(plain)
            self._plain_cache: Optional[str] = plain
        else:
            self._encrypted_token = None
            self._plain_cache = None

        self.limit: int = 5000 if token else 60
        self.remaining: int = 5000 if token else 60
        self.reset_timestamp: float = time.time() + 3600
        self.last_used: float = 0.0

    @property
    def token(self) -> Optional[str]:
        """Returns the decrypted token for authenticated outbound requests."""
        if not self._encrypted_token:
            return None
        if self._plain_cache is None:
            self._plain_cache = decrypt_token(self._encrypted_token)
        return self._plain_cache

    @property
    def encrypted_token(self) -> Optional[str]:
        return self._encrypted_token

    @property
    def token_masked(self) -> str:
        return mask_token(self.token)

    @property
    def is_exhausted(self) -> bool:
        now = time.time()
        if now > self.reset_timestamp:
            self.remaining = self.limit
            self.reset_timestamp = now + 3600
            return False
        return self.remaining <= 1

    @property
    def seconds_until_reset(self) -> int:
        return max(0, int(self.reset_timestamp - time.time()))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "token_masked": self.token_masked,
            "limit": self.limit,
            "remaining": self.remaining,
            "seconds_until_reset": self.seconds_until_reset,
            "is_exhausted": self.is_exhausted
        }


class RateLimitStore:
    """Abstract interface for shared rate-limit state."""
    def get_state(self, token_masked: str) -> Optional[Dict[str, Any]]:
        raise NotImplementedError

    def set_state(self, token_masked: str, limit: int, remaining: int, reset_timestamp: float) -> None:
        raise NotImplementedError


class RedisRateLimitStore(RateLimitStore):
    """Distributed Redis-backed rate-limit store per Technical Plan P0.6."""

    def __init__(self, redis_url: str):
        import redis
        self.client = redis.Redis.from_url(redis_url, decode_responses=True)

    def get_state(self, token_masked: str) -> Optional[Dict[str, Any]]:
        try:
            val = self.client.get(f"datagit:ratelimit:{token_masked}")
            if val:
                return json.loads(val)
        except Exception:
            pass
        return None

    def set_state(self, token_masked: str, limit: int, remaining: int, reset_timestamp: float) -> None:
        try:
            data = {"limit": limit, "remaining": remaining, "reset_timestamp": reset_timestamp}
            ttl = max(60, int(reset_timestamp - time.time()) + 120)
            self.client.setex(f"datagit:ratelimit:{token_masked}", ttl, json.dumps(data))
        except Exception:
            pass


class DatabaseRateLimitStore(RateLimitStore):
    """SQL-backed persistent rate-limit store for local development and fallback."""

    def get_state(self, token_masked: str) -> Optional[Dict[str, Any]]:
        try:
            db = SessionLocal()
            state = db.query(RateLimitState).filter(RateLimitState.token_masked == token_masked).first()
            if state:
                result = {
                    "limit": state.limit,
                    "remaining": state.remaining,
                    "reset_timestamp": state.reset_timestamp
                }
                db.close()
                return result
            db.close()
        except Exception:
            pass
        return None

    def set_state(self, token_masked: str, limit: int, remaining: int, reset_timestamp: float) -> None:
        try:
            db = SessionLocal()
            state = db.query(RateLimitState).filter(RateLimitState.token_masked == token_masked).first()
            if not state:
                state = RateLimitState(
                    token_masked=token_masked,
                    limit=limit,
                    remaining=remaining,
                    reset_timestamp=reset_timestamp
                )
                db.add(state)
            else:
                state.limit = limit
                state.remaining = remaining
                state.reset_timestamp = reset_timestamp
                state.last_used = datetime.now(timezone.utc)
            db.commit()
            db.close()
        except Exception:
            pass


class TokenManager:
    """Manages GitHub API tokens with shared Redis/DB state across workers per Constitution & Plan."""
    
    def __init__(self, initial_tokens: Optional[List[str]] = None, sync_live: bool = True):
        self._lock = threading.Lock()
        self.tokens: List[TokenStatus] = []
        
        # Initialize Rate Limit Store (Redis if available, else DB)
        redis_url = os.getenv("DATAGIT_REDIS_URL") or os.getenv("REDIS_URL")
        self.store: RateLimitStore = None
        if redis_url:
            try:
                self.store = RedisRateLimitStore(redis_url)
            except Exception:
                self.store = DatabaseRateLimitStore()
        else:
            self.store = DatabaseRateLimitStore()

        if initial_tokens:
            for t in initial_tokens:
                self.add_token(t)
        if not self.tokens:
            self.tokens.append(TokenStatus(None))

        # Restore from store and sync with GitHub live rate_limit API
        self.load_from_db()
        if sync_live:
            self.sync_with_github_api()

    def add_token(self, token: Optional[str]) -> None:
        if not token or not token.strip():
            return
        token = token.strip()
        with self._lock:
            if any(t.token == token for t in self.tokens):
                return
            self.tokens = [t for t in self.tokens if t.token is not None]
            self.tokens.append(TokenStatus(token))

    def load_from_db(self) -> None:
        """Hydrates token quotas from store (Redis or DB) to coordinate across workers."""
        try:
            now = time.time()
            for t in self.tokens:
                state = self.store.get_state(t.token_masked)
                if state:
                    reset_ts = state.get("reset_timestamp", 0)
                    if reset_ts > now:
                        t.remaining = state.get("remaining", t.remaining)
                        t.limit = state.get("limit", t.limit)
                        t.reset_timestamp = reset_ts
        except Exception:
            pass

    def persist_to_db(self, token_status: TokenStatus) -> None:
        """Persists updated rate limit state to the shared store."""
        try:
            self.store.set_state(
                token_masked=token_status.token_masked,
                limit=token_status.limit,
                remaining=token_status.remaining,
                reset_timestamp=token_status.reset_timestamp
            )
        except Exception:
            pass

    def sync_with_github_api(self) -> None:
        """Queries official GitHub /rate_limit endpoint to discover true budget."""
        for t in self.tokens:
            headers = {"Accept": "application/vnd.github+json", "User-Agent": "DataGit-Crawler"}
            if t.token:
                headers["Authorization"] = f"Bearer {t.token}"
            try:
                r = requests.get("https://api.github.com/rate_limit", headers=headers, timeout=5)
                if r.status_code == 200:
                    data = r.json()
                    core = (data.get("resources") or {}).get("core") or {}
                    t.limit = core.get("limit", t.limit)
                    t.remaining = core.get("remaining", t.remaining)
                    t.reset_timestamp = float(core.get("reset", t.reset_timestamp))
                    self.persist_to_db(t)
            except Exception:
                pass

    def acquire_token(self) -> TokenStatus:
        """Selects the token with the highest remaining budget, refreshing state from shared store."""
        with self._lock:
            self.load_from_db()
            now = time.time()
            for t in self.tokens:
                if now > t.reset_timestamp:
                    t.remaining = t.limit
                    t.reset_timestamp = now + 3600

            available = [t for t in self.tokens if not t.is_exhausted]
            if not available:
                soonest = min(self.tokens, key=lambda t: t.seconds_until_reset)
                wait_sec = soonest.seconds_until_reset
                raise RuntimeError(
                    f"GitHub Rate Limit Reached across all tokens. Please wait {wait_sec}s for limit reset, or provide additional GitHub PATs."
                )

            chosen = max(available, key=lambda t: t.remaining)
            chosen.last_used = time.time()
            return chosen

    def update_limits(self, token_str: Optional[str], headers: Dict[str, str]) -> None:
        """Parses X-RateLimit headers returned by GitHub API and persists to shared store."""
        with self._lock:
            target = next((t for t in self.tokens if t.token == token_str), None)
            if not target:
                return

            lower_headers = {k.lower(): v for k, v in headers.items()}
            limit_hdr = lower_headers.get("x-ratelimit-limit")
            rem_hdr = lower_headers.get("x-ratelimit-remaining")
            reset_hdr = lower_headers.get("x-ratelimit-reset")

            if limit_hdr:
                try:
                    target.limit = int(limit_hdr)
                except (ValueError, TypeError):
                    pass
            if rem_hdr:
                try:
                    target.remaining = int(rem_hdr)
                except (ValueError, TypeError):
                    pass
            if reset_hdr:
                try:
                    target.reset_timestamp = float(reset_hdr)
                except (ValueError, TypeError):
                    pass

            self.persist_to_db(target)

    def get_summary(self) -> Dict[str, Any]:
        with self._lock:
            self.load_from_db()
            total_remaining = sum(t.remaining for t in self.tokens)
            total_limit = sum(t.limit for t in self.tokens)
            return {
                "active_tokens_count": len(self.tokens),
                "total_remaining_requests": total_remaining,
                "total_limit": total_limit,
                "pools": [t.to_dict() for t in self.tokens]
            }
