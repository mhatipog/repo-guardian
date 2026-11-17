"""Narrow public PR reply bridge tests: no external access or tokens."""
import hashlib
import json
import unittest

from repoguardian.comment_bridge import CommentRefused, submit, validate
from repoguardian.controller import Control, Refused, parse_intent

OWNER = "mhatipog"
FORK = "mhatipog/plugins"
UPSTREAM = "opnsense/plugins"
SHA = "0cfb426bb0014e589df895a7c8610a1296c06695"
ORIGINAL = "We could also just double the timeout here."
BODY = ("Good point. Doesn't configctl also have its own 120-second socket timeout? "
        "Would increasing the PHP timeout address that as well, particularly for scheduled updates?")
VALUE = {
    "version": 1, "action": "comment_pr", "fork": FORK, "upstream": UPSTREAM,
    "pr_number": 5936, "expected_head_sha": SHA, "reply_to_comment_id": 6956966805,
    "expected_comment_author": "AdSchellevis",
    "expected_comment_sha256": hashlib.sha256(ORIGINAL.encode()).hexdigest(),
    "body": BODY, "acknowledge_public_exposure": True,
}
PREFIX = "/repos/" + UPSTREAM
ISSUE_URL = "https://api.github.com" + PREFIX + "/issues/5936"


def fake_api(method, path, data=None, *, actor=OWNER, parent=UPSTREAM, sha=SHA,
             prior=ORIGINAL, pr_author=OWNER, pr_state="open", existing=False,
             wrong_comment_pr=False, post_fail=False):
    if method == "GET":
        if path == "/user":
            return {"login": actor, "type": "User"}
        if path == "/repos/" + FORK:
            return {"fork": True, "private": False, "archived": False,
                    "full_name": FORK, "parent": {"full_name": parent}}
        if path == PREFIX:
            return {"full_name": UPSTREAM, "private": False, "archived": False}
        if path == PREFIX + "/pulls/5936":
            return {"number": 5936, "state": pr_state, "draft": False,
                    "user": {"login": pr_author},
                    "head": {"sha": sha, "repo": {"full_name": FORK}},
                    "base": {"repo": {"full_name": UPSTREAM}},
                    "html_url": "https://github.com/" + UPSTREAM + "/pull/5936"}
        if path == PREFIX + "/issues/comments/6956966805":
            return {"id": 6956966805, "user": {"login": "AdSchellevis"},
                    "body": prior, "issue_url": ISSUE_URL if not wrong_comment_pr else ISSUE_URL+"x"}
        if path == PREFIX + "/issues/5936/comments?per_page=100&page=1":
            return ([{"id": 70, "user": {"login": OWNER}, "body": BODY}] if existing else
                    [{"id": 6956966805, "user": {"login": "AdSchellevis"}, "body": ORIGINAL}])
        if path == PREFIX + "/issues/comments/713":
            return {"id": 713, "body": BODY, "user": {"login": OWNER}, "issue_url": ISSUE_URL}
    if method == "POST" and path == PREFIX + "/issues/5936/comments":
        assert not post_fail
        assert data == {"body": BODY}
        return {"id": 713}
    raise AssertionError((method, path, data))


class CommentBridgeTests(unittest.TestCase):
    def test_parse_and_validate(self):
        self.assertEqual(validate(VALUE, OWNER), VALUE)
        self.assertEqual(parse_intent(json.dumps(VALUE)), VALUE)

    def test_reject_unexpected_fields(self):
        for bad in ({"at": "2026-11-17T19:00:00Z"}, {"shell": "echo hi"}):
            with self.subTest(bad=bad), self.assertRaises(Refused):
                parse_intent(json.dumps({**VALUE, **bad}))

    def test_reject_missing_or_bad_acknowledgement(self):
        for bad in (None, False, 1):
            with self.subTest(bad=bad), self.assertRaises(CommentRefused):
                validate({**VALUE, "acknowledge_public_exposure": bad}, OWNER)

    def test_reject_invalid_values(self):
        cases = [
            {"pr_number": True}, {"reply_to_comment_id": False},
            {"pr_number": 0}, {"reply_to_comment_id": 0},
            {"fork": "other/plugins"}, {"upstream": "../core"},
            {"expected_head_sha": "a"}, {"expected_comment_sha256": "oops"},
            {"expected_comment_author": OWNER}, {"body": "tiny"},
            {"body": BODY + "\x00"}, {"body": BODY + "\x7f"},
            {"body": " x" + BODY + " "},
        ]
        for bad in cases:
            with self.subTest(bad=bad), self.assertRaises(CommentRefused):
                validate({**VALUE, **bad}, OWNER)

    def test_success_and_post_write_verification(self):
        calls = []
        def admin(*args):
            calls.append(args)
            return fake_api(*args)
        response = submit(VALUE, admin, OWNER)
        self.assertIn("Verified owner-authored", response)
        self.assertNotIn("github.com", response)
        self.assertEqual([("POST", PREFIX + "/issues/5936/comments", {"body": BODY})],
                         [c for c in calls if c[0] == "POST"])

    def test_no_duplicate_on_retry(self):
        calls = []
        def admin(*args):
            calls.append(args)
            return fake_api(*args, existing=True)
        response = submit(VALUE, admin, OWNER)
        self.assertIn("already exists", response)
        self.assertFalse(any(c[0] == "POST" for c in calls))

    def test_wrong_identity_fails_before_write(self):
        for option in ({"actor": "somebot"}, {"parent": "another/repo"},
                       {"sha": "b"*40}, {"pr_author": "not-owner"},
                       {"pr_state": "closed"}, {"wrong_comment_pr": True},
                       {"prior": "Maintainer edited their message"}):
            calls = []
            def admin(*args):
                calls.append(args)
                return fake_api(*args, **option)
            with self.subTest(option=option), self.assertRaises(CommentRefused):
                submit(VALUE, admin, OWNER)
            self.assertFalse(any(c[0] == "POST" for c in calls))

    def test_controller_dispatch(self):
        ctrl = Control("issue-token", "admin-token")
        calls = []
        def admin(*args):
            calls.append(args)
            return fake_api(*args)
        ctrl.admin = admin
        self.assertIn("Verified owner-authored", ctrl.execute(VALUE))
        self.assertEqual(1, sum(c[0] == "POST" for c in calls))


if __name__ == "__main__":
    unittest.main()
