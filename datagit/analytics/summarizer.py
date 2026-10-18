from typing import Dict, Any, Optional
from datetime import datetime, timezone
import json
import logging
from sqlalchemy.orm import Session
from datagit.storage.models import Repository, Commit, Issue, User
from datagit.config import settings

logger = logging.getLogger("datagit.summarizer")

class RepositorySummarizer:
    @staticmethod
    def is_eligible_for_summary(user: User) -> bool:
        """Enforces Epic P3.2: summary generation is restricted to paid plan tiers."""
        return user.plan in ("pro", "enterprise", "team")

    @classmethod
    def generate_summary(cls, repo: Repository, db: Session, user: Optional[User] = None, force_refresh: bool = False) -> Dict[str, Any]:
        """Generates or retrieves an AI-powered technical summary for a repository."""
        if user and not cls.is_eligible_for_summary(user):
            raise PermissionError("Repository technical summary generation requires a Pro or Enterprise tier subscription.")

        # Return cached summary if available and not forcing refresh
        if repo.ai_summary and not force_refresh:
            try:
                cached = json.loads(repo.ai_summary)
                return cached
            except Exception:
                pass

        # Gather repository context
        recent_commits = db.query(Commit).filter(Commit.repo_id == repo.id).order_by(Commit.committed_at.desc()).limit(10).all()
        recent_issues = db.query(Issue).filter(Issue.repo_id == repo.id).order_by(Issue.created_at.desc()).limit(10).all()

        commit_msgs = [c.message for c in recent_commits if c.message]
        issue_titles = [iss.title for iss in recent_issues if iss.title]

        # Check for external LLM API keys (Groq, Google Gemini, etc.)
        llm_summary = cls._call_external_llm(repo, commit_msgs, issue_titles)
        if not llm_summary:
            llm_summary = cls._generate_extractive_summary(repo, commit_msgs, issue_titles)

        # Store in database
        repo.ai_summary = json.dumps(llm_summary)
        db.commit()

        return llm_summary

    @classmethod
    def _call_external_llm(cls, repo: Repository, commit_msgs: list, issue_titles: list) -> Optional[Dict[str, Any]]:
        # Attempt Gemini / Groq if configured
        import os
        gemini_key = os.getenv("GEMINI_API_KEY") or getattr(settings, "gemini_api_key", None)
        if gemini_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=gemini_key)
                model = genai.GenerativeModel("gemini-1.5-flash")
                prompt = (
                    f"Analyze this GitHub repository and output concise JSON with keys: "
                    f"overview (string), tech_stack (list of strings), primary_use_case (string), "
                    f"activity_level (string: high/medium/low), rag_recommendation (string).\n"
                    f"Repository: {repo.full_name}\nDescription: {repo.description}\n"
                    f"Language: {repo.language}\nStars: {repo.stars}\nRecent Commits: {commit_msgs[:5]}\n"
                    f"Recent Issues: {issue_titles[:5]}"
                )
                response = model.generate_content(prompt)
                text = response.text.strip()
                if "```json" in text:
                    text = text.split("```json")[1].split("```")[0].strip()
                elif "```" in text:
                    text = text.split("```")[1].split("```")[0].strip()
                return json.loads(text)
            except Exception as e:
                logger.debug(f"External LLM call failed or skipped: {e}")

        return None

    @classmethod
    def _generate_extractive_summary(cls, repo: Repository, commit_msgs: list, issue_titles: list) -> Dict[str, Any]:
        """High-precision extractive technical analysis for instant offline or fallback summaries."""
        stars = repo.stars or 0
        forks = repo.forks or 0
        lang = repo.language or "Multi-language"

        activity = "High" if stars > 1000 or len(commit_msgs) >= 5 else ("Moderate" if stars > 100 else "Emerging")

        tags = [lang]
        if repo.description:
            desc_lower = repo.description.lower()
            for tech in ["python", "rust", "typescript", "react", "next.js", "docker", "llm", "rag", "pytorch", "fastapi", "ai"]:
                if tech in desc_lower and tech.title() not in tags:
                    tags.append(tech.title())

        overview = (
            f"{repo.full_name} is an active {lang} repository with {stars:,} stars and {forks:,} forks. "
            f"{repo.description or 'No explicit description provided.'} "
            f"Shows {activity.lower()} developmental velocity based on recent commits and issue activity."
        )

        rag_rec = (
            f"Highly suitable for code ingestion and AI retrieval corpora. "
            f"Recommended export format: RAG JSON or Parquet with AST chunks."
            if stars > 50 else
            f"Standard utility repository; suitable for general software dataset collections."
        )

        return {
            "overview": overview,
            "tech_stack": tags,
            "primary_use_case": f"{lang} software development and repository tooling",
            "activity_level": activity,
            "stars_count": stars,
            "forks_count": forks,
            "recent_focus": commit_msgs[0] if commit_msgs else "Routine maintenance",
            "rag_recommendation": rag_rec,
            "generated_at": datetime.now(timezone.utc).isoformat()
        }
