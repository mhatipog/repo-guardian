import json
import os
import unittest
from unittest.mock import patch

from repoguardian import cli
from repoguardian.controller import Refused


class FakeController:
    def __init__(self, *args, **kwargs):
        self.admin_calls = []
        self.requests = []

    def admin(self, method, endpoint, payload=None):
        self.admin_calls.append((method, endpoint))
        return {"id": 222, "full_name": "mhatipog/fixture",
                "visibility": "private", "fork": False,
                "default_branch": "main", "archived": False}

    def execute(self, request):
        self.requests.append(request)
        return "SIMULATED VERIFIED " + request["action"]


class CLITests(unittest.TestCase):
    def test_requires_token(self):
        with patch.dict(os.environ, {"RG_ADMIN_TOKEN": "", "GH_TOKEN": ""}):
            self.assertEqual(cli.main(["inspect", "mhatipog/fixture"]), 2)

    def test_inspect_is_read_only(self):
        ctrl = FakeController()
        with patch.dict(os.environ, {"RG_ADMIN_TOKEN": "test"}), patch.object(
            cli, "Control", return_value=ctrl):
            self.assertEqual(cli.main(["inspect", "mhatipog/fixture"]), 0)
        self.assertEqual(ctrl.admin_calls, [("GET", "/repos/mhatipog/fixture")])
        self.assertEqual(ctrl.requests, [])

    def test_topics_execute(self):
        ctrl = FakeController()
        with patch.dict(os.environ, {"RG_ADMIN_TOKEN": "test"}), patch.object(
            cli, "Control", return_value=ctrl):
            self.assertEqual(cli.main(["topics", "mhatipog/fixture", "chatgpt",
                                       "github-api"]), 0)
        self.assertEqual(ctrl.requests[0]["action"], "topics")

    def test_visibility_uses_actual_repo_identity(self):
        ctrl = FakeController()
        with patch.dict(os.environ, {"RG_ADMIN_TOKEN": "test"}), patch.object(
            cli, "Control", return_value=ctrl):
            self.assertEqual(cli.main(["visibility", "mhatipog/fixture", "public"]), 0)
        self.assertEqual(ctrl.requests[0]["expected_repo_id"], 222)
        self.assertEqual(ctrl.requests[0]["expected_visibility"], "private")

    def test_execute_json_rejects_unknown_fields(self):
        ctrl = FakeController()
        data = json.dumps({"version": 1, "action": "create_repo", "name": "x",
                           "visibility": "private", "shell": "bad"})
        with patch.dict(os.environ, {"RG_ADMIN_TOKEN": "test"}), patch.object(
            cli, "Control", return_value=ctrl):
            self.assertEqual(cli.main(["execute-json", "--request", data]), 1)
        self.assertEqual(ctrl.requests, [])


if __name__ == "__main__":
    unittest.main()
