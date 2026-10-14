import requests
import time
import random
import logging
from typing import Dict, Any, List, Optional, Tuple
from datagit.config import settings
from datagit.core.token_manager import TokenManager

logger = logging.getLogger("datagit.crawler")

class GitHubClient:
    """Production-grade GitHub API client respecting Constitution Principle 2 & Rate Limits."""

    def __init__(self, token_manager: Optional[TokenManager] = None):
        if token_manager:
            self.token_manager = token_manager
        else:
            self.token_manager = TokenManager(settings.github_tokens)
        self.base_url = settings.github_api_base
        self.last_request_time: float = 0.0
        self.min_pacing_seconds: float = 0.25 # 250ms baseline pacing

    def _pace_request(self) -> None:
        """Enforces inter-request pacing and jitter per Constitution Principle 2."""
        now = time.time()
        elapsed = now - self.last_request_time
        jitter = random.uniform(0.05, 0.15)
        required_wait = (self.min_pacing_seconds + jitter) - elapsed
        if required_wait > 0:
            time.sleep(required_wait)
        self.last_request_time = time.time()

    def _request(self, endpoint: str, params: Optional[Dict[str, Any]] = None, retries: int = 3) -> Tuple[int, Any, Dict[str, str]]:
        """Executes HTTP request with rate-limit tracking, pacing, retries, and token rotation."""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        params = params or {}

        for attempt in range(retries):
            self._pace_request()
            token_status = self.token_manager.acquire_token()
            headers = {
                "Accept": "application/vnd.github+json",
                "User-Agent": "DataGit-Crawler/0.2.0"
            }
            if token_status.token:
                headers["Authorization"] = f"Bearer {token_status.token}"

            try:
                response = requests.get(url, headers=headers, params=params, timeout=settings.request_timeout)
                # Update rate limits from GitHub response headers
                self.token_manager.update_limits(token_status.token, dict(response.headers))

                # Handle Rate Limit HTTP 403 or 429
                if response.status_code in (403, 429):
                    msg = ""
                    try:
                        if response.content:
                            body = response.json()
                            if isinstance(body, dict):
                                msg = body.get("message", "")
                    except Exception:
                        msg = response.text or ""

                    is_secondary = "secondary rate limit" in msg.lower()
                    is_standard_rate = "rate limit" in msg.lower()

                    if is_secondary or is_standard_rate or response.status_code == 429:
                        token_status.remaining = 0
                        if is_secondary:
                            # Exponential backoff starting at 60s for secondary rate limits
                            retry_after = max(60, int(response.headers.get("retry-after", 60))) * (2 ** attempt)
                            logger.warning(
                                f"GitHub Secondary Rate Limit hit on {token_status.token_masked}. Backing off {retry_after}s..."
                            )
                        else:
                            retry_after = max(5, int(response.headers.get("retry-after", 5)))
                            logger.warning(
                                f"Rate limit triggered on {token_status.token_masked}. Waiting {retry_after}s..."
                            )

                        time.sleep(retry_after)
                        continue

                # Handle transient server errors with backoff
                if response.status_code in (500, 502, 503, 504):
                    logger.warning(f"GitHub server error {response.status_code}. Retrying ({attempt+1}/{retries})...")
                    time.sleep(2 ** attempt)
                    continue

                if response.status_code == 200:
                    return 200, response.json(), dict(response.headers)
                elif response.status_code == 404:
                    return 404, None, dict(response.headers)
                else:
                    return response.status_code, response.text, dict(response.headers)

            except requests.RequestException as e:
                logger.error(f"Network error requesting {url}: {e}")
                if attempt == retries - 1:
                    raise
                time.sleep(2 ** attempt)

        raise RuntimeError(f"Failed to fetch {url} after {retries} retries.")

    def detect_target_type(self, target: str) -> Optional[str]:
        """Determines if target is a single Repository (owner/repo), Organization, User, or Global Search/Topic."""
        clean_target = target.strip().strip("/")
        if clean_target.startswith("topic:"):
            return "Topic"
        if clean_target.startswith("search:") or clean_target.startswith("query:"):
            return "Search"

        if "/" in clean_target:
            # Single repository target
            status, data, _ = self._request(f"/repos/{clean_target}")
            if status == 200 and isinstance(data, dict):
                return "Repository"
            if status == 404:
                return None
            if status in (401, 403):
                raise RuntimeError(f"GitHub API access error ({status}) checking repo '{clean_target}': {data}")

        status, data, _ = self._request(f"/users/{clean_target}")
        if status == 200 and isinstance(data, dict):
            return data.get("type", "User")
        if status in (401, 403):
            raise RuntimeError(f"GitHub API authentication/access error ({status}) checking '{clean_target}': {data}")

        # Fallback: Check if target matches global GitHub repositories (e.g. claude, chatgpt, gemini, llm)
        status, search_data, _ = self._request("/search/repositories", params={"q": clean_target, "per_page": 1})
        if status == 200 and isinstance(search_data, dict) and search_data.get("total_count", 0) > 0:
            return "Search"

        return None

    def fetch_repositories(self, target: str, max_pages: Optional[int] = 10, per_page: int = 100) -> List[Dict[str, Any]]:
        """Crawls all repositories for a user, organization, single repository, or global GitHub search/topic."""
        clean_target = target.strip().strip("/")
        target_type = self.detect_target_type(clean_target)
        if target_type is None:
            raise ValueError(f"GitHub target '{clean_target}' was not found on GitHub.")

        if target_type == "Repository":
            status, repo_data, _ = self._request(f"/repos/{clean_target}")
            if status == 200 and isinstance(repo_data, dict):
                return [repo_data]
            raise ValueError(f"Failed to fetch single repository '{clean_target}' (status {status}).")

        if target_type in ("Search", "Topic"):
            if clean_target.startswith("topic:"):
                query = f"topic:{clean_target[6:].strip()}"
            elif clean_target.startswith("search:"):
                query = clean_target[7:].strip()
            elif clean_target.startswith("query:"):
                query = clean_target[6:].strip()
            else:
                query = clean_target

            all_repos = []
            page = 1
            effective_max = max_pages or 10

            logger.info(f"Crawling global GitHub repositories matching query '{query}' (max_pages={effective_max})...")

            while page <= effective_max:
                status, page_data, _ = self._request(
                    "/search/repositories",
                    params={"q": query, "sort": "stars", "order": "desc", "per_page": per_page, "page": page}
                )
                if status != 200 or not isinstance(page_data, dict):
                    if page == 1 and status != 404:
                        raise RuntimeError(f"GitHub Search API error {status} for query '{query}': {page_data}")
                    break

                items = page_data.get("items", [])
                if not items:
                    break

                all_repos.extend(items)
                total_count = page_data.get("total_count", 0)
                if len(items) < per_page or len(all_repos) >= total_count:
                    break
                page += 1

            logger.info(f"Retrieved {len(all_repos)} repositories across GitHub for query '{query}'.")
            return all_repos

        endpoint = f"/orgs/{clean_target}/repos" if target_type == "Organization" else f"/users/{clean_target}/repos"
        
        all_repos = []
        page = 1
        effective_max = max_pages or 10

        logger.info(f"Crawling {target_type} '{clean_target}' via {endpoint} (max_pages={effective_max})...")

        while page <= effective_max:
            status, page_data, _ = self._request(endpoint, params={"per_page": per_page, "page": page, "sort": "pushed"})
            if status != 200:
                if page == 1 and status != 404:
                    raise RuntimeError(f"GitHub API error {status} fetching repos for '{clean_target}': {page_data}")
                break

            if not page_data or not isinstance(page_data, list):
                break

            all_repos.extend(page_data)
            if len(page_data) < per_page:
                break
            page += 1

        logger.info(f"Retrieved {len(all_repos)} repositories for '{clean_target}'.")
        return all_repos

    def fetch_commits(self, owner: str, repo: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Fetches recent commits for a repository."""
        status, commits, _ = self._request(f"/repos/{owner}/{repo}/commits", params={"per_page": limit})
        if status == 200 and isinstance(commits, list):
            return commits
        return []

    def fetch_issues(self, owner: str, repo: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Fetches recent issues and PRs for a repository."""
        status, issues, _ = self._request(f"/repos/{owner}/{repo}/issues", params={"per_page": limit, "state": "all"})
        if status == 200 and isinstance(issues, list):
            return issues
        return []
