import unittest
import uuid
from fastapi.testclient import TestClient
from datagit.api.app import app
from datagit.storage.database import SessionLocal
from datagit.storage.models import CrawlJob

class TestAPIEndpoints(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.email = f"tester_{uuid.uuid4().hex[:8]}@datagit.dev"
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

    def test_job_rerun_endpoint(self):
        """Spec 4.2: Tests idempotent job re-enqueueing."""
        r_create = self.client.post(
            "/api/jobs",
            json={"target": "pallets/flask", "depth": "metadata", "max_pages": 1},
            headers=self.auth_headers
        )
        self.assertEqual(r_create.status_code, 200)
        job_id = r_create.json()["job_id"]

        r_rerun = self.client.post(f"/api/jobs/{job_id}/rerun", headers=self.auth_headers)
        self.assertEqual(r_rerun.status_code, 200)
        rerun_data = r_rerun.json()
        self.assertIn("job_id", rerun_data)
        self.assertEqual(rerun_data["target"], "pallets/flask")
        self.assertEqual(rerun_data["original_job_id"], job_id)

    def test_plans_endpoint(self):
        """Spec 4.7: Tests transparent pricing and quotas endpoint."""
        r = self.client.get("/api/plans")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn("plans", data)
        self.assertTrue(len(data["plans"]) >= 3)
        plan_ids = [p["id"] for p in data["plans"]]
        self.assertIn("free", plan_ids)
        self.assertIn("pro", plan_ids)

    def test_account_deletion_gdpr(self):
        """Spec 4.1: Tests privacy compliance and self-serve account deletion."""
        temp_email = f"to_delete_{uuid.uuid4().hex[:8]}@datagit.dev"
        temp_pass = "temporary_password_123"
        r_signup = self.client.post("/api/auth/signup", json={"email": temp_email, "password": temp_pass})
        self.assertEqual(r_signup.status_code, 200)
        token = r_signup.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Delete account
        r_del = self.client.delete("/api/auth/account", headers=headers)
        self.assertEqual(r_del.status_code, 200)
        self.assertIn("successfully deleted", r_del.json()["message"])

        # Signing in again fails with 401
        r_signin = self.client.post("/api/auth/signin", json={"email": temp_email, "password": temp_pass})
        self.assertEqual(r_signin.status_code, 401)

    def test_account_lockout_after_consecutive_failed_attempts(self):
        """Technical Plan P0.4: Verifies account lockout on 5 consecutive failed sign-in attempts."""
        lockout_email = f"lockout_{uuid.uuid4().hex[:8]}@datagit.dev"
        correct_pass = "correct_password_123"
        wrong_pass = "wrong_password_999"

        # Register account
        r_up = self.client.post("/api/auth/signup", json={"email": lockout_email, "password": correct_pass})
        self.assertEqual(r_up.status_code, 200)

        # 4 consecutive bad attempts should return 401
        for _ in range(4):
            r = self.client.post("/api/auth/signin", json={"email": lockout_email, "password": wrong_pass})
            self.assertEqual(r.status_code, 401)

        # 5th bad attempt triggers lockout
        r5 = self.client.post("/api/auth/signin", json={"email": lockout_email, "password": wrong_pass})
        self.assertEqual(r5.status_code, 401)

        # 6th attempt (even with CORRECT password) is rejected with 423 Locked
        r6 = self.client.post("/api/auth/signin", json={"email": lockout_email, "password": correct_pass})
        self.assertEqual(r6.status_code, 423)
        self.assertIn("temporarily locked", r6.json().get("detail", ""))

    def test_audit_log_endpoint(self):
        """Technical Plan P0.11: Verifies audit log inspection endpoint."""
        # Unauthenticated request fails closed with 401
        unauth = TestClient(app)
        self.assertEqual(unauth.get("/api/audit").status_code, 401)

        # Authenticated request succeeds
        r = self.client.get("/api/audit", headers=self.auth_headers)
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn("total", data)
        self.assertIn("items", data)
        self.assertTrue(isinstance(data["items"], list))

    def test_api_key_lifecycle_and_authentication(self):
        """Epic P2.2: Tests API key creation, authentication, listing, and revocation."""
        # 1. Create API key
        r_create = self.client.post(
            "/api/auth/api-keys",
            json={"name": "CI Deployment Key"},
            headers=self.auth_headers
        )
        self.assertEqual(r_create.status_code, 200)
        key_data = r_create.json()
        key_id = key_data["id"]
        raw_key = key_data["api_key"]
        self.assertTrue(raw_key.startswith("dg_live_"))

        # 2. Authenticate using Bearer dg_live_...
        api_client = TestClient(app)
        r_auth_bearer = api_client.get("/api/jobs", headers={"Authorization": f"Bearer {raw_key}"})
        self.assertEqual(r_auth_bearer.status_code, 200)

        # 3. Authenticate using X-API-Key header
        r_auth_header = api_client.get("/api/jobs", headers={"X-API-Key": raw_key})
        self.assertEqual(r_auth_header.status_code, 200)

        # 4. List keys
        r_list = self.client.get("/api/auth/api-keys", headers=self.auth_headers)
        self.assertEqual(r_list.status_code, 200)
        items = r_list.json()["items"]
        self.assertTrue(any(k["id"] == key_id for k in items))

        # 5. Revoke key
        r_revoke = self.client.delete(f"/api/auth/api-keys/{key_id}", headers=self.auth_headers)
        self.assertEqual(r_revoke.status_code, 200)

        # 6. Request with revoked key must fail with 401
        r_revoked_fail = api_client.get("/api/jobs", headers={"X-API-Key": raw_key})
        self.assertEqual(r_revoked_fail.status_code, 401)

    def test_workspaces_lifecycle(self):
        """Epic P1.1: Tests multi-tenant workspace listing and creation."""
        # 1. Listing auto-creates personal workspace
        r_list = self.client.get("/api/workspaces", headers=self.auth_headers)
        self.assertEqual(r_list.status_code, 200)
        items = r_list.json()["items"]
        self.assertTrue(len(items) >= 1)
        self.assertTrue(any(w["is_owner"] for w in items))

        # 2. Create team workspace
        r_create = self.client.post(
            "/api/workspaces",
            json={"name": f"Analytics Team {uuid.uuid4().hex[:6]}"},
            headers=self.auth_headers
        )
        self.assertEqual(r_create.status_code, 200)
        new_ws = r_create.json()
        self.assertIn("id", new_ws)
        self.assertIn("slug", new_ws)

    def test_webhooks_lifecycle(self):
        """Epic P3.2: Tests webhook creation, listing, signature ping, and deletion."""
        # 1. Create webhook
        r_create = self.client.post(
            "/api/webhooks",
            json={"url": "https://example.com/webhook-receiver", "events": "job.completed,export.ready"},
            headers=self.auth_headers
        )
        self.assertEqual(r_create.status_code, 200)
        hook_data = r_create.json()
        hook_id = hook_data["id"]
        self.assertTrue(hook_data["secret"].startswith("whsec_"))

        # 2. List webhooks
        r_list = self.client.get("/api/webhooks", headers=self.auth_headers)
        self.assertEqual(r_list.status_code, 200)
        hooks = r_list.json()["items"]
        self.assertTrue(any(h["id"] == hook_id for h in hooks))

        # 3. Test webhook ping
        r_test = self.client.post(f"/api/webhooks/{hook_id}/test", headers=self.auth_headers)
        self.assertEqual(r_test.status_code, 200)
        self.assertIn("signature", r_test.json())

        # 4. Delete webhook
        r_del = self.client.delete(f"/api/webhooks/{hook_id}", headers=self.auth_headers)
        self.assertEqual(r_del.status_code, 200)

    def test_export_artifacts_and_signed_download(self):
        """Epic P1.3: Tests object storage export generation, artifact listing, and public signed download."""
        # 1. Generate export artifact
        r_gen = self.client.post(
            "/api/export/generate",
            json={"format": "csv", "min_stars": 0},
            headers=self.auth_headers
        )
        self.assertEqual(r_gen.status_code, 200)
        artifact = r_gen.json()
        download_token = artifact["download_token"]
        download_url = artifact["download_url"]
        self.assertIsNotNone(download_token)
        self.assertIn(download_token, download_url)

        # 2. List artifacts
        r_list = self.client.get("/api/export/artifacts", headers=self.auth_headers)
        self.assertEqual(r_list.status_code, 200)
        items = r_list.json()["items"]
        self.assertTrue(any(a["download_url"] == download_url for a in items))

        # 3. Public download via signed token (no auth headers required)
        public_client = TestClient(app)
        r_down = public_client.get(f"/api/export/download/{download_token}")
        self.assertEqual(r_down.status_code, 200)
        self.assertIn("attachment;", r_down.headers.get("content-disposition", ""))
        self.assertIn("Organization", r_down.text)

    def test_token_pool_endpoints(self):
        """Epic P2.1: Tests token pool summary and addition."""
        # List tokens
        r_list = self.client.get("/api/tokens", headers=self.auth_headers)
        self.assertEqual(r_list.status_code, 200)
        data = r_list.json()
        self.assertIn("active_tokens_count", data)

        # Add dummy token
        r_add = self.client.post(
            "/api/tokens/add",
            json={"token": "ghp_mocktesttoken1234567890abcdefghijklmn"},
            headers=self.auth_headers
        )
        self.assertEqual(r_add.status_code, 200)
        self.assertIn("token_masked", r_add.json())

    def test_saved_searches_lifecycle(self):
        """Epic P3.2: Tests saved search creation, listing, and deletion."""
        # 1. Create saved search
        payload = {
            "name": "High Star Python Repos",
            "query_params": {"language": "Python", "min_stars": 500},
            "notify_on_new": True
        }
        r_create = self.client.post("/api/saved-searches", json=payload, headers=self.auth_headers)
        self.assertEqual(r_create.status_code, 200)
        search_data = r_create.json()
        search_id = search_data["id"]
        self.assertEqual(search_data["name"], "High Star Python Repos")
        self.assertTrue(search_data["notify_on_new"])

        # 2. List saved searches
        r_list = self.client.get("/api/saved-searches", headers=self.auth_headers)
        self.assertEqual(r_list.status_code, 200)
        items = r_list.json()["items"]
        self.assertTrue(any(s["id"] == search_id for s in items))

        # 3. Delete saved search
        r_del = self.client.delete(f"/api/saved-searches/{search_id}", headers=self.auth_headers)
        self.assertEqual(r_del.status_code, 200)

        # 4. Confirm deleted
        r_list2 = self.client.get("/api/saved-searches", headers=self.auth_headers)
        self.assertFalse(any(s["id"] == search_id for s in r_list2.json()["items"]))

    def test_billing_checkout_and_webhook(self):
        """Epic P3.1: Tests Stripe billing checkout simulation and webhook event dispatch."""
        # 1. Checkout upgrade to pro
        r_checkout = self.client.post(
            "/api/billing/checkout",
            json={"plan": "pro"},
            headers=self.auth_headers
        )
        self.assertEqual(r_checkout.status_code, 200)
        self.assertEqual(r_checkout.json()["plan"], "pro")

        # Verify user plan is now pro
        r_profile = self.client.get("/api/auth/me", headers=self.auth_headers)
        self.assertEqual(r_profile.json()["plan"], "pro")
        self.assertEqual(r_profile.json()["monthly_crawls_limit"], 2000)

        # 2. Test Stripe Webhook: Subscription cancellation downgrades to free
        webhook_payload = {
            "type": "customer.subscription.deleted",
            "data": {
                "object": {
                    "customer_email": self.email
                }
            }
        }
        r_hook = self.client.post("/api/billing/webhook", json=webhook_payload)
        self.assertEqual(r_hook.status_code, 200)

        # Verify user plan returned to free
        r_profile2 = self.client.get("/api/auth/me", headers=self.auth_headers)
        self.assertEqual(r_profile2.json()["plan"], "free")
        self.assertEqual(r_profile2.json()["monthly_crawls_limit"], 50)

    def test_rag_json_export_endpoints(self):
        """Epic P3.2: Tests RAG JSON vector chunks direct stream and artifact generation."""
        # 1. Direct stream
        r_stream = self.client.get("/api/export?format=rag_json", headers=self.auth_headers)
        self.assertEqual(r_stream.status_code, 200)
        self.assertEqual(r_stream.headers.get("content-type"), "application/json")

        # 2. Generate artifact
        r_gen = self.client.post(
            "/api/export/generate",
            json={"format": "rag_json"},
            headers=self.auth_headers
        )
        self.assertEqual(r_gen.status_code, 200)
        data = r_gen.json()
        self.assertEqual(data["format"], "rag_json")
        self.assertTrue(data["filename"].endswith(".rag.json"))

    def test_github_app_flow(self):
        """Epic P2.1: Tests GitHub App installation URL and callback flow."""
        # 1. Fetch installation URL
        r_url = self.client.get("/api/github/app/install-url", headers=self.auth_headers)
        self.assertEqual(r_url.status_code, 200)
        self.assertIn("install_url", r_url.json())
        self.assertIn("github.com/apps/", r_url.json()["install_url"])

        # 2. Callback with installation ID
        r_cb = self.client.get(
            "/api/github/app/callback?installation_id=gh_inst_987654",
            headers=self.auth_headers
        )
        self.assertEqual(r_cb.status_code, 200)
        self.assertEqual(r_cb.json()["status"], "success")
        self.assertEqual(r_cb.json()["installation_id"], "gh_inst_987654")

    def test_repository_summary_paid_flow(self):
        """Epic P3.2: Tests AI technical summary generation requiring paid plan."""
        # Create a test repo
        from datagit.storage.models import Repository
        db = SessionLocal()
        r_suffix = uuid.uuid4().hex[:8]
        repo_name = f"sumtest_{r_suffix}"
        repo_full_name = f"testorg/{repo_name}"
        repo = Repository(
            owner="testorg",
            name=repo_name,
            full_name=repo_full_name,
            url=f"https://github.com/{repo_full_name}",
            stars=150,
            language="Python",
            description="High-performance data pipeline for machine learning."
        )
        db.add(repo)
        db.commit()
        db.refresh(repo)
        repo_id = repo.id
        db.close()

        # 1. Free user should receive 403 Forbidden
        r_free = self.client.get(f"/api/repositories/{repo_id}/summary", headers=self.auth_headers)
        self.assertEqual(r_free.status_code, 403)
        self.assertIn("Pro or Enterprise", r_free.json()["detail"])

        # 2. Upgrade to Pro
        self.client.post("/api/billing/checkout", json={"plan": "pro"}, headers=self.auth_headers)

        # 3. Pro user should receive 200 with generated summary
        r_pro = self.client.get(f"/api/repositories/{repo_id}/summary", headers=self.auth_headers)
        self.assertEqual(r_pro.status_code, 200)
        data = r_pro.json()
        self.assertIn("overview", data)
        self.assertIn("tech_stack", data)
        self.assertIn("activity_level", data)

    def test_feature_flags_admin_flow(self):
        """Epic P3.3: Tests crawler feature flags listing and toggling."""
        # 1. List flags
        r_list = self.client.get("/api/admin/feature-flags", headers=self.auth_headers)
        self.assertEqual(r_list.status_code, 200)
        flags = r_list.json()
        self.assertTrue(len(flags) >= 1)

        # 2. Toggle a flag
        r_toggle = self.client.post(
            "/api/admin/feature-flags",
            json={"name": "aggressive_pacing", "is_enabled": True},
            headers=self.auth_headers
        )
        self.assertEqual(r_toggle.status_code, 200)
        self.assertTrue(r_toggle.json()["is_enabled"])

    def test_slo_telemetry_flow(self):
        """Epic P3.3: Tests real-time Service Level Objectives (SLO) telemetry endpoint."""
        r_slo = self.client.get("/api/admin/slos", headers=self.auth_headers)
        self.assertEqual(r_slo.status_code, 200)
        data = r_slo.json()
        self.assertEqual(data["status"], "healthy")
        self.assertIn("targets", data)
        self.assertIn("current", data)
        self.assertIn("error_budget_remaining", data)
        self.assertLessEqual(data["current"]["crawl_start_latency_p95_seconds"], 5.0)

if __name__ == "__main__":
    unittest.main()
