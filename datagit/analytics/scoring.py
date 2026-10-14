from datetime import datetime, timezone
import math
from typing import Dict, Any, Optional

def calculate_repository_health(
    repo_pushed_at: Optional[datetime],
    stars: int = 0,
    forks: int = 0,
    open_issues: int = 0,
    is_archived: bool = False,
    is_deleted: bool = False,
    has_description: bool = True
) -> Dict[str, Any]:
    """Computes a standardized repository health score (0-100) per Epic P3.2."""
    now = datetime.now(timezone.utc)
    
    # 1. Recency & Maintenance Velocity (Max 40 points)
    recency_score = 0
    if repo_pushed_at:
        if repo_pushed_at.tzinfo is None:
            pushed_dt = repo_pushed_at.replace(tzinfo=timezone.utc)
        else:
            pushed_dt = repo_pushed_at
        days_since_push = max(0, (now - pushed_dt).days)

        if days_since_push <= 7:
            recency_score = 40
        elif days_since_push <= 30:
            recency_score = 34
        elif days_since_push <= 90:
            recency_score = 25
        elif days_since_push <= 180:
            recency_score = 15
        elif days_since_push <= 365:
            recency_score = 8
        else:
            recency_score = 2
    else:
        recency_score = 10

    # 2. Community Adoption & Traction (Max 25 points)
    popularity_score = 0
    effective_stars = max(0, stars)
    if effective_stars >= 10000:
        popularity_score = 25
    elif effective_stars >= 2500:
        popularity_score = 22
    elif effective_stars >= 500:
        popularity_score = 18
    elif effective_stars >= 100:
        popularity_score = 14
    elif effective_stars >= 10:
        popularity_score = 9
    elif effective_stars > 0:
        popularity_score = 5
    else:
        popularity_score = 2

    # 3. Issue Responsiveness & Ratio (Max 20 points)
    issue_score = 0
    if effective_stars > 0:
        ratio = open_issues / (effective_stars + 1)
        if ratio <= 0.05:
            issue_score = 20
        elif ratio <= 0.15:
            issue_score = 16
        elif ratio <= 0.30:
            issue_score = 12
        elif ratio <= 0.60:
            issue_score = 8
        else:
            issue_score = 4
    else:
        issue_score = 15 if open_issues <= 2 else 8

    # 4. Vitality & Hygiene (Max 15 points)
    vitality_score = 0
    if not is_archived:
        vitality_score += 8
    if not is_deleted:
        vitality_score += 4
    if has_description:
        vitality_score += 3

    total_score = min(100, max(0, recency_score + popularity_score + issue_score + vitality_score))

    if total_score >= 80:
        label = "Thriving"
        color = "emerald"
    elif total_score >= 60:
        label = "Active"
        color = "indigo"
    elif total_score >= 40:
        label = "Moderate"
        color = "amber"
    else:
        label = "Dormant"
        color = "red"

    return {
        "score": total_score,
        "label": label,
        "color": color,
        "breakdown": {
            "recency": recency_score,
            "popularity": popularity_score,
            "issue_hygiene": issue_score,
            "vitality": vitality_score
        }
    }
