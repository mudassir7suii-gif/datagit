import os
from pathlib import Path
from typing import List
from pydantic import BaseModel, Field

BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseModel):
    # App
    app_name: str = "DataGit"
    app_version: str = "0.2.0"
    debug: bool = os.getenv("DATAGIT_DEBUG", "false").lower() == "true"
    
    # Storage
    database_url: str = os.getenv("DATAGIT_DATABASE_URL", f"sqlite:///{BASE_DIR / 'datagit.db'}")
    export_dir: Path = BASE_DIR / "exports"
    
    # GitHub Integration
    github_tokens: List[str] = Field(default_factory=lambda: [
        t.strip() for t in os.getenv("DATAGIT_GITHUB_TOKENS", "").split(",") if t.strip()
    ] or ([os.getenv("GITHUB_TOKEN")] if os.getenv("GITHUB_TOKEN") else []))
    github_api_base: str = "https://api.github.com"
    request_timeout: int = 20
    
    # Security & CORS
    jwt_secret: str = Field(default_factory=lambda: os.getenv("DATAGIT_JWT_SECRET") or "")
    jwt_algorithm: str = "HS256"
    jwt_expiration_minutes: int = 60 * 24 # 24 hours
    allowed_origins: List[str] = Field(default_factory=lambda: [
        origin.strip() for origin in os.getenv("DATAGIT_CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",") if origin.strip()
    ])
    auth_rate_limit_per_minute: int = int(os.getenv("DATAGIT_AUTH_RATE_LIMIT", "10"))

    def validate_production_security(self) -> None:
        """Fail-closed check per DataGit Constitution Principle 1."""
        if not self.jwt_secret:
            if not self.debug:
                raise RuntimeError(
                    "CRITICAL SECURITY CONFIGURATION ERROR: 'DATAGIT_JWT_SECRET' environment variable is required "
                    "when running in production mode (DATAGIT_DEBUG=false). Set DATAGIT_JWT_SECRET before starting DataGit."
                )
            # Dev mode fallback
            import warnings
            warnings.warn(
                "Running in DEBUG mode with automatic dev JWT secret. DO NOT deploy to production without setting DATAGIT_JWT_SECRET!",
                stacklevel=2
            )
            self.jwt_secret = "datagit-insecure-dev-key-change-in-prod-772911"

settings = Settings()
settings.validate_production_security()
settings.export_dir.mkdir(parents=True, exist_ok=True)
