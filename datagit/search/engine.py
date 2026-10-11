from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, desc, asc
from datagit.storage.models import Repository

class SearchEngine:
    """Provides structured filtering and full-text keyword search across crawled repositories."""

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
        query = db.query(Repository)

        # Keyword search across name and description
        if keyword and keyword.strip():
            term = f"%{keyword.strip()}%"
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
                "crawled_at": r.crawled_at.isoformat() if r.crawled_at else None
            })

        return {
            "total": total_count,
            "limit": limit,
            "offset": offset,
            "items": results
        }

    @staticmethod
    def get_insights(db: Session) -> Dict[str, Any]:
        """Calculates global metrics and language breakdown."""
        total_repos = db.query(Repository).count()
        total_stars = db.query(func.sum(Repository.stars)).scalar() or 0
        total_forks = db.query(func.sum(Repository.forks)).scalar() or 0

        # Top languages
        top_languages = (
            db.query(Repository.language, func.count(Repository.id).label("count"))
            .filter(Repository.language.isnot(None), Repository.language != "")
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
