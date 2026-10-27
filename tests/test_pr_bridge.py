import unittest

from repoguardian.controller import Refused, parse_intent
from repoguardian.pr_bridge import validate, submit, PrRefused

OWNER = "mhatipog"
FORK = "mhatipog/terraform-azurerm-avm-res-datafactory-factory"
UPSTREAM = "Azure/terraform-azurerm-avm-res-datafactory-factory"
SHA = "a" * 40
REQUEST = {
    "version": 1,
    "action": "open_pr",
    "fork": FORK,
    "upstream": UPSTREAM,
    "head": "fix/private-endpoint-default-names",
    "base": "main",
    "expected_head_sha": SHA,
    "title": "Fix duplicate generated private endpoint names",
    "body": "Reproduction and verified safeguards for Azure naming.",
    "acknowledge_public_exposure": True,
}


def fake_response(method, path, payload=None, existing=False, mismatch=False):
    if method == "GET":
        if path == "/repos/" + FORK:
            return {"full_name": FORK, "fork": True, "private": False,
                    "parent": {"full_name": UPSTREAM}}
        if path == "/repos/" + UPSTREAM:
            return {"full_name": UPSTREAM, "private": False, "archived": False}
        if path == "/repos/" + FORK + "/git/ref/heads/fix/private-endpoint-default-names":
            return {"object": {"sha": SHA if not mismatch else "b" * 40}}
        if path == "/repos/" + UPSTREAM + "/git/ref/heads/main":
            return {"object": {"sha": "c" * 40}}
        if path.startswith("/repos/" + UPSTREAM + "/pulls?"):
            return [{"number": 15}] if existing else []
        if path == "/repos/" + UPSTREAM + "/pulls/15":
            return {"number": 15, "state": "open",
                    "head": {"sha": SHA, "repo": {"full_name": FORK}},
                    "base": {"ref": "main", "repo": {"full_name": UPSTREAM}},
                    "user": {"login": OWNER},
                    "html_url": "https://github.com/" + UPSTREAM + "/pull/15"}
    if method == "POST" and path == "/repos/" + UPSTREAM + "/pulls":
        assert payload["head"] == "mhatipog:fix/private-endpoint-default-names"
        assert payload["maintainer_can_modify"] is True
        return {"number": 15}
    raise AssertionError((method, path, payload))


class PRBridgeTests(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(validate(REQUEST, OWNER), REQUEST)

    def test_controller_parses_action(self):
        import json
        self.assertEqual(parse_intent(json.dumps(REQUEST)), REQUEST)

    def test_reject_unexpected_field(self):
        with self.assertRaises(PrRefused):
            validate({**REQUEST, "shell": "uname -a"}, OWNER)

    def test_reject_other_fork(self):
        with self.assertRaises(PrRefused):
            validate({**REQUEST, "fork": "someone/fork"}, OWNER)

    def test_requires_public_exposure_acknowledgement(self):
        with self.assertRaises(PrRefused):
            validate({**REQUEST, "acknowledge_public_exposure": False}, OWNER)

    def test_reject_bad_sha(self):
        with self.assertRaises(PrRefused):
            validate({**REQUEST, "expected_head_sha": "bad"}, OWNER)

    def test_reject_api_path_injections(self):
        for bad in ["../../other", "foo%2fbar", "foo..bar",
                    "foo/../bar", "https://evil", "fix//bad", "foo@{bad}"]:
            with self.subTest(bad=bad), self.assertRaises(PrRefused):
                validate({**REQUEST, "head": bad}, OWNER)

    def test_verify_created_pr(self):
        calls = []
        def api(*args):
            calls.append(args)
            return fake_response(*args)
        self.assertIn("/pull/15", submit(REQUEST, api, OWNER))
        self.assertEqual(1, sum(v[0] == "POST" for v in calls))

    def test_existing_pr_is_idempotent(self):
        calls = []
        def api(*args):
            calls.append(args)
            return fake_response(*args, existing=True)
        self.assertIn("Verified upstream PR", submit(REQUEST, api, OWNER))
        self.assertFalse(any(v[0] == "POST" for v in calls))

    def test_sha_mismatch_refuses_before_write(self):
        calls = []
        def api(*args):
            calls.append(args)
            return fake_response(*args, mismatch=True)
        with self.assertRaises(PrRefused):
            submit(REQUEST, api, OWNER)
        self.assertFalse(any(v[0] == "POST" for v in calls))

    def test_fork_parent_mismatch_refuses_before_write(self):
        calls = []
        def api(method, path, payload=None):
            calls.append((method, path))
            if path == "/repos/" + FORK:
                return {"full_name": FORK, "fork": True, "private": False,
                        "parent": {"full_name": "other/repo"}}
            return fake_response(method, path, payload)
        with self.assertRaises(PrRefused):
            submit(REQUEST, api, OWNER)
        self.assertEqual([("GET", "/repos/" + FORK)], calls)


if __name__ == "__main__":
    unittest.main()
