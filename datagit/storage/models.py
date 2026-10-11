from datetime import datetime, timezone
import hashlib
from typing import Optional
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, BigInteger
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

class CrawlJob(Base):
    __tablename__ = "crawl_jobs"

    id = Column(Integer, primary_key=True, index=True)
    target = Column(String(255), index=True, nullable=False)
    target_type = Column(String(50), default="org") # org, user, repo
    depth = Column(String(50), default="metadata") # metadata, commits, issues, full
    status = Column(String(50), default="queued") # queued, running, completed, failed
    total_found = Column(Integer, default=0)
    items_crawled = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=now_utc)
    completed_at = Column(DateTime, nullable=True)

class Repository(Base):
    __tablename__ = "repositories"

    id = Column(Integer, primary_key=True, index=True)
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
