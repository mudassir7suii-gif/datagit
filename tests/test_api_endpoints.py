import unittest
from fastapi.testclient import TestClient
from datagit.api.app import app
from datagit.storage.database import SessionLocal
from datagit.storage.models import CrawlJob

class TestAPIEndpoints(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.email = "tester_spec@datagit.dev"
        cls.password = "strong_password_99"

        # Ensure account exists and retrieve token
        r_signup = cls.client.post("/api/auth/signup", json={"email": cls.email, "password": cls.password})
        if r_signup.status_code == 200:
            cls.token = r_signup.json().get("access_token")
        else:
            r_signin = cls.client.post("/api/auth/signin", json={"email": cls.email, "password": cls.password})
            cls.token = r_signin.json().get("access_token")

        cls.auth_headers = {"Authorization": f"Bearer {cls.token}"}

    def test_unauthenticated_heavy_endpoints_fail_closed(self):
        """Constitution Non-Negotiable 1 Verification: No unauthenticated heavy endpoints."""
        unauth_client = TestClient(app)
        r_jobs = unauth_client.post("/api/jobs", json={"target": "testorg"})
        self.assertEqual(r_jobs.status_code, 401)

        r_crawl = unauth_client.post("/api/crawl", json={"target": "testorg"})
        self.assertEqual(r_crawl.status_code, 401)

        r_export = unauth_client.get("/api/export", params={"format": "csv"})
        self.assertEqual(r_export.status_code, 401)

        r_rate = unauth_client.get("/api/ratelimit")
        self.assertEqual(r_rate.status_code, 401)

        r_del = unauth_client.delete("/api/repos/1")
        self.assertEqual(r_del.status_code, 401)

    def test_signup_and_signin(self):
        email = "unique_tester_99@datagit.dev"
        password = "strong_password_99"

        # Sign Up
        r_signup = self.client.post("/api/auth/signup", json={"email": email, "password": password})
        self.assertIn(r_signup.status_code, (200, 400))

        # Sign In
        r_signin = self.client.post("/api/auth/signin", json={"email": email, "password": password})
        self.assertEqual(r_signin.status_code, 200)
        data = r_signin.json()
        self.assertIn("access_token", data)
        self.assertIn("datagit_access_token", r_signin.headers.get("set-cookie", ""))

    def test_authenticated_jobs_lifecycle_and_cancellation(self):
        """Tests job creation, listing, status inspection, and cancellation."""
        r_create = self.client.post(
            "/api/jobs",
            json={"target": "facebook/react", "depth": "metadata", "max_pages": 1},
            headers=self.auth_headers
        )
        self.assertEqual(r_create.status_code, 200)
        data = r_create.json()
        job_id = data.get("job_id")
        self.assertIsNotNone(job_id)

        # Inspect job
        r_get = self.client.get(f"/api/jobs/{job_id}", headers=self.auth_headers)
        self.assertEqual(r_get.status_code, 200)
        self.assertEqual(r_get.json()["target"], "facebook/react")

        # Cancel job (create a running job to test cancellation cleanly without background task race)
        with SessionLocal() as db:
            active_job = CrawlJob(target="test/cancel-active", target_type="repo", depth="metadata", status="running")
            db.add(active_job)
            db.commit()
            active_job_id = active_job.id

        r_cancel = self.client.post(f"/api/jobs/{active_job_id}/cancel", headers=self.auth_headers)
        self.assertEqual(r_cancel.status_code, 200)
        self.assertEqual(r_cancel.json()["status"], "cancelled")

        # Cancelling an already cancelled job returns 400
        r_cancel_again = self.client.post(f"/api/jobs/{active_job_id}/cancel", headers=self.auth_headers)
        self.assertEqual(r_cancel_again.status_code, 400)

        # List jobs
        r_list = self.client.get("/api/jobs", headers=self.auth_headers)
        self.assertEqual(r_list.status_code, 200)
        self.assertIn("items", r_list.json())

    def test_insights_and_search_endpoints(self):
        r_insights = self.client.get("/api/insights")
        self.assertEqual(r_insights.status_code, 200)
        data = r_insights.json()
        self.assertIn("total_repositories", data)
        self.assertIn("top_languages", data)

        r_search = self.client.get("/api/repos", params={"limit": 5, "min_stars": 10})
        self.assertEqual(r_search.status_code, 200)
        res = r_search.json()
        self.assertIn("items", res)
        self.assertIn("total", res)

    def test_repository_details_and_deletion(self):
        """Tests fetching details with commits/issues and soft-deletion."""
        r_search = self.client.get("/api/repos", params={"limit": 1})
        items = r_search.json().get("items", [])
        if not items:
            return
        repo_id = items[0]["id"]

        # Details
        r_detail = self.client.get(f"/api/repos/{repo_id}")
        self.assertEqual(r_detail.status_code, 200)
        data = r_detail.json()
        self.assertIn("commits", data)
        self.assertIn("issues", data)

        # Soft delete
        r_del = self.client.delete(f"/api/repos/{repo_id}", headers=self.auth_headers)
        self.assertEqual(r_del.status_code, 200)

        # Fetching deleted repo returns 404
        r_after = self.client.get(f"/api/repos/{repo_id}")
        self.assertEqual(r_after.status_code, 404)

    def test_authenticated_streaming_export(self):
        """Tests streaming CSV and JSON exports with active filter parameters."""
        r_csv = self.client.get(
            "/api/export",
            params={"format": "csv", "min_stars": 100},
            headers=self.auth_headers
        )
        self.assertEqual(r_csv.status_code, 200)
        self.assertIn("text/csv", r_csv.headers.get("content-type", ""))
        self.assertIn("Organization,Name,Full_Name", r_csv.text)

        r_json = self.client.get(
            "/api/export",
            params={"format": "json", "min_stars": 100},
            headers=self.auth_headers
        )
        self.assertEqual(r_json.status_code, 200)
        self.assertIn("application/json", r_json.headers.get("content-type", ""))

    def test_metrics_observability_endpoint(self):
        """Epic 9: Tests metrics telemetry endpoint."""
        r = self.client.get("/api/metrics", headers=self.auth_headers)
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["status"], "healthy")
        self.assertIn("active_jobs", data)
        self.assertIn("rate_limits", data)

    def test_auth_validation_rules(self):
        # Invalid email
        r = self.client.post("/api/auth/signup", json={"email": "not-an-email", "password": "valid_password_123"})
        self.assertEqual(r.status_code, 400)

        # Short password (< 8 chars)
        r = self.client.post("/api/auth/signup", json={"email": "valid@email.com", "password": "12345"})
        self.assertEqual(r.status_code, 400)

    def test_ratelimit_status_authenticated(self):
        r = self.client.get("/api/ratelimit", headers=self.auth_headers)
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn("active_tokens_count", data)
        self.assertIn("total_remaining_requests", data)

    def test_auth_rate_limiting_lockout(self):
        """Epic 1: Tests sliding window rate limiting on auth endpoints."""
        from datagit.api.app import AuthRateLimiter
        limiter = AuthRateLimiter(limit=3, window_seconds=60)
        self.assertTrue(limiter.check("10.0.0.1"))
        self.assertTrue(limiter.check("10.0.0.1"))
        self.assertTrue(limiter.check("10.0.0.1"))
        self.assertFalse(limiter.check("10.0.0.1"))
        # Another IP should not be locked out
        self.assertTrue(limiter.check("10.0.0.2"))

if __name__ == "__main__":
    unittest.main()
