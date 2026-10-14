import urllib.request
import urllib.parse
import urllib.error
import json
from typing import Optional, Dict, Any, List

class DataGitAPIError(Exception):
    def __init__(self, status_code: int, detail: str):
        super().__init__(f"DataGit API Error {status_code}: {detail}")
        self.status_code = status_code
        self.detail = detail

class _BaseNamespace:
    def __init__(self, client: "DataGitClient"):
        self._client = client

    def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Any:
        return self._client._request("GET", path, params=params)

    def _post(self, path: str, body: Optional[Dict[str, Any]] = None) -> Any:
        return self._client._request("POST", path, body=body)

    def _delete(self, path: str) -> Any:
        return self._client._request("DELETE", path)


class JobsNamespace(_BaseNamespace):
    def list(self) -> List[Dict[str, Any]]:
        res = self._get("/api/jobs")
        return res.get("items", [])

    def create(self, target: str, depth: str = "metadata", max_pages: int = 3) -> Dict[str, Any]:
        return self._post("/api/jobs", body={"target": target, "depth": depth, "max_pages": max_pages})

    def get(self, job_id: int) -> Dict[str, Any]:
        return self._get(f"/api/jobs/{job_id}")

    def cancel(self, job_id: int) -> Dict[str, Any]:
        return self._post(f"/api/jobs/{job_id}/cancel")

    def rerun(self, job_id: int) -> Dict[str, Any]:
        return self._post(f"/api/jobs/{job_id}/rerun")


class RepositoriesNamespace(_BaseNamespace):
    def search(
        self,
        keyword: Optional[str] = None,
        language: Optional[str] = None,
        owner: Optional[str] = None,
        min_stars: int = 0,
        limit: int = 24,
        offset: int = 0
    ) -> Dict[str, Any]:
        params = {
            "search": keyword,
            "language": language,
            "owner": owner,
            "min_stars": min_stars,
            "limit": limit,
            "offset": offset
        }
        filtered_params = {k: v for k, v in params.items() if v is not None}
        return self._get("/api/repos", params=filtered_params)

    def get(self, repo_id: int) -> Dict[str, Any]:
        return self._get(f"/api/repos/{repo_id}")

    def delete(self, repo_id: int) -> Dict[str, Any]:
        return self._delete(f"/api/repos/{repo_id}")


class ExportsNamespace(_BaseNamespace):
    def download_bytes(
        self,
        format: str = "csv",
        search: Optional[str] = None,
        owner: Optional[str] = None,
        language: Optional[str] = None,
        min_stars: Optional[int] = None
    ) -> bytes:
        params = {
            "format": format,
            "search": search,
            "owner": owner,
            "language": language,
            "min_stars": min_stars
        }
        filtered_params = {k: str(v) for k, v in params.items() if v is not None}
        query_string = urllib.parse.urlencode(filtered_params)
        url = f"{self._client.base_url}/api/export?{query_string}"
        headers = self._client._build_headers()

        req = urllib.request.Request(url, headers=headers, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=self._client.timeout) as resp:
                return resp.read()
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8", errors="replace")
            raise DataGitAPIError(e.code, raw)

    def create_artifact(
        self,
        format: str = "csv",
        search: Optional[str] = None,
        owner: Optional[str] = None,
        language: Optional[str] = None,
        min_stars: Optional[int] = None
    ) -> Dict[str, Any]:
        body = {
            "format": format,
            "search": search,
            "owner": owner,
            "language": language,
            "min_stars": min_stars
        }
        return self._post("/api/export/generate", body={k: v for k, v in body.items() if v is not None})

    def list_artifacts(self) -> List[Dict[str, Any]]:
        res = self._get("/api/export/artifacts")
        return res.get("items", [])


class WebhooksNamespace(_BaseNamespace):
    def list(self) -> List[Dict[str, Any]]:
        res = self._get("/api/webhooks")
        return res.get("items", [])

    def create(self, url: str, secret: Optional[str] = None, events: Optional[List[str]] = None) -> Dict[str, Any]:
        body: Dict[str, Any] = {"url": url}
        if secret:
            body["secret"] = secret
        if events:
            body["events"] = ",".join(events)
        return self._post("/api/webhooks", body=body)

    def delete(self, webhook_id: int) -> Dict[str, Any]:
        return self._delete(f"/api/webhooks/{webhook_id}")

    def test(self, webhook_id: int) -> Dict[str, Any]:
        return self._post(f"/api/webhooks/{webhook_id}/test")


class WorkspacesNamespace(_BaseNamespace):
    def list(self) -> List[Dict[str, Any]]:
        res = self._get("/api/workspaces")
        return res.get("items", [])

    def create(self, name: str) -> Dict[str, Any]:
        return self._post("/api/workspaces", body={"name": name})


class SavedSearchesNamespace(_BaseNamespace):
    def list(self) -> List[Dict[str, Any]]:
        res = self._get("/api/saved-searches")
        return res.get("items", [])

    def create(self, name: str, query_params: Dict[str, Any], notify_on_new: bool = False, workspace_id: Optional[int] = None) -> Dict[str, Any]:
        return self._post("/api/saved-searches", body={
            "name": name,
            "query_params": query_params,
            "notify_on_new": notify_on_new,
            "workspace_id": workspace_id
        })

    def delete(self, search_id: int) -> Dict[str, Any]:
        return self._delete(f"/api/saved-searches/{search_id}")


class DataGitClient:
    """Official DataGit Python SDK Client."""

    def __init__(self, api_key: str, base_url: str = "http://localhost:8000", timeout: int = 30):
        self.api_key = api_key.strip()
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

        self.jobs = JobsNamespace(self)
        self.repositories = RepositoriesNamespace(self)
        self.exports = ExportsNamespace(self)
        self.webhooks = WebhooksNamespace(self)
        self.workspaces = WorkspacesNamespace(self)
        self.saved_searches = SavedSearchesNamespace(self)

    def _build_headers(self) -> Dict[str, str]:
        headers = {
            "User-Agent": "DataGit-Python-SDK/0.2.0",
            "Accept": "application/json"
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
            headers["X-API-Key"] = self.api_key
        return headers

    def _request(self, method: str, path: str, params: Optional[Dict[str, Any]] = None, body: Optional[Dict[str, Any]] = None) -> Any:
        url = f"{self.base_url}{path}"
        if params:
            query = urllib.parse.urlencode({k: str(v) for k, v in params.items() if v is not None})
            url = f"{url}?{query}"

        headers = self._build_headers()
        data = None
        if body is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(body).encode("utf-8")

        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                content = resp.read().decode("utf-8")
                if not content:
                    return {}
                return json.loads(content)
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8", errors="replace")
            try:
                err_json = json.loads(raw)
                detail = err_json.get("detail", raw)
            except Exception:
                detail = raw
            raise DataGitAPIError(e.code, detail)

    def ratelimit_status(self) -> Dict[str, Any]:
        return self._request("GET", "/api/ratelimit")
