"""Owner-only upstream PR body edits cannot overwrite unexpected changes."""
import unittest

from repoguardian.controller import Refused, parse_intent
from repoguardian.pr_bridge import PrRefused, update_body

FORK = "mhatipog/certbot"
UPSTREAM = "certbot/certbot"
NUMBER = 10817
SHA = "a" * 40
OLD = "## Original\n\nExisting public PR description."
NEW = "## Improved\n\nExisting public PR description."
INTENT = {
    "version": 1, "action": "update_pr_body", "fork": FORK,
    "upstream": UPSTREAM, "pr_number": NUMBER,
    "expected_head_sha": SHA, "expected_body": OLD, "body": NEW,
    "acknowledge_public_exposure": True,
}


class UpdateBodyTests(unittest.TestCase):
    def test_input_validation(self):
        import json
        self.assertEqual(parse_intent(json.dumps(INTENT)), INTENT)
        for patch in (
            {"fork": "someone/certbot"},
            {"pr_number": True},
            {"expected_head_sha": "bad"},
            {"acknowledge_public_exposure": False},
            {"unexpected_field": True},
        ):
            with self.subTest(patch=patch), self.assertRaises(Refused):
                parse_intent(json.dumps({**INTENT, **patch}))

    def fake_api(self, calls, current=OLD, actor="mhatipog", head=SHA):
        def api(method, endpoint, payload=None):
            calls.append((method, endpoint, payload))
            if endpoint == "/user":
                return {"login": actor, "type": "User"}
            if endpoint == "/repos/" + FORK:
                return {"full_name": FORK, "fork": True, "private": False,
                        "parent": {"full_name": UPSTREAM}}
            if endpoint == "/repos/" + UPSTREAM:
                return {"full_name": UPSTREAM, "private": False, "archived": False}
            if endpoint == "/repos/" + UPSTREAM + "/pulls/" + str(NUMBER):
                if method == "PATCH":
                    self.assertEqual(payload, {"body": NEW})
                    return {}
                return {"number": NUMBER, "state": "open", "draft": False,
                        "head": {"sha": head, "repo": {"full_name": FORK}},
                        "base": {"repo": {"full_name": UPSTREAM}},
                        "user": {"login": "mhatipog"},
                        "html_url": "https://github.com/" + UPSTREAM + "/pull/" + str(NUMBER),
                        "body": NEW if any(c[0] == "PATCH" for c in calls) else current}
            raise AssertionError((method, endpoint, payload))
        return api

    def test_updates_exact_pr_body_and_verifies(self):
        calls = []
        self.assertIn("Updated and verified", update_body(INTENT, self.fake_api(calls), "mhatipog"))
        self.assertEqual(1, sum(c[0] == "PATCH" for c in calls))

    def test_stale_body_and_head_are_refused_without_write(self):
        for current, head in (("Changed by someone else", SHA), (OLD, "b" * 40)):
            calls = []
            with self.assertRaises(PrRefused):
                update_body(INTENT, self.fake_api(calls, current=current, head=head), "mhatipog")
            self.assertFalse(any(c[0] == "PATCH" for c in calls))

    def test_wrong_actor_refused_without_write(self):
        calls = []
        with self.assertRaises(PrRefused):
            update_body(INTENT, self.fake_api(calls, actor="another-user"), "mhatipog")
        self.assertEqual([("GET", "/user", None)], calls)


if __name__ == "__main__":
    unittest.main()
