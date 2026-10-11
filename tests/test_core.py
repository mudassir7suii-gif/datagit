import unittest
import time
from datagit.storage.database import init_db, SessionLocal
from datagit.storage.models import Repository, CrawlJob, User
from datagit.search.engine import SearchEngine
from datagit.api.auth import hash_password, verify_password
from datagit.core.token_manager import TokenManager, TokenStatus
from datagit.storage.exporters import DataExporter
from datagit.cli.main import _safe_int, _extract_owner_from_url

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

    def test_repository_search(self):
        res = SearchEngine.query_repositories(self.db, limit=10)
        self.assertIn("items", res)
        self.assertIn("total", res)

    def test_token_manager_lifecycle_and_rotation(self):
        tm = TokenManager(["token_alpha", "token_beta"])
        self.assertEqual(len(tm.tokens), 2)

        # Ignores empty or blank tokens
        tm.add_token("")
        tm.add_token("   ")
        tm.add_token(None)
        self.assertEqual(len(tm.tokens), 2)

        # Acquires token with highest remaining
        chosen = tm.acquire_token()
        self.assertIn(chosen.token, ("token_alpha", "token_beta"))

        # Case-insensitive header parsing
        tm.update_limits("token_alpha", {
            "X-RateLimit-Limit": "5000",
            "x-ratelimit-remaining": "4500",
            "X-RATELIMIT-RESET": str(time.time() + 1800)
        })
        alpha = next(t for t in tm.tokens if t.token == "token_alpha")
        self.assertEqual(alpha.remaining, 4500)
        self.assertEqual(alpha.limit, 5000)

        # Advances reset_timestamp when period passes
        alpha.reset_timestamp = time.time() - 10
        alpha.remaining = 0
        self.assertFalse(alpha.is_exhausted)
        self.assertEqual(alpha.remaining, 5000)
        self.assertGreater(alpha.reset_timestamp, time.time())

    def test_data_exporter_safe_path(self):
        sample = [{"owner": "test", "name": "repo1", "stars": 42}]
        # Path traversal and invalid chars sanitized
        csv_path = DataExporter.to_csv(sample, "../../evil/test:export")
        self.assertTrue(csv_path.exists())
        self.assertNotIn("..", csv_path.name)
        self.assertNotIn(":", csv_path.name)
        if csv_path.exists():
            csv_path.unlink()

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

if __name__ == "__main__":
    unittest.main()
