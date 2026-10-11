from datetime import datetime, timezone
import logging
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
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

            raw_repos = self.client.fetch_repositories(target, max_pages=effective_pages)
            job.total_found = len(raw_repos)
            saved_count = 0

            for r in raw_repos:
                full_name = r.get("full_name") or f"{target}/{r.get('name')}"
                gh_id = r.get("id")
                
                # Check by github_id first to prevent duplicate key crashes when repos are renamed
                repo = None
                if gh_id:
                    repo = db.query(Repository).filter(Repository.github_id == gh_id).first()
                if not repo:
                    repo = db.query(Repository).filter(Repository.full_name == full_name).first()
                if not repo:
                    repo = Repository(full_name=full_name, github_id=gh_id)
                    db.add(repo)

                repo.full_name = full_name
                repo.github_id = gh_id
                repo.owner = (r.get("owner") or {}).get("login", target)
                repo.name = r.get("name", "")
                repo.description = r.get("description")
                repo.url = r.get("html_url", "")
                repo.language = r.get("language")
                repo.stars = r.get("stargazers_count", 0)
                repo.forks = r.get("forks_count", 0)
                repo.open_issues = r.get("open_issues_count", 0)
                repo.default_branch = r.get("default_branch", "main")
                repo.is_fork = r.get("fork", False)
                repo.is_private = r.get("private", False)
                repo.repo_created_at = parse_iso(r.get("created_at"))
                repo.repo_updated_at = parse_iso(r.get("updated_at"))
                repo.repo_pushed_at = parse_iso(r.get("pushed_at"))
                repo.crawled_at = datetime.now(timezone.utc)
                repo.content_hash = repo.generate_hash()
                
                db.flush() # ensure repo.id exists

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
                db.commit()

            job.status = "completed"
            job.completed_at = datetime.now(timezone.utc)
            db.commit()
            return job

        except Exception as e:
            logger.error(f"Error during crawl job #{job_id}: {e}", exc_info=True)
            try:
                db.rollback()
                job.status = "failed"
                job.error_message = str(e)
                job.completed_at = datetime.now(timezone.utc)
                db.commit()
            except Exception as rollback_err:
                logger.error(f"Failed to record failure status for job #{job_id}: {rollback_err}")
            raise
        finally:
            db.close()
