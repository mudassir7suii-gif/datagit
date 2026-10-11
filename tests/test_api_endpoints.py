import unittest
from fastapi.testclient import TestClient
from datagit.api.app import app

class TestAPIEndpoints(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_signup_and_signin(self):
        email = "tester_mvp@datagit.dev"
        password = "strong_password_99"

        # Sign Up
        r_signup = self.client.post("/api/auth/signup", json={"email": email, "password": password})
        self.assertIn(r_signup.status_code, (200, 400)) # 200 or already exists

        # Sign In
        r_signin = self.client.post("/api/auth/signin", json={"email": email, "password": password})
        self.assertEqual(r_signin.status_code, 200)
        data = r_signin.json()
        self.assertIn("access_token", data)

    def test_insights_endpoint(self):
        r = self.client.get("/api/insights")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn("total_repositories", data)
        self.assertIn("top_languages", data)

    def test_repos_search_endpoint(self):
        r = self.client.get("/api/repos", params={"limit": 5, "min_stars": 10})
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn("items", data)
        self.assertIn("total", data)

    def test_ratelimit_telemetry_endpoint(self):
        r = self.client.get("/api/ratelimit")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn("active_tokens_count", data)
        self.assertIn("total_remaining_requests", data)

    def test_export_endpoint(self):
        r_csv = self.client.get("/api/export", params={"format": "csv"})
        self.assertEqual(r_csv.status_code, 200)
        self.assertEqual(r_csv.headers.get("content-type"), "text/csv; charset=utf-8")

        r_json = self.client.get("/api/export", params={"format": "json"})
        self.assertEqual(r_json.status_code, 200)
        self.assertEqual(r_json.headers.get("content-type"), "application/json")

        r_pq = self.client.get("/api/export", params={"format": "parquet"})
        self.assertEqual(r_pq.status_code, 200)
        self.assertEqual(r_pq.headers.get("content-type"), "application/octet-stream")

    def test_auth_validation(self):
        # Invalid email
        r = self.client.post("/api/auth/signup", json={"email": "not-an-email", "password": "valid_password"})
        self.assertEqual(r.status_code, 400)

        # Short password
        r = self.client.post("/api/auth/signup", json={"email": "valid@email.com", "password": "123"})
        self.assertEqual(r.status_code, 400)

    def test_jobs_creation_with_null_max_pages(self):
        r = self.client.post("/api/jobs", json={"target": "testorg", "max_pages": None})
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn("job_id", data)
        self.assertEqual(data["status"], "queued")

if __name__ == "__main__":
    unittest.main()
