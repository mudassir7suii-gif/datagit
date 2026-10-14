import unittest
import json
from unittest.mock import patch, MagicMock
from datagit.sdk import DataGitClient, DataGitAPIError

def make_mock_cm(data: dict):
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(data).encode("utf-8")
    mock_resp.status = 200
    mock_cm = MagicMock()
    mock_cm.__enter__.return_value = mock_resp
    return mock_cm

class TestPythonSDK(unittest.TestCase):
    def setUp(self):
        self.client = DataGitClient(api_key="dg_live_mockkey12345678", base_url="http://mock-api.datagit.dev")

    @patch("urllib.request.urlopen")
    def test_jobs_create_and_list(self, mock_urlopen):
        mock_urlopen.side_effect = [
            make_mock_cm({"job_id": 42, "status": "queued"}),
            make_mock_cm({"items": [{"id": 42, "target": "facebook/react"}]})
        ]

        res = self.client.jobs.create(target="facebook/react", depth="metadata")
        self.assertEqual(res.get("job_id"), 42)

        items = self.client.jobs.list()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["target"], "facebook/react")

    @patch("urllib.request.urlopen")
    def test_repositories_search(self, mock_urlopen):
        mock_urlopen.return_value = make_mock_cm({"total": 1, "items": [{"id": 1, "name": "react", "stars": 200000}]})

        results = self.client.repositories.search(keyword="react", min_stars=1000)
        self.assertEqual(results["total"], 1)
        self.assertEqual(results["items"][0]["name"], "react")

    @patch("urllib.request.urlopen")
    def test_webhooks_create_and_list(self, mock_urlopen):
        mock_urlopen.return_value = make_mock_cm({"id": 10, "url": "https://example.com/wh", "secret": "whsec_123"})

        hook = self.client.webhooks.create(url="https://example.com/wh", events=["job.completed"])
        self.assertEqual(hook["id"], 10)
        self.assertEqual(hook["secret"], "whsec_123")

    @patch("urllib.request.urlopen")
    def test_exports_generate_artifact(self, mock_urlopen):
        mock_urlopen.return_value = make_mock_cm({"artifact_id": 5, "download_token": "tok123", "download_url": "/api/export/download/tok123"})

        res = self.client.exports.create_artifact(format="csv", search="ai")
        self.assertEqual(res["artifact_id"], 5)
        self.assertEqual(res["download_token"], "tok123")

    @patch("urllib.request.urlopen")
    def test_workspaces_list(self, mock_urlopen):
        mock_urlopen.return_value = make_mock_cm({"items": [{"id": 1, "name": "Personal Workspace"}]})

        workspaces = self.client.workspaces.list()
        self.assertEqual(len(workspaces), 1)
        self.assertEqual(workspaces[0]["name"], "Personal Workspace")

    @patch("urllib.request.urlopen")
    def test_saved_searches(self, mock_urlopen):
        mock_urlopen.side_effect = [
            make_mock_cm({"id": 1, "name": "LLMs", "query_params": {"language": "Python"}}),
            make_mock_cm({"items": [{"id": 1, "name": "LLMs"}]}),
            make_mock_cm({"message": "Saved search deleted successfully."})
        ]

        created = self.client.saved_searches.create(name="LLMs", query_params={"language": "Python"})
        self.assertEqual(created["id"], 1)

        items = self.client.saved_searches.list()
        self.assertEqual(len(items), 1)

        deleted = self.client.saved_searches.delete(1)
        self.assertIn("deleted successfully", deleted["message"])

if __name__ == "__main__":
    unittest.main()
