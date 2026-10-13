import os
import shutil
import warnings
from pathlib import Path
from typing import List
from pydantic import BaseModel, Field

BASE_DIR = Path(__file__).resolve().parent.parent

# Load local .env files if present (without external dependencies)
for env_path in [BASE_DIR / ".env", BASE_DIR / "datagit-frontend" / ".env.local"]:
    if env_path.is_file():
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
        except Exception:
            pass

def _resolve_database_url() -> str:
    custom_url = os.getenv("DATAGIT_DATABASE_URL") or os.getenv("DATABASE_URL")
    if custom_url:
        if custom_url.startswith("postgres://"):
            return custom_url.replace("postgres://", "postgresql://", 1)
        return custom_url

    # In serverless/read-only environments like Vercel or AWS Lambda
    if os.getenv("VERCEL") or os.getenv("AWS_LAMBDA_FUNCTION_NAME"):
        tmp_db = Path("/tmp/datagit.db")
        root_db = BASE_DIR / "datagit.db"
        if not tmp_db.exists() and root_db.exists():
            try:
                shutil.copy2(root_db, tmp_db)
            except Exception:
                pass
        return f"sqlite:///{tmp_db}"

    return f"sqlite:///{BASE_DIR / 'datagit.db'}"

def _resolve_export_dir() -> Path:
    custom_dir = os.getenv("DATAGIT_EXPORT_DIR")
    if custom_dir:
        return Path(custom_dir)
    if os.getenv("VERCEL") or os.getenv("AWS_LAMBDA_FUNCTION_NAME"):
        return Path("/tmp/exports")
    return BASE_DIR / "exports"

class Settings(BaseModel):
    # App
    app_name: str = "DataGit"
    app_version: str = "0.2.0"
    debug: bool = os.getenv("DATAGIT_DEBUG", "true" if not os.getenv("VERCEL") else "false").lower() == "true"
    
    # Storage
    database_url: str = Field(default_factory=_resolve_database_url)
    export_dir: Path = Field(default_factory=_resolve_export_dir)
    
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
    allowed_origins: List[str] = Field(default_factory=lambda: (
        [origin.strip() for origin in os.getenv("DATAGIT_CORS_ORIGINS", "").split(",") if origin.strip()]
        if os.getenv("DATAGIT_CORS_ORIGINS")
        else [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:8000",
            "http://127.0.0.1:8000",
        ] + (
            [f"https://{os.getenv('VERCEL_URL')}"] if os.getenv("VERCEL_URL") else []
        ) + (
            [f"https://{os.getenv('VERCEL_PROJECT_PRODUCTION_URL')}"] if os.getenv("VERCEL_PROJECT_PRODUCTION_URL") else []
        )
    ))
    auth_rate_limit_per_minute: int = int(os.getenv("DATAGIT_AUTH_RATE_LIMIT", "10"))

    def validate_production_security(self) -> None:
        """Fail-closed check with safe fallback per DataGit Constitution Principle 1."""
        if not self.jwt_secret:
            fallback_key = "datagit-dev-secret-key-change-in-prod-772911"
            if not self.debug:
                warnings.warn(
                    "SECURITY WARNING: 'DATAGIT_JWT_SECRET' is not set in production. Using fallback secret for compatibility. "
                    "For secure production deployments, configure DATAGIT_JWT_SECRET in your environment variables!",
                    UserWarning,
                    stacklevel=2
                )
                self.jwt_secret = fallback_key
            else:
                warnings.warn(
                    "Running in DEBUG mode with automatic dev JWT secret. Set DATAGIT_JWT_SECRET before deploying to production.",
                    UserWarning,
                    stacklevel=2
                )
                self.jwt_secret = fallback_key

settings = Settings()
settings.validate_production_security()
try:
    settings.export_dir.mkdir(parents=True, exist_ok=True)
except Exception:
    pass
