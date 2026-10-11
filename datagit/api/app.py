from fastapi import FastAPI, HTTPException, Depends, Query, BackgroundTasks, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, EmailStr
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from datagit.config import settings
from datagit.storage.database import init_db, get_db
from datagit.storage.models import User, CrawlJob, Repository
from datagit.storage.exporters import DataExporter
from datagit.crawler.orchestrator import CrawlOrchestrator
from datagit.crawler.github_client import GitHubClient
from datagit.search.engine import SearchEngine
from datagit.api.auth import hash_password, verify_password, create_access_token, get_current_user

# Initialize Database
init_db()

app = FastAPI(
    title="DataGit API Gateway",
    version=settings.app_version,
    description="Intelligent GitHub Repository Mining & Data Platform"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Shared Crawler client
client = GitHubClient()
orchestrator = CrawlOrchestrator(client=client)

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
    if len(password.strip()) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters.")
    return email, password

# --- Authentication Routes ---
@app.post("/api/auth/signup")
@app.post("/api/signup") # Compatibility
def sign_up(req: UserAuthRequest, db: Session = Depends(get_db)):
    email, password = validate_auth_payload(req)
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        raise HTTPException(status_code=400, detail="User already exists with this email.")
    
    hashed = hash_password(password)
    user = User(email=email, hashed_password=hashed)
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token({"sub": user.email})
    return {"message": "Account created successfully!", "email": user.email, "access_token": token, "token_type": "bearer"}

@app.post("/api/auth/signin")
@app.post("/api/signin") # Compatibility
def sign_in(req: UserAuthRequest, db: Session = Depends(get_db)):
    email = req.email.strip().lower()
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(req.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    
    token = create_access_token({"sub": user.email})
    return {"message": "Login successful!", "email": user.email, "access_token": token, "token_type": "bearer"}

@app.get("/api/auth/me")
def get_me(user: Optional[User] = Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated.")
    return {"id": user.id, "email": user.email, "created_at": user.created_at}

# --- Crawl Job Routes ---
def execute_background_job(job_id: int, max_pages: Optional[int] = 3):
    try:
        orchestrator.run_job(job_id, max_pages=max_pages or 3)
    except Exception as e:
        print(f"Background crawl job {job_id} failed: {e}")

@app.post("/api/jobs")
def create_crawl_job(req: CrawlJobRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    target = req.target.strip().strip("/")
    if not target:
        raise HTTPException(status_code=400, detail="Target name cannot be empty.")

    depth = (req.depth or "metadata").lower()
    if depth not in ("metadata", "commits", "issues", "full"):
        depth = "metadata"
    effective_pages = max(1, min(req.max_pages or 3, 50))

    job = CrawlJob(target=target, depth=depth, status="queued")
    db.add(job)
    db.commit()
    db.refresh(job)

    background_tasks.add_task(execute_background_job, job.id, effective_pages)
    return {"job_id": job.id, "status": "queued", "target": job.target, "depth": job.depth}

@app.get("/api/jobs")
def list_crawl_jobs(limit: int = 10, db: Session = Depends(get_db)):
    jobs = db.query(CrawlJob).order_by(CrawlJob.id.desc()).limit(limit).all()
    return [{
        "id": j.id,
        "target": j.target,
        "depth": j.depth,
        "status": j.status,
        "total_found": j.total_found,
        "items_crawled": j.items_crawled,
        "error_message": j.error_message,
        "created_at": j.created_at,
        "completed_at": j.completed_at
    } for j in jobs]

@app.get("/api/jobs/{job_id}")
def get_crawl_job(job_id: int, db: Session = Depends(get_db)):
    job = db.query(CrawlJob).filter(CrawlJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    return {
        "id": job.id,
        "target": job.target,
        "depth": job.depth,
        "status": job.status,
        "total_found": job.total_found,
        "items_crawled": job.items_crawled,
        "error_message": job.error_message,
        "created_at": job.created_at,
        "completed_at": job.completed_at
    }

# Sync Crawl Compatibility Endpoint for Frontend
@app.post("/api/crawl")
def run_crawl_sync(req: CrawlJobRequest, db: Session = Depends(get_db)):
    target = req.target.strip().strip("/")
    if not target:
        raise HTTPException(status_code=400, detail="Target name cannot be empty.")
    
    depth = (req.depth or "metadata").lower()
    if depth not in ("metadata", "commits", "issues", "full"):
        depth = "metadata"
    effective_pages = max(1, min(req.max_pages or 3, 50))

    job = CrawlJob(target=target, depth=depth, status="queued")
    db.add(job)
    db.commit()
    db.refresh(job)

    try:
        completed = orchestrator.run_job(job.id, max_pages=effective_pages)
        repos = (
            db.query(Repository)
            .filter(Repository.owner.ilike(target))
            .order_by(Repository.stars.desc())
            .limit(50)
            .all()
        )
        summary = [{
            "name": r.name,
            "language": r.language,
            "stars": r.stars,
            "forks": r.forks,
            "url": r.url
        } for r in repos]
        return {
            "target": target,
            "total_found": completed.total_found,
            "repositories": summary
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# --- Repository Search & Insights ---
@app.get("/api/repos")
def search_repositories(
    search: Optional[str] = Query(None, description="Keyword search in name/description"),
    language: Optional[str] = Query(None, description="Filter by language"),
    owner: Optional[str] = Query(None, description="Filter by owner/organization"),
    min_stars: Optional[int] = Query(0, description="Minimum stars"),
    sort_by: str = Query("stars", description="Column to sort by"),
    order: str = Query("desc", description="Sort order: asc or desc"),
    limit: int = Query(50, ge=1, le=200),
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

@app.get("/api/insights")
def get_insights(db: Session = Depends(get_db)):
    return SearchEngine.get_insights(db)

# --- Observability: Rate-Limit Tracking ---
@app.get("/api/ratelimit")
def get_rate_limit_status():
    return client.token_manager.get_summary()

# --- Export Endpoint ---
@app.get("/api/export")
def export_data(
    format: str = Query("csv", pattern="^(csv|json|parquet)$"),
    owner: Optional[str] = None,
    language: Optional[str] = None,
    min_stars: Optional[int] = None,
    db: Session = Depends(get_db)
):
    query = db.query(Repository)
    if owner and owner.strip():
        query = query.filter(Repository.owner.ilike(owner.strip()))
    if language and language.strip():
        query = query.filter(Repository.language.ilike(language.strip()))
    if min_stars is not None and min_stars > 0:
        query = query.filter(Repository.stars >= min_stars)

    repos = query.all()

    data = [{
        "Organization": r.owner,
        "Name": r.name,
        "Full_Name": r.full_name,
        "Description": r.description,
        "Language": r.language,
        "Stars": r.stars,
        "Forks": r.forks,
        "Open_Issues": r.open_issues,
        "URL": r.url,
        "Crawled_At": r.crawled_at.isoformat() if r.crawled_at else None
    } for r in repos]

    import re
    clean_owner = re.sub(r"[^\w\-]", "_", owner.strip()) if owner and owner.strip() else "all"
    filename = f"datagit_{clean_owner}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    if format == "csv":
        path = DataExporter.to_csv(data, filename)
        media_type = "text/csv"
    elif format == "json":
        path = DataExporter.to_json(data, filename)
        media_type = "application/json"
    else:
        path = DataExporter.to_parquet(data, filename)
        media_type = "application/octet-stream"

    return FileResponse(path=str(path), media_type=media_type, filename=path.name)
