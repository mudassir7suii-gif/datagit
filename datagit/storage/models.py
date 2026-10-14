from datetime import datetime, timezone
import hashlib
from typing import Optional
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, BigInteger, UniqueConstraint, Float
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

def now_utc():
    return datetime.now(timezone.utc)

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=now_utc)
    is_active = Column(Boolean, default=True)
    failed_login_attempts = Column(Integer, default=0)
    locked_until = Column(DateTime, nullable=True)
    plan = Column(String(50), default="free")

    owned_workspaces = relationship("Workspace", back_populates="owner", cascade="all, delete-orphan", foreign_keys="Workspace.owner_id")

class Workspace(Base):
    __tablename__ = "workspaces"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    slug = Column(String(100), unique=True, index=True, nullable=False)
    owner_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    created_at = Column(DateTime, default=now_utc)

    owner = relationship("User", foreign_keys=[owner_id], back_populates="owned_workspaces")
    members = relationship("WorkspaceMember", back_populates="workspace", cascade="all, delete-orphan")

class WorkspaceMember(Base):
    __tablename__ = "workspace_members"
    __table_args__ = (
        UniqueConstraint("workspace_id", "user_id", name="uq_workspace_member"),
    )

    id = Column(Integer, primary_key=True, index=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    role = Column(String(50), default="member") # owner, admin, member
    created_at = Column(DateTime, default=now_utc)

    workspace = relationship("Workspace", back_populates="members")
    user = relationship("User", backref="workspace_memberships")

class ApiKey(Base):
    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="SET NULL"), index=True, nullable=True)
    name = Column(String(100), nullable=False)
    key_prefix = Column(String(16), index=True, nullable=False)
    key_hash = Column(String(64), unique=True, index=True, nullable=False)
    created_at = Column(DateTime, default=now_utc)
    last_used_at = Column(DateTime, nullable=True)
    is_revoked = Column(Boolean, default=False, index=True)

    user = relationship("User", backref="api_keys")

class CrawlJob(Base):
    __tablename__ = "crawl_jobs"

    id = Column(Integer, primary_key=True, index=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="SET NULL"), index=True, nullable=True)
    target = Column(String(255), index=True, nullable=False)
    target_type = Column(String(50), default="org") # org, user, repo
    depth = Column(String(50), default="metadata") # metadata, commits, issues, full
    status = Column(String(50), default="queued", index=True) # queued, running, completed, failed, cancelled
    total_found = Column(Integer, default=0)
    items_crawled = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=now_utc)
    completed_at = Column(DateTime, nullable=True)

class Repository(Base):
    __tablename__ = "repositories"

    id = Column(Integer, primary_key=True, index=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="SET NULL"), index=True, nullable=True)
    github_id = Column(BigInteger, unique=True, index=True, nullable=True)
    owner = Column(String(100), index=True, nullable=False)
    name = Column(String(150), index=True, nullable=False)
    full_name = Column(String(255), unique=True, index=True, nullable=False)
    description = Column(Text, nullable=True)
    url = Column(String(255), nullable=False)
    language = Column(String(100), index=True, nullable=True)
    stars = Column(Integer, default=0, index=True)
    forks = Column(Integer, default=0)
    open_issues = Column(Integer, default=0)
    default_branch = Column(String(100), default="main")
    is_fork = Column(Boolean, default=False)
    is_private = Column(Boolean, default=False)
    is_archived = Column(Boolean, default=False)
    is_deleted = Column(Boolean, default=False, index=True)
    
    # Timestamps & Data Freshness
    repo_created_at = Column(DateTime, nullable=True)
    repo_updated_at = Column(DateTime, nullable=True)
    repo_pushed_at = Column(DateTime, nullable=True)
    crawled_at = Column(DateTime, default=now_utc, index=True)
    
    # Data deduplication & integrity hashing
    content_hash = Column(String(64), nullable=True)

    # Relationships
    commits = relationship("Commit", back_populates="repository", cascade="all, delete-orphan")
    issues = relationship("Issue", back_populates="repository", cascade="all, delete-orphan")

    def generate_hash(self) -> str:
        raw = f"{self.full_name}:{self.stars}:{self.forks}:{self.repo_pushed_at}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

class Commit(Base):
    __tablename__ = "commits"
    __table_args__ = (
        UniqueConstraint("repo_id", "sha", name="uq_commit_repo_sha"),
    )

    id = Column(Integer, primary_key=True, index=True)
    repo_id = Column(Integer, ForeignKey("repositories.id", ondelete="CASCADE"), index=True, nullable=False)
    sha = Column(String(40), index=True, nullable=False)
    author_name = Column(String(150), nullable=True)
    author_email = Column(String(150), nullable=True)
    message = Column(Text, nullable=True)
    committed_at = Column(DateTime, nullable=True)
    url = Column(String(255), nullable=True)

    repository = relationship("Repository", back_populates="commits")

class Issue(Base):
    __tablename__ = "issues"
    __table_args__ = (
        UniqueConstraint("repo_id", "github_number", name="uq_issue_repo_number"),
    )

    id = Column(Integer, primary_key=True, index=True)
    repo_id = Column(Integer, ForeignKey("repositories.id", ondelete="CASCADE"), index=True, nullable=False)
    github_number = Column(Integer, nullable=False)
    title = Column(Text, nullable=False)
    state = Column(String(50), default="open") # open, closed
    author = Column(String(100), nullable=True)
    comments_count = Column(Integer, default=0)
    is_pull_request = Column(Boolean, default=False)
    created_at = Column(DateTime, nullable=True)
    closed_at = Column(DateTime, nullable=True)
    url = Column(String(255), nullable=True)

    repository = relationship("Repository", back_populates="issues")

class RateLimitState(Base):
    __tablename__ = "rate_limit_states"

    id = Column(Integer, primary_key=True)
    token_masked = Column(String(50), unique=True, index=True, nullable=False)
    limit = Column(Integer, default=5000)
    remaining = Column(Integer, default=5000)
    reset_timestamp = Column(Float, nullable=False)
    last_used = Column(DateTime, default=now_utc)
    updated_at = Column(DateTime, default=now_utc)

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_email = Column(String(255), nullable=True, index=True)
    action = Column(String(100), nullable=False, index=True) # crawl_started, export_generated, repo_deleted, login_failed
    target = Column(String(255), nullable=True)
    details = Column(Text, nullable=True)
    ip_address = Column(String(45), nullable=True)
    created_at = Column(DateTime, default=now_utc, index=True)

class Webhook(Base):
    __tablename__ = "webhooks"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="SET NULL"), index=True, nullable=True)
    url = Column(String(500), nullable=False)
    secret = Column(String(100), nullable=False)
    events = Column(String(255), default="job.completed,job.failed")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=now_utc)
    last_triggered_at = Column(DateTime, nullable=True)
    failure_count = Column(Integer, default=0)

    user = relationship("User", backref="webhooks")

class ExportArtifact(Base):
    __tablename__ = "export_artifacts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="SET NULL"), index=True, nullable=True)
    filename = Column(String(255), nullable=False)
    storage_path = Column(String(500), nullable=False)
    storage_backend = Column(String(50), default="local") # local, s3
    format = Column(String(20), nullable=False) # csv, json, parquet
    file_size = Column(BigInteger, default=0)
    checksum_sha256 = Column(String(64), nullable=True)
    download_token = Column(String(64), unique=True, index=True, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=now_utc)

    user = relationship("User", backref="export_artifacts")


class SavedSearch(Base):
    __tablename__ = "saved_searches"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="SET NULL"), index=True, nullable=True)
    name = Column(String(100), nullable=False)
    query_params = Column(Text, nullable=False)  # JSON-encoded filters: keyword, language, min_stars, etc.
    notify_on_new = Column(Boolean, default=False)
    last_checked_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=now_utc)

    user = relationship("User", backref="saved_searches")

