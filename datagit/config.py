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
    
    # Security
    jwt_secret: str = os.getenv("DATAGIT_JWT_SECRET", "datagit-super-secret-key-change-in-prod-38294719")
    jwt_algorithm: str = "HS256"
    jwt_expiration_minutes: int = 60 * 24 # 24 hours

settings = Settings()
settings.export_dir.mkdir(parents=True, exist_ok=True)
