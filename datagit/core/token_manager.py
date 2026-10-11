import time
import threading
from typing import List, Dict, Optional, Any

class TokenStatus:
    def __init__(self, token: Optional[str]):
        self.token = token
        self.limit: int = 5000 if token else 60
        self.remaining: int = 5000 if token else 60
        self.reset_timestamp: float = time.time() + 3600
        self.last_used: float = 0.0

    @property
    def is_exhausted(self) -> bool:
        now = time.time()
        if now > self.reset_timestamp:
            # Rate limit period has passed, reset assumed
            self.remaining = self.limit
            self.reset_timestamp = now + 3600
            return False
        return self.remaining <= 1

    @property
    def seconds_until_reset(self) -> int:
        return max(0, int(self.reset_timestamp - time.time()))

    def to_dict(self) -> Dict[str, Any]:
        masked = f"{self.token[:4]}...{self.token[-4:]}" if self.token and len(self.token) > 8 else ("Unauthenticated" if not self.token else "***")
        return {
            "token_masked": masked,
            "limit": self.limit,
            "remaining": self.remaining,
            "seconds_until_reset": self.seconds_until_reset,
            "is_exhausted": self.is_exhausted
        }

class TokenManager:
    """Manages GitHub API tokens and their rate-limit budgets per Constitution Principle 1."""
    
    def __init__(self, initial_tokens: Optional[List[str]] = None):
        self._lock = threading.Lock()
        self.tokens: List[TokenStatus] = []
        if initial_tokens:
            for t in initial_tokens:
                self.add_token(t)
        if not self.tokens:
            # Fallback to unauthenticated pool
            self.tokens.append(TokenStatus(None))

    def add_token(self, token: Optional[str]) -> None:
        if not token or not token.strip():
            return
        token = token.strip()
        with self._lock:
            # Avoid duplicate tokens
            if any(t.token == token for t in self.tokens):
                return
            # Remove dummy unauthenticated token if adding real token
            self.tokens = [t for t in self.tokens if t.token is not None]
            self.tokens.append(TokenStatus(token))

    def acquire_token(self) -> TokenStatus:
        """Selects the token with the highest remaining budget."""
        with self._lock:
            # Refresh expired statuses
            now = time.time()
            for t in self.tokens:
                if now > t.reset_timestamp:
                    t.remaining = t.limit
                    t.reset_timestamp = now + 3600

            available = [t for t in self.tokens if not t.is_exhausted]
            if not available:
                # All tokens exhausted - pick the one resetting soonest
                soonest = min(self.tokens, key=lambda t: t.seconds_until_reset)
                wait_sec = soonest.seconds_until_reset
                raise RuntimeError(
                    f"GitHub Rate Limit Reached across all tokens. Please wait {wait_sec}s for limit reset, or provide additional GitHub PATs."
                )

            # Sort by remaining calls descending
            chosen = max(available, key=lambda t: t.remaining)
            chosen.last_used = time.time()
            return chosen

    def update_limits(self, token_str: Optional[str], headers: Dict[str, str]) -> None:
        """Parses X-RateLimit headers returned by GitHub API."""
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

    def get_summary(self) -> Dict[str, Any]:
        with self._lock:
            total_remaining = sum(t.remaining for t in self.tokens)
            total_limit = sum(t.limit for t in self.tokens)
            return {
                "active_tokens_count": len(self.tokens),
                "total_remaining_requests": total_remaining,
                "total_limit": total_limit,
                "pools": [t.to_dict() for t in self.tokens]
            }
