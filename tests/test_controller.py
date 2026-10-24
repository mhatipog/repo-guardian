import datetime as dt
import json
import unittest
from unittest.mock import patch
from repoguardian.controller import Refused, digest, parse_intent, review_status, safe_repo, Control


class GuardianTests(unittest.TestCase):
    def parse(self, value):
        return parse_intent(json.dumps(value))

    def test_create_private(self):
        v = self.parse({'version': 1, 'action': 'create_repo', 'name': 'test-42', 'visibility': 'private'})
        self.assertEqual(v['name'], 'test-42')

    def test_reject_untrusted_fields(self):
        with self.assertRaises(Refused):
            self.parse({'version': 1, 'action': 'create_repo', 'name': 'test',
                        'visibility': 'private', 'shell': 'curl bad'})

    def test_visibility_identity_required(self):
        with self.assertRaises(Refused):
            self.parse({'version': 1, 'action': 'visibility', 'repo': 'mhatipog/example',
                        'visibility': 'public', 'expected_visibility': 'private'})

    def test_prevent_other_owner(self):
        with self.assertRaises(Refused):
            self.parse({'version': 1, 'action': 'visibility', 'repo': 'someone/example',
                        'visibility': 'public', 'expected_visibility': 'private',
                        'expected_repo_id': 123})

    def test_reject_path_or_api_injection(self):
        for r in ['x/y/z', '../repo', 'user/../admin', 'user/%2F',
                  'https://example.com/x']:
            with self.assertRaises(Refused):
                safe_repo(r)

    def test_hash_independent_of_json_key_order(self):
        self.assertEqual(digest({'name': 'x', 'action': 'fork'}),
                         digest({'action': 'fork', 'name': 'x'}))

    def test_missing_deadline(self):
        now = dt.datetime(2026, 11, 10, 10, tzinfo=dt.timezone.utc)
        intent = {'version': 1, 'action': 'visibility', 'repo': 'mhatipog/test',
                  'visibility': 'public', 'expected_repo_id': 1,
                  'expected_visibility': 'private', 'at': '2026-11-10T09:00:00Z'}
        self.assertEqual(review_status(intent, now), 'missed')
        intent['visibility'] = 'private'
        self.assertEqual(review_status(intent, now), 'ready')

    def test_future(self):
        now = dt.datetime(2026, 11, 10, 7, tzinfo=dt.timezone.utc)
        self.assertEqual(review_status({
            'at': '2026-11-10T09:00:00Z', 'action': 'visibility',
            'visibility': 'public'}, now), 'waiting')

    def test_status_request(self):
        self.assertEqual(self.parse({"version": 1, "action": "status"})["action"], "status")

    def test_publication_requires_explicit_risk_acknowledgement(self):
        value = {"version": 1, "action": "visibility", "repo": "mhatipog/demo",
                 "visibility": "public", "expected_repo_id": 123, "expected_visibility": "private"}
        with self.assertRaises(Refused):
            self.parse(value)
        value["acknowledge_public_exposure"] = True
        self.assertEqual(self.parse(value)["visibility"], "public")

    def test_add_topics(self):
        v = self.parse({"version": 1, "action": "topics",
                        "repo": "mhatipog/repo-guardian",
                        "names": ["chatgpt", "github-automation"]})
        self.assertEqual(v["names"], ["chatgpt", "github-automation"])

    def test_reject_invalid_topics(self):
        for bad in [["Private"], ["trailing-"], ["a" * 51], ["hello/world"],
                    ["dupe", "dupe"], ["x"] * 21]:
            with self.assertRaises(Refused):
                self.parse({"version": 1, "action": "topics",
                            "repo": "mhatipog/repo-guardian",
                            "names": bad})

    def test_private_copy(self):
        v = self.parse({"version": 1, "action": "private_copy",
                        "source": "octocat/Hello-World", "name": "rg-smoke-private"})
        self.assertEqual(v["source"], "octocat/Hello-World")

    def test_no_arbitrary_shell(self):
        with self.assertRaises(Refused):
            self.parse({"version": 1, "action": "private_copy",
                        "source": "octocat/Hello-World",
                        "name": "rg-smoke-private", "run": "rm -rf /"})

    def test_topics_execute_merges_and_verifies(self):
        c = Control("issue-token", "admin-token")
        records = []
        def fake_admin(method, endpoint, payload=None):
            records.append((method, endpoint, payload))
            if endpoint == "/repos/mhatipog/repo-guardian":
                return {"id": 4, "fork": False, "private": False}
            if endpoint.endswith("/topics"):
                if method == "PUT":
                    return {"names": payload["names"]}
                if sum(1 for record in records if record[0] == "GET" and record[1].endswith("/topics")) == 1:
                    return {"names": ["python"]}
                return {"names": ["chatgpt", "github-automation", "python"]}
            raise AssertionError(endpoint)
        with patch.object(c, "admin", side_effect=fake_admin):
            message = c.execute({"action":"topics","repo":"mhatipog/repo-guardian",
                                 "names":["chatgpt", "github-automation"],"mode":"add"})
        self.assertIn("chatgpt", message)
        self.assertIn(("PUT", "/repos/mhatipog/repo-guardian/topics",
                       {"names":["chatgpt", "github-automation", "python"]}), records)

    def test_private_copy_creates_nonfork_private_and_checks_sha(self):
        c = Control("issue-token", "admin-token")
        seen = []
        def fake_admin(method, endpoint, payload=None):
            seen.append((method, endpoint, payload))
            if endpoint == "/repos/octocat/Hello-World":
                return {"size": 2, "private": False, "default_branch": "master"}
            if endpoint == "/repos/mhatipog/fixture-private" and method == "GET":
                if any(v[0]=="POST" and v[1]=="/user/repos" for v in seen):
                    return {"id": 321, "visibility": "private", "fork": False}
                raise Refused("GitHub returned HTTP 404: Not Found")
            if endpoint == "/user/repos":
                return {"id": 321, "full_name": "mhatipog/fixture-private", "private": True}
            if endpoint in ("/repos/octocat/Hello-World/git/ref/heads/master",
                            "/repos/mhatipog/fixture-private/git/ref/heads/master"):
                return {"object":{"sha":"abc123"}}
            raise AssertionError((method,endpoint,payload))
        with patch.object(c, "admin", side_effect=fake_admin), patch(
                "repoguardian.controller.subprocess.run") as proc:
            proc.return_value.returncode = 0
            proc.return_value.stdout = ""
            proc.return_value.stderr = ""
            result = c.execute({"action":"private_copy","source":"octocat/Hello-World",
                                "name":"fixture-private"})
        self.assertIn("verified", result)
        self.assertEqual(proc.call_count, 2)
        self.assertTrue(any(x[0]=="POST" and x[1]=="/user/repos" and x[2]["private"] for x in seen))

    def test_invalid_date(self):
        with self.assertRaises(Refused):
            self.parse({'version': 1, 'action': 'create_repo', 'name': 'test',
                        'visibility': 'private', 'at': '2026-13-10T09:00:00Z'})


if __name__ == '__main__':
    unittest.main()
