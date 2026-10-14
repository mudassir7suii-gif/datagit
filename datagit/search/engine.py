from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, desc, asc, text
from datagit.storage.models import Repository, Commit, Issue
from datagit.analytics.scoring import calculate_repository_health

class SearchEngine:
    """Provides structured filtering and FTS5 full-text search across crawled repositories."""

    @staticmethod
    def query_repositories(
        db: Session,
        keyword: Optional[str] = None,
        language: Optional[str] = None,
        owner: Optional[str] = None,
        min_stars: Optional[int] = None,
        sort_by: str = "stars",
        order: str = "desc",
        limit: int = 50,
        offset: int = 0
    ) -> Dict[str, Any]:
        query = db.query(Repository).filter(Repository.is_deleted.isnot(True))

        # High-performance search: Try SQLite FTS5 first, fallback to ILIKE
        if keyword and keyword.strip():
            clean_kw = keyword.strip()
            fts_ids = None
            try:
                # FTS5 match query with prefix support
                fts_term = f'"{clean_kw}"*'
                fts_res = db.execute(
                    text("SELECT id FROM repositories_fts WHERE repositories_fts MATCH :t LIMIT 500"),
                    {"t": fts_term}
                ).fetchall()
                if fts_res:
                    fts_ids = [row[0] for row in fts_res]
            except Exception:
                fts_ids = None

            if fts_ids is not None:
                query = query.filter(Repository.id.in_(fts_ids))
            else:
                term = f"%{clean_kw}%"
                query = query.filter(
                    or_(
                        Repository.name.ilike(term),
                        Repository.full_name.ilike(term),
                        Repository.description.ilike(term)
                    )
                )

        if language and language.strip():
            query = query.filter(Repository.language.ilike(language.strip()))

        if owner and owner.strip():
            query = query.filter(Repository.owner.ilike(owner.strip()))

        if min_stars is not None and min_stars > 0:
            query = query.filter(Repository.stars >= min_stars)

        total_count = query.count()

        # Safe Sorting with whitelisted columns
        ALLOWED_SORT_FIELDS = {
            "stars": Repository.stars,
            "forks": Repository.forks,
            "open_issues": Repository.open_issues,
            "crawled_at": Repository.crawled_at,
            "name": Repository.name,
            "repo_pushed_at": Repository.repo_pushed_at,
            "repo_created_at": Repository.repo_created_at
        }
        sort_column = ALLOWED_SORT_FIELDS.get(sort_by.lower() if sort_by else "", Repository.stars)
        if order.lower() == "asc":
            query = query.order_by(asc(sort_column))
        else:
            query = query.order_by(desc(sort_column))

        items = query.offset(offset).limit(limit).all()

        results = []
        for r in items:
            health = calculate_repository_health(
                repo_pushed_at=r.repo_pushed_at,
                stars=r.stars or 0,
                forks=r.forks or 0,
                open_issues=r.open_issues or 0,
                is_archived=bool(r.is_archived),
                is_deleted=bool(r.is_deleted),
                has_description=bool(r.description)
            )
            results.append({
                "id": r.id,
                "github_id": r.github_id,
                "owner": r.owner,
                "name": r.name,
                "full_name": r.full_name,
                "description": r.description,
                "url": r.url,
                "language": r.language,
                "stars": r.stars,
                "forks": r.forks,
                "open_issues": r.open_issues,
                "is_archived": r.is_archived,
                "repo_pushed_at": r.repo_pushed_at.isoformat() if r.repo_pushed_at else None,
                "crawled_at": r.crawled_at.isoformat() if r.crawled_at else None,
                "health": health
            })

        return {
            "total": total_count,
            "limit": limit,
            "offset": offset,
            "items": results
        }

    @staticmethod
    def get_repository_details(db: Session, repo_id: int) -> Optional[Dict[str, Any]]:
        """Fetches full repository metadata along with recent commits and issues."""
        repo = db.query(Repository).filter(Repository.id == repo_id, Repository.is_deleted.isnot(True)).first()
        if not repo:
            return None

        commits = db.query(Commit).filter(Commit.repo_id == repo.id).order_by(Commit.committed_at.desc()).limit(20).all()
        issues = db.query(Issue).filter(Issue.repo_id == repo.id).order_by(Issue.created_at.desc()).limit(20).all()

        health = calculate_repository_health(
            repo_pushed_at=repo.repo_pushed_at,
            stars=repo.stars or 0,
            forks=repo.forks or 0,
            open_issues=repo.open_issues or 0,
            is_archived=bool(repo.is_archived),
            is_deleted=bool(repo.is_deleted),
            has_description=bool(repo.description)
        )

        return {
            "id": repo.id,
            "github_id": repo.github_id,
            "owner": repo.owner,
            "name": repo.name,
            "full_name": repo.full_name,
            "description": repo.description,
            "url": repo.url,
            "language": repo.language,
            "stars": repo.stars,
            "forks": repo.forks,
            "open_issues": repo.open_issues,
            "default_branch": repo.default_branch,
            "is_fork": repo.is_fork,
            "is_private": repo.is_private,
            "is_archived": repo.is_archived,
            "repo_created_at": repo.repo_created_at.isoformat() if repo.repo_created_at else None,
            "repo_updated_at": repo.repo_updated_at.isoformat() if repo.repo_updated_at else None,
            "repo_pushed_at": repo.repo_pushed_at.isoformat() if repo.repo_pushed_at else None,
            "crawled_at": repo.crawled_at.isoformat() if repo.crawled_at else None,
            "health": health,
            "commits": [{
                "id": c.id,
                "sha": c.sha,
                "author_name": c.author_name,
                "author_email": c.author_email,
                "message": c.message,
                "committed_at": c.committed_at.isoformat() if c.committed_at else None,
                "url": c.url
            } for c in commits],
            "issues": [{
                "id": i.id,
                "github_number": i.github_number,
                "title": i.title,
                "state": i.state,
                "author": i.author,
                "comments_count": i.comments_count,
                "is_pull_request": i.is_pull_request,
                "created_at": i.created_at.isoformat() if i.created_at else None,
                "closed_at": i.closed_at.isoformat() if i.closed_at else None,
                "url": i.url
            } for i in issues]
        }

    @staticmethod
    def get_insights(db: Session) -> Dict[str, Any]:
        """Calculates global metrics and language breakdown."""
        total_repos = db.query(Repository).filter(Repository.is_deleted.isnot(True)).count()
        total_stars = db.query(func.sum(Repository.stars)).filter(Repository.is_deleted.isnot(True)).scalar() or 0
        total_forks = db.query(func.sum(Repository.forks)).filter(Repository.is_deleted.isnot(True)).scalar() or 0

        # Top languages
        top_languages = (
            db.query(Repository.language, func.count(Repository.id).label("count"))
            .filter(Repository.language.isnot(None), Repository.language != "", Repository.is_deleted.isnot(True))
            .group_by(Repository.language)
            .order_by(desc("count"))
            .limit(10)
            .all()
        )

        return {
            "total_repositories": total_repos,
            "total_stars": total_stars,
            "total_forks": total_forks,
            "top_languages": [{"language": lang, "count": cnt} for lang, cnt in top_languages]
        }
