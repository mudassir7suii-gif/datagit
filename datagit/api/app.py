from fastapi import FastAPI, HTTPException, Depends, Query, BackgroundTasks, Response, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from datetime import datetime, timezone
import collections
import threading
import time
import re

from datagit.config import settings
from datagit.storage.database import init_db, get_db
from datagit.storage.models import User, CrawlJob, Repository, AuditLog
from datagit.storage.exporters import DataExporter
from datagit.crawler.orchestrator import CrawlOrchestrator
from datagit.crawler.github_client import GitHubClient
from datagit.search.engine import SearchEngine
from datagit.api.auth import (
    hash_password, verify_password, create_access_token,
    get_current_user, require_current_user, COOKIE_NAME
)

# Initialize Database & Full-Text Search
init_db()

app = FastAPI(
    title="DataGit API Gateway",
    version=settings.app_version,
    description="Intelligent GitHub Repository Mining & Data Platform (Constitution Compliant)"
)

# CORS: Configured with explicit origins & credentials support
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Shared Crawler client & Orchestrator
client = GitHubClient()
orchestrator = CrawlOrchestrator(client=client)

# In-Memory Sliding Window Rate Limiter for Auth Routes per Principle 1
class AuthRateLimiter:
    def __init__(self, limit: int = 10, window_seconds: int = 60):
        self.limit = limit
        self.window = window_seconds
        self.requests = collections.defaultdict(list)
        self._lock = threading.Lock()

    def check(self, ip: str) -> bool:
        now = time.time()
        with self._lock:
            # Clean expired timestamps
            valid = [t for t in self.requests[ip] if now - t < self.window]
            if len(valid) >= self.limit:
                return False
            valid.append(now)
            self.requests[ip] = valid
            return True

auth_limiter = AuthRateLimiter(limit=settings.auth_rate_limit_per_minute, window_seconds=60)

# --- Pydantic Schemas ---
class UserAuthRequest(BaseModel):
    email: str
    password: str

class CrawlJobRequest(BaseModel):
    target: str
    depth: Optional[str] = "metadata"
    max_pages: Optional[int] = 3

def validate_auth_payload(req: UserAuthRequest) -> tuple[str, str]:
    email = req.email.strip().lower()
    if not email or "@" not in email or "." not in email:
        raise HTTPException(status_code=400, detail="A valid email address is required.")
    password = req.password
    if len(password.strip()) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters.")
    if len(password) > 72:
        raise HTTPException(status_code=400, detail="Password must not exceed 72 characters.")
    return email, password

# --- Authentication Routes ---
@app.post("/api/auth/signup")
@app.post("/api/signup") # Compatibility
def sign_up(req: UserAuthRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    ip = request.client.host if request.client else "127.0.0.1"
    if not auth_limiter.check(ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many authentication attempts. Please wait 60 seconds."
        )

    email, password = validate_auth_payload(req)
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        raise HTTPException(status_code=400, detail="User already exists with this email.")
    
    hashed = hash_password(password)
    user = User(email=email, hashed_password=hashed)
    try:
        db.add(user)
        db.commit()
        db.refresh(user)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database transaction error: {str(e)}")

    token = create_access_token({"sub": user.email})
    # Set httpOnly cookie for web clients per Principle 1
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        secure=not settings.debug,
        max_age=settings.jwt_expiration_minutes * 60
    )

    try:
        db.add(AuditLog(user_email=user.email, action="user_signup", ip_address=ip))
        db.commit()
    except Exception:
        db.rollback()

    return {"message": "Account created successfully!", "email": user.email, "access_token": token, "token_type": "bearer"}

@app.post("/api/auth/signin")
@app.post("/api/signin") # Compatibility
def sign_in(req: UserAuthRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    ip = request.client.host if request.client else "127.0.0.1"
    if not auth_limiter.check(ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many authentication attempts. Please wait 60 seconds."
        )

    email = req.email.strip().lower()
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(req.password, user.hashed_password):
        try:
            db.add(AuditLog(user_email=email, action="signin_failed", ip_address=ip))
            db.commit()
        except Exception:
            db.rollback()
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    
    token = create_access_token({"sub": user.email})
    # Set httpOnly cookie for web clients per Principle 1
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        secure=not settings.debug,
        max_age=settings.jwt_expiration_minutes * 60
    )

    try:
        db.add(AuditLog(user_email=user.email, action="signin_success", ip_address=ip))
        db.commit()
    except Exception:
        db.rollback()

    return {"message": "Login successful!", "email": user.email, "access_token": token, "token_type": "bearer"}

@app.post("/api/auth/signout")
def sign_out(response: Response, user: User = Depends(require_current_user)):
    response.delete_cookie(key=COOKIE_NAME)
    return {"message": "Signed out successfully."}

@app.get("/api/auth/me")
def get_me(user: User = Depends(require_current_user)):
    return {"id": user.id, "email": user.email, "created_at": user.created_at}

# --- Background Crawl Job Management (Protected per Non-Negotiable 1 & Principle 1) ---
def execute_background_job(job_id: int, max_pages: Optional[int] = 3):
    try:
        orchestrator.run_job(job_id, max_pages=max_pages or 3)
    except Exception as e:
        print(f"Background crawl job #{job_id} failed: {e}")

@app.post("/api/jobs")
def create_crawl_job(
    req: CrawlJobRequest,
    background_tasks: BackgroundTasks,
    request: Request,
    user: User = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    target = req.target.strip().strip("/")
    if not target:
        raise HTTPException(status_code=400, detail="Target name cannot be empty.")

    depth = (req.depth or "metadata").lower()
    if depth not in ("metadata", "commits", "issues", "full"):
        depth = "metadata"
    effective_pages = max(1, min(req.max_pages or 3, 50))

    target_type = "repo" if "/" in target else "org"
    job = CrawlJob(target=target, target_type=target_type, depth=depth, status="queued")
    db.add(job)
    db.commit()
    db.refresh(job)

    # Audit log
    ip = request.client.host if request.client else "127.0.0.1"
    db.add(AuditLog(user_email=user.email, action="crawl_job_created", target=target, details=f"depth={depth}, pages={effective_pages}", ip_address=ip))
    db.commit()

    background_tasks.add_task(execute_background_job, job.id, effective_pages)
    return {"job_id": job.id, "status": "queued", "target": job.target, "depth": job.depth}

@app.get("/api/jobs")
def list_crawl_jobs(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: User = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    jobs = db.query(CrawlJob).order_by(CrawlJob.id.desc()).offset(offset).limit(limit).all()
    total = db.query(CrawlJob).count()
    return {
        "total": total,
        "items": [{
            "id": j.id,
            "target": j.target,
            "target_type": j.target_type,
            "depth": j.depth,
            "status": j.status,
            "total_found": j.total_found,
            "items_crawled": j.items_crawled,
            "error_message": j.error_message,
            "created_at": j.created_at.isoformat() if j.created_at else None,
            "completed_at": j.completed_at.isoformat() if j.completed_at else None
        } for j in jobs]
    }

@app.get("/api/jobs/{job_id}")
def get_crawl_job(job_id: int, user: User = Depends(require_current_user), db: Session = Depends(get_db)):
    job = db.query(CrawlJob).filter(CrawlJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    return {
        "id": job.id,
        "target": job.target,
        "target_type": job.target_type,
        "depth": job.depth,
        "status": job.status,
        "total_found": job.total_found,
        "items_crawled": job.items_crawled,
        "error_message": job.error_message,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None
    }

@app.post("/api/jobs/{job_id}/cancel")
def cancel_crawl_job(job_id: int, user: User = Depends(require_current_user), db: Session = Depends(get_db)):
    job = db.query(CrawlJob).filter(CrawlJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    if job.status in ("completed", "failed", "cancelled"):
        raise HTTPException(status_code=400, detail=f"Job is already {job.status}.")
    
    job.status = "cancelled"
    job.completed_at = datetime.now(timezone.utc)
    db.commit()
    return {"message": f"Job #{job_id} cancelled.", "status": "cancelled"}

# Crawl Job Enqueue Endpoint (Strictly Non-Blocking per Non-Negotiable 3)
@app.post("/api/crawl")
def run_crawl_async(
    req: CrawlJobRequest,
    background_tasks: BackgroundTasks,
    request: Request,
    user: User = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """Non-blocking crawl trigger per Constitution Non-Negotiable 3."""
    return create_crawl_job(req, background_tasks, request, user, db)

# --- Observability & System Metrics (Epic 9) ---
@app.get("/api/metrics")
def get_system_metrics(user: User = Depends(require_current_user), db: Session = Depends(get_db)):
    """Exposes real-time operational telemetry per Constitution Principle 5."""
    active_jobs = db.query(CrawlJob).filter(CrawlJob.status.in_(["queued", "running"])).count()
    failed_jobs = db.query(CrawlJob).filter(CrawlJob.status == "failed").count()
    total_jobs = db.query(CrawlJob).count()
    rate_summary = client.token_manager.get_summary()
    return {
        "status": "healthy",
        "app_version": settings.app_version,
        "active_jobs": active_jobs,
        "failed_jobs": failed_jobs,
        "total_jobs": total_jobs,
        "rate_limits": rate_summary
    }

# --- Repository Search, Details & Deletion ---
@app.get("/api/repos")
def search_repositories(
    search: Optional[str] = Query(None, description="Keyword search in name/description"),
    language: Optional[str] = Query(None, description="Filter by language"),
    owner: Optional[str] = Query(None, description="Filter by owner/organization"),
    min_stars: Optional[int] = Query(0, description="Minimum stars"),
    sort_by: str = Query("stars", description="Column to sort by"),
    order: str = Query("desc", description="Sort order: asc or desc"),
    limit: int = Query(24, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    return SearchEngine.query_repositories(
        db=db,
        keyword=search,
        language=language,
        owner=owner,
        min_stars=min_stars,
        sort_by=sort_by,
        order=order,
        limit=limit,
        offset=offset
    )

@app.get("/api/repos/{repo_id}")
def get_repository_details(repo_id: int, db: Session = Depends(get_db)):
    details = SearchEngine.get_repository_details(db, repo_id)
    if not details:
        raise HTTPException(status_code=404, detail="Repository not found.")
    return details

@app.delete("/api/repos/{repo_id}")
def delete_repository(
    repo_id: int,
    request: Request,
    user: User = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """Soft-deletes repository per Constitution Principle 6 (Privacy & Compliance)."""
    repo = db.query(Repository).filter(Repository.id == repo_id).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found.")
    
    repo.is_deleted = True
    ip = request.client.host if request.client else "127.0.0.1"
    db.add(AuditLog(user_email=user.email, action="repo_deleted", target=repo.full_name, ip_address=ip))
    db.commit()
    return {"message": f"Repository '{repo.full_name}' deleted successfully."}

@app.get("/api/insights")
def get_insights(db: Session = Depends(get_db)):
    return SearchEngine.get_insights(db)

# --- Observability: Rate-Limit Tracking (Protected per Non-Negotiable 1) ---
@app.get("/api/ratelimit")
def get_rate_limit_status(user: User = Depends(require_current_user)):
    return client.token_manager.get_summary()

# --- Streaming Export Endpoint (Protected & Constitution Compliant) ---
@app.get("/api/export")
def export_data(
    format: str = Query("csv", pattern="^(csv|json|parquet)$"),
    search: Optional[str] = Query(None, description="Filter export by search term"),
    owner: Optional[str] = None,
    language: Optional[str] = None,
    min_stars: Optional[int] = None,
    request: Request = None,
    user: User = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    query = db.query(Repository).filter(Repository.is_deleted.isnot(True))
    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(
            (Repository.name.ilike(term)) | (Repository.full_name.ilike(term)) | (Repository.description.ilike(term))
        )
    if owner and owner.strip():
        query = query.filter(Repository.owner.ilike(owner.strip()))
    if language and language.strip():
        query = query.filter(Repository.language.ilike(language.strip()))
    if min_stars is not None and min_stars > 0:
        query = query.filter(Repository.stars >= min_stars)

    clean_owner = re.sub(r"[^\w\-]", "_", owner.strip()) if owner and owner.strip() else "dataset"
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"datagit_{clean_owner}_{timestamp}"

    # Audit log
    ip = request.client.host if request and request.client else "127.0.0.1"
    db.add(AuditLog(user_email=user.email, action="data_exported", target=f"{format}:{filename}", ip_address=ip))
    db.commit()

    # Streaming exports per Constitution Principle 4 (No unbounded RAM loads)
    if format == "csv":
        return StreamingResponse(
            DataExporter.stream_csv(query),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}.csv"'}
        )
    elif format == "json":
        return StreamingResponse(
            DataExporter.stream_json(query),
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{filename}.json"'}
        )
    else: # parquet
        repos = query.all()
        data = [DataExporter.repo_to_dict(r) for r in repos]
        path = DataExporter.to_parquet(data, filename)
        DataExporter.cleanup_old_exports(max_age_hours=24)
        return FileResponse(path=str(path), media_type="application/octet-stream", filename=path.name)
