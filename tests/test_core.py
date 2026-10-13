import unittest
import time
import uuid
import os
from unittest.mock import patch, MagicMock
from click.testing import CliRunner
from sqlalchemy.exc import IntegrityError

from datagit.storage.database import init_db, SessionLocal
from datagit.storage.models import Repository, CrawlJob, User, RateLimitState, Commit, Issue
from datagit.search.engine import SearchEngine
from datagit.api.auth import hash_password, verify_password
from datagit.core.token_manager import TokenManager, TokenStatus
from datagit.crawler.github_client import GitHubClient
from datagit.storage.exporters import DataExporter
from datagit.cli.main import cli, _safe_int, _extract_owner_from_url

class TestDataGitCore(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    def setUp(self):
        self.db = SessionLocal()

    def tearDown(self):
        self.db.close()

    def test_password_hashing(self):
        password = "secret_password_123"
        hashed = hash_password(password)
        self.assertNotEqual(password, hashed)
        self.assertTrue(verify_password(password, hashed))
        self.assertFalse(verify_password("wrong_password", hashed))

    def test_search_and_insights(self):
        insights = SearchEngine.get_insights(self.db)
        self.assertIn("total_repositories", insights)
        self.assertIn("top_languages", insights)
        self.assertGreaterEqual(insights["total_repositories"], 0)

    def test_repository_search_and_fts(self):
        res = SearchEngine.query_repositories(self.db, limit=10)
        self.assertIn("items", res)
        self.assertIn("total", res)

        # Keyword FTS test
        fts_res = SearchEngine.query_repositories(self.db, keyword="anthropic", limit=5)
        self.assertIn("items", fts_res)

    def test_token_manager_db_persistence(self):
        """Verifies shared rate-limit state persistence across worker instances per Principle 4."""
        tm1 = TokenManager(["token_worker_test"], sync_live=False)
        self.assertEqual(len(tm1.tokens), 1)

        # Update and persist
        status = tm1.tokens[0]
        status.remaining = 4200
        tm1.persist_to_db(status)

        # Separate worker instance loads persisted state
        tm2 = TokenManager(["token_worker_test"], sync_live=False)
        self.assertEqual(tm2.tokens[0].remaining, 4200)

    def test_token_manager_exhaustion_and_recovery(self):
        """Epic 3: Test rate limit budget exhaustion and automatic recovery upon period reset."""
        unique_token = f"token_exhaust_{uuid.uuid4().hex[:8]}"
        tm = TokenManager([unique_token], sync_live=False)
        t = tm.tokens[0]
        t.remaining = 0
        t.reset_timestamp = time.time() + 3600
        tm.persist_to_db(t)
        self.assertTrue(t.is_exhausted)

        # Acquiring exhausted token raises RuntimeError
        with self.assertRaises(RuntimeError):
            tm.acquire_token()

        # Simulate reset timestamp elapsed
        t.reset_timestamp = time.time() - 1
        tm.persist_to_db(t)
        self.assertFalse(t.is_exhausted)
        chosen = tm.acquire_token()
        self.assertEqual(chosen.remaining, chosen.limit)

    def test_streaming_csv_and_cleanup(self):
        query = self.db.query(Repository).limit(5)
        chunks = list(DataExporter.stream_csv(query, chunk_size=2))
        self.assertGreater(len(chunks), 0)
        self.assertIn("Organization,Name,Full_Name", chunks[0])

        # Retention cleanup function runs without error
        cleaned = DataExporter.cleanup_old_exports(max_age_hours=0)
        self.assertGreaterEqual(cleaned, 0)

    def test_compound_unique_constraints_prevent_duplicates(self):
        """Epic 5: Test that compound unique constraints prevent duplicate commits and issues."""
        repo = self.db.query(Repository).first()
        if not repo:
            repo = Repository(full_name="test/repo", owner="test", name="repo", url="https://github.com/test/repo")
            self.db.add(repo)
            self.db.commit()

        # Add commit with unique sha
        test_sha = uuid.uuid4().hex + uuid.uuid4().hex[:8]
        c1 = Commit(repo_id=repo.id, sha=test_sha, message="Commit 1")
        self.db.add(c1)
        self.db.commit()

        # Attempt to insert identical commit (same repo_id and sha)
        c2 = Commit(repo_id=repo.id, sha=test_sha, message="Duplicate commit")
        self.db.add(c2)
        with self.assertRaises(IntegrityError):
            self.db.commit()
        self.db.rollback()

        # Add issue with unique number
        test_num = int(time.time() * 1000) % 1000000
        i1 = Issue(repo_id=repo.id, github_number=test_num, title="Issue 1")
        self.db.add(i1)
        self.db.commit()

        # Attempt to insert identical issue (same repo_id and github_number)
        i2 = Issue(repo_id=repo.id, github_number=test_issue_num if "test_issue_num" in locals() else test_num, title="Duplicate Issue")
        self.db.add(i2)
        with self.assertRaises(IntegrityError):
            self.db.commit()
        self.db.rollback()

    def test_single_repo_target_detection(self):
        """Epic 4: Test single-repo target (owner/repo) detection in GitHubClient."""
        client = GitHubClient(token_manager=TokenManager(sync_live=False))
        with patch.object(client, "_request", return_value=(200, {"name": "react", "full_name": "facebook/react"}, {})):
            target_type = client.detect_target_type("facebook/react")
            self.assertEqual(target_type, "Repository")

            repos = client.fetch_repositories("facebook/react")
            self.assertEqual(len(repos), 1)
            self.assertEqual(repos[0]["name"], "react")

    def test_cli_commands_with_runner(self):
        """Epic 8: Automated CLI testing with Click CliRunner."""
        runner = CliRunner()

        # Status command
        res_status = runner.invoke(cli, ["status"])
        self.assertEqual(res_status.exit_code, 0)
        self.assertIn("DataGit Status", res_status.output)

        # Search command
        res_search = runner.invoke(cli, ["search", "anthropic", "--limit", "2"])
        self.assertEqual(res_search.exit_code, 0)

        # Export command
        res_export = runner.invoke(cli, ["export", "--format", "json", "--min-stars", "1000", "--filename", "test_runner_export"])
        self.assertEqual(res_export.exit_code, 0)
        if os.path.exists("test_runner_export.json"):
            os.remove("test_runner_export.json")

    def test_cli_safe_int_and_url_parser(self):
        self.assertEqual(_safe_int("14,088"), 14088)
        self.assertEqual(_safe_int(" 10.5 "), 10)
        self.assertEqual(_safe_int(None, 0), 0)
        self.assertEqual(_safe_int("invalid", 5), 5)

        owner, name = _extract_owner_from_url("https://github.com/octocat/Spoon-Knife")
        self.assertEqual(owner, "octocat")
        self.assertEqual(name, "Spoon-Knife")

        owner_slash, name_slash = _extract_owner_from_url("https://github.com/google/guava/")
        self.assertEqual(owner_slash, "google")
        self.assertEqual(name_slash, "guava")

        bad_o, bad_n = _extract_owner_from_url("https://example.com/not/github")
        self.assertIsNone(bad_o)
        self.assertIsNone(bad_n)

    def test_orchestrator_failure_and_rollback(self):
        """Epic 8: Tests orchestrator exception handling, database rollback, and failure recording."""
        from datagit.crawler.orchestrator import CrawlOrchestrator
        job = CrawlJob(target="fake/fail_repo", depth="metadata", status="queued")
        self.db.add(job)
        self.db.commit()
        job_id = job.id

        mock_client = MagicMock()
        mock_client.fetch_repositories.side_effect = RuntimeError("Simulated network failure")
        orch = CrawlOrchestrator(client=mock_client)

        with self.assertRaises(RuntimeError):
            orch.run_job(job_id)

        # Verify job marked as failed and error message stored
        self.db.expire_all()
        failed_job = self.db.query(CrawlJob).filter(CrawlJob.id == job_id).first()
        self.assertEqual(failed_job.status, "failed")
        self.assertIn("Simulated network failure", failed_job.error_message)

    def test_orchestrator_incremental_skip(self):
        """Epic 4: Tests that content_hash skip prevents reprocessing unchanged repositories."""
        from datagit.crawler.orchestrator import CrawlOrchestrator
        unique_repo_name = f"skip-repo-{uuid.uuid4().hex[:8]}"
        full_repo_name = f"test/{unique_repo_name}"
        raw_repo = {
            "name": unique_repo_name,
            "full_name": full_repo_name,
            "stargazers_count": 42,
            "forks_count": 10,
            "pushed_at": "2026-01-01T00:00:00Z"
        }
        mock_client = MagicMock()
        mock_client.fetch_repositories.return_value = [raw_repo]
        mock_client.fetch_commits.return_value = [{"sha": "sha123", "commit": {"message": "init"}}]

        job1 = CrawlJob(target=full_repo_name, depth="commits", status="queued")
        self.db.add(job1)
        self.db.commit()

        orch = CrawlOrchestrator(client=mock_client)
        orch.run_job(job1.id)
        # Should have called fetch_commits once on fresh repo
        self.assertEqual(mock_client.fetch_commits.call_count, 1)

        # Run again with same metadata (content_hash is unchanged)
        job2 = CrawlJob(target=full_repo_name, depth="commits", status="queued")
        self.db.add(job2)
        self.db.commit()

        orch.run_job(job2.id)
        # Content hash unchanged -> fetch_commits should NOT be called again
        self.assertEqual(mock_client.fetch_commits.call_count, 1)

if __name__ == "__main__":
    unittest.main()
