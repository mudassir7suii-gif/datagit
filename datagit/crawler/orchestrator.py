from datetime import datetime, timezone
import logging
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text
from datagit.crawler.github_client import GitHubClient
from datagit.storage.models import CrawlJob, Repository, Commit, Issue
from datagit.storage.database import SessionLocal

logger = logging.getLogger("datagit.orchestrator")

def parse_iso(dt_str: Optional[str]) -> Optional[datetime]:
    if not dt_str:
        return None
    try:
        return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
    except Exception:
        return None

class CrawlOrchestrator:
    """Orchestrates crawl jobs, normalization, and database synchronization."""

    def __init__(self, client: Optional[GitHubClient] = None):
        self.client = client or GitHubClient()

    def run_job(self, job_id: int, max_pages: Optional[int] = 5) -> CrawlJob:
        db: Session = SessionLocal()
        job = db.query(CrawlJob).filter(CrawlJob.id == job_id).first()
        if not job:
            db.close()
            raise ValueError(f"Job #{job_id} not found.")

        job.status = "running"
        db.commit()

        try:
            target = job.target
            depth = job.depth or "metadata"
            effective_pages = max_pages or 5

            try:
                detected_type = self.client.detect_target_type(target)
                if detected_type:
                    job.target_type = detected_type.lower()
            except Exception:
                pass

            try:
                raw_repos = self.client.fetch_repositories(target, max_pages=effective_pages)
            except ValueError as fetch_err:
                # Epic P1.1: If single repo target is not found on GitHub, mark existing record as deleted
                if "/" in target:
                    existing_repo = db.query(Repository).filter(Repository.full_name == target).first()
                    if existing_repo:
                        existing_repo.is_deleted = True
                        existing_repo.crawled_at = datetime.now(timezone.utc)
                        job.status = "completed"
                        job.items_crawled = 1
                        job.total_found = 1
                        job.error_message = f"Repository '{target}' not found on GitHub; marked as deleted per Epic P1.1."
                        job.completed_at = datetime.now(timezone.utc)
                        db.commit()
                        return job
                raise fetch_err

            job.total_found = len(raw_repos)
            saved_count = 0
            BATCH_SIZE = 50

            for r in raw_repos:
                # Check for job cancellation
                db.refresh(job)
                if job.status == "cancelled":
                    logger.info(f"Crawl job #{job_id} was cancelled by user.")
                    break

                owner_login = (r.get("owner") or {}).get("login") or target
                full_name = r.get("full_name") or f"{owner_login}/{r.get('name', '')}"
                gh_id = r.get("id")
                
                # Check by github_id first to prevent duplicate key crashes when repos are renamed
                repo = None
                if gh_id:
                    repo = db.query(Repository).filter(Repository.github_id == gh_id).first()
                if not repo:
                    repo = db.query(Repository).filter(Repository.full_name == full_name).first()

                is_new = repo is None
                if is_new:
                    repo = Repository(full_name=full_name, github_id=gh_id)
                    db.add(repo)

                stars = r.get("stargazers_count", 0)
                forks = r.get("forks_count", 0)
                pushed_at_str = r.get("pushed_at")
                new_hash_raw = f"{full_name}:{stars}:{forks}:{pushed_at_str}"
                import hashlib
                new_hash = hashlib.sha256(new_hash_raw.encode("utf-8")).hexdigest()

                # Incremental Update Optimization per Constitution Principle 3:
                # If repository metadata has not changed since last crawl, skip heavy updates
                if not is_new and repo.content_hash == new_hash:
                    repo.crawled_at = datetime.now(timezone.utc)
                    saved_count += 1
                    job.items_crawled = saved_count
                    if saved_count % BATCH_SIZE == 0:
                        db.commit()
                    continue

                repo.full_name = full_name
                repo.github_id = gh_id
                repo.owner = owner_login
                repo.name = r.get("name", "")
                repo.description = r.get("description")
                repo.url = r.get("html_url", "")
                repo.language = r.get("language")
                repo.stars = stars
                repo.forks = forks
                repo.open_issues = r.get("open_issues_count", 0)
                repo.default_branch = r.get("default_branch", "main")
                repo.is_fork = r.get("fork", False)
                repo.is_private = r.get("private", False)
                repo.is_archived = r.get("archived", False)
                repo.repo_created_at = parse_iso(r.get("created_at"))
                repo.repo_updated_at = parse_iso(r.get("updated_at"))
                repo.repo_pushed_at = parse_iso(pushed_at_str)
                repo.crawled_at = datetime.now(timezone.utc)
                repo.content_hash = new_hash
                
                db.flush() # ensure repo.id exists

                # SQLite FTS sync
                try:
                    db.execute(text("INSERT OR REPLACE INTO repositories_fts(id, full_name, name, description) VALUES (:id, :full_name, :name, :description)"), {
                        "id": repo.id,
                        "full_name": repo.full_name,
                        "name": repo.name,
                        "description": repo.description or ""
                    })
                except Exception:
                    pass

                # Optional Deep Crawls: Commits & Issues
                if depth in ("commits", "full"):
                    raw_commits = self.client.fetch_commits(repo.owner, repo.name, limit=5)
                    for c in raw_commits:
                        sha = c.get("sha")
                        if sha and not db.query(Commit).filter(Commit.repo_id == repo.id, Commit.sha == sha).first():
                            commit_info = c.get("commit") or {}
                            if not isinstance(commit_info, dict):
                                commit_info = {}
                            author_info = commit_info.get("author") or {}
                            if not isinstance(author_info, dict):
                                author_info = {}
                            db.add(Commit(
                                repo_id=repo.id,
                                sha=sha,
                                author_name=author_info.get("name"),
                                author_email=author_info.get("email"),
                                message=commit_info.get("message"),
                                committed_at=parse_iso(author_info.get("date")),
                                url=c.get("html_url")
                            ))

                if depth in ("issues", "full"):
                    raw_issues = self.client.fetch_issues(repo.owner, repo.name, limit=5)
                    for iss in raw_issues:
                        if not isinstance(iss, dict):
                            continue
                        num = iss.get("number")
                        if num and not db.query(Issue).filter(Issue.repo_id == repo.id, Issue.github_number == num).first():
                            user_info = iss.get("user") or {}
                            db.add(Issue(
                                repo_id=repo.id,
                                github_number=num,
                                title=iss.get("title", ""),
                                state=iss.get("state", "open"),
                                author=user_info.get("login") if isinstance(user_info, dict) else None,
                                comments_count=iss.get("comments", 0),
                                is_pull_request="pull_request" in iss,
                                created_at=parse_iso(iss.get("created_at")),
                                closed_at=parse_iso(iss.get("closed_at")),
                                url=iss.get("html_url")
                            ))

                saved_count += 1
                job.items_crawled = saved_count
                
                # Batched database commit per Constitution Principle 3 & 4
                if saved_count % BATCH_SIZE == 0:
                    db.commit()

            if job.status != "cancelled":
                job.status = "completed"
            job.completed_at = datetime.now(timezone.utc)
            db.commit()

            # Epic P3.2: Dispatch webhook event for job completion
            try:
                from datagit.services.webhook_dispatcher import webhook_dispatcher
                webhook_dispatcher.dispatch_event(
                    event_name="job.completed",
                    data={
                        "job_id": job.id,
                        "target": job.target,
                        "status": job.status,
                        "items_crawled": job.items_crawled,
                        "total_found": job.total_found
                    },
                    workspace_id=job.workspace_id,
                    async_dispatch=True
                )
            except Exception:
                pass

            return job

        except Exception as e:
            logger.error(f"Error during crawl job #{job_id}: {e}", exc_info=True)
            try:
                db.rollback()
                job.status = "failed"
                job.error_message = str(e)
                job.completed_at = datetime.now(timezone.utc)
                db.commit()

                # Epic P3.2: Dispatch webhook event for job failure
                try:
                    from datagit.services.webhook_dispatcher import webhook_dispatcher
                    webhook_dispatcher.dispatch_event(
                        event_name="job.failed",
                        data={
                            "job_id": job.id,
                            "target": job.target,
                            "status": "failed",
                            "error": str(e)
                        },
                        workspace_id=job.workspace_id,
                        async_dispatch=True
                    )
                except Exception:
                    pass
            except Exception as rollback_err:
                logger.error(f"Failed to record failure status for job #{job_id}: {rollback_err}")
            raise
        finally:
            db.close()
