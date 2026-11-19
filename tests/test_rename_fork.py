"""Safety checks for GitHub public-fork renaming via Repo Guardian."""
import json
import unittest
from unittest.mock import patch

from repoguardian.controller import Control, Refused, parse_intent


class RenamePublicForkTests(unittest.TestCase):
    def setUp(self):
        self.intent = {
            "version": 1, "action": "rename_fork", "repo": "mhatipog/sqlglot",
            "name": "queryport", "expected_repo_id": 1464458837,
            "expected_parent": "tobymao/sqlglot",
            "description": "QueryPort: tested SQL parsing, dialect transpilation and semantic validation",
        }

    def test_valid_request(self):
        self.assertEqual(parse_intent(json.dumps(self.intent)), self.intent)

    def test_reject_invalid_requests(self):
        bad = [
            {"repo": "someone/sqlglot"},
            {"name": "../../escape"},
            {"name": "sqlglot"},
            {"expected_repo_id": True},
            {"expected_parent": "mhatipog/sqlglot"},
            {"description": "a" + chr(10) + "b"},
            {"shell": "curl attacker"},
        ]
        for replacement in bad:
            with self.subTest(replacement=replacement), self.assertRaises(Refused):
                parse_intent(json.dumps({**self.intent, **replacement}))

    def test_rename_checks_existing_fork_and_verifies_result(self):
        control = Control("issue-token", "admin-token")
        calls = []
        def admin(method, path, payload=None):
            calls.append((method, path, payload))
            old = {"id": 1464458837, "full_name": "mhatipog/sqlglot",
                   "fork": True, "private": False, "archived": False,
                   "parent": {"full_name": "tobymao/sqlglot"}}
            if path == "/repos/mhatipog/sqlglot" and method == "GET":
                return old
            if path == "/repos/mhatipog/queryport" and method == "GET":
                if not any(c[0] == "PATCH" for c in calls):
                    raise Refused("GitHub returned HTTP 404: Not Found")
                return {**old, "full_name": "mhatipog/queryport",
                        "description": self.intent["description"]}
            if path == "/repos/mhatipog/sqlglot" and method == "PATCH":
                return {"id": 1464458837}
            raise AssertionError((method, path, payload))
        with patch.object(control, "admin", side_effect=admin):
            self.assertIn("verified public fork", control.execute(self.intent))
        self.assertIn(("PATCH", "/repos/mhatipog/sqlglot", {
            "name": "queryport", "description": self.intent["description"]}), calls)

    def test_refuses_wrong_id_or_parent_before_any_patch(self):
        for change in [{"id": 8}, {"parent": {"full_name": "attacker/repo"}},
                       {"fork": False}, {"private": True}, {"archived": True}]:
            control = Control("issue-token", "admin-token")
            def admin(method, path, payload=None):
                self.assertEqual(method, "GET")
                return {"id": 1464458837, "full_name": "mhatipog/sqlglot",
                        "fork": True, "private": False, "archived": False,
                        "parent": {"full_name": "tobymao/sqlglot"}, **change}
            with self.subTest(change=change), patch.object(control, "admin", side_effect=admin):
                with self.assertRaises(Refused):
                    control.execute(self.intent)

    def test_refuses_existing_destination_without_patch(self):
        control = Control("issue-token", "admin-token")
        def admin(method, path, payload=None):
            self.assertEqual(method, "GET")
            return {"id": 1464458837, "full_name": "mhatipog/sqlglot",
                    "fork": True, "private": False, "archived": False,
                    "parent": {"full_name": "tobymao/sqlglot"}}
        with patch.object(control, "admin", side_effect=admin), self.assertRaises(Refused):
            control.execute(self.intent)


if __name__ == "__main__":
    unittest.main()
