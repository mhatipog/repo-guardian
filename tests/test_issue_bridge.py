"""Upstream issue bridge contract tests (no network or credentials)."""
import json
import unittest

from repoguardian.controller import Control, Refused, parse_intent
from repoguardian.issue_bridge import IssueRefused, submit, validate

OWNER = "mhatipog"
FORK = "mhatipog/fabric-cicd"
UPSTREAM = "microsoft/fabric-cicd"
HEAD = "fix/scoped-orphan-folder-cleanup-20261105"
SHA = "6fc37f5172332a89aa95470881dbd4ad77c8a331"
TITLE = "[BUG] Scoped orphan cleanup removes unrelated empty workspace folders"
BODY = ("Minimal reproducer: unpublish_all_orphan_items with an exclude-all "
        "regex selects no items, but still sends a DELETE request for a "
        "workspace-empty folder outside the selected deployment scope. "
        "This is reproducible using a test-only Fabric workspace. ")
VALUE = {"version": 1, "action": "open_issue", "fork": FORK, "upstream": UPSTREAM,
         "head": HEAD, "expected_head_sha": SHA, "title": TITLE, "body": BODY,
         "acknowledge_public_exposure": True}


def fake_response(method, path, data=None, *, actor=OWNER, parent=UPSTREAM,
                  head_sha=SHA, existing=False, has_issues=True, issue_author=OWNER,
                  existing_body=BODY):
    if method == "GET":
        if path == "/user":
            return {"login": actor, "type": "User"}
        if path == "/repos/" + FORK:
            return {"fork": True, "private": False, "archived": False,
                    "full_name": FORK, "parent": {"full_name": parent}}
        if path == "/repos/" + UPSTREAM:
            return {"full_name": UPSTREAM, "archived": False,
                    "private": False, "has_issues": has_issues}
        if path == "/repos/" + FORK + "/git/ref/heads/" + HEAD:
            return {"object": {"sha": head_sha}}
        if path == "/repos/" + UPSTREAM + "/issues?state=all&per_page=100":
            return ([{"number": 42, "title": TITLE, "body": existing_body,
                      "user": {"login": issue_author}}] if existing else [])
        if path == "/repos/" + UPSTREAM + "/issues/42":
            return {"number": 42, "title": TITLE, "body": BODY,
                    "user": {"login": OWNER}, "state": "open",
                    "html_url": "https://github.com/" + UPSTREAM + "/issues/42"}
    if method == "POST" and path == "/repos/" + UPSTREAM + "/issues":
        assert data == {"title": TITLE, "body": BODY}
        return {"number": 42}
    raise AssertionError((method, path, data))


class IssueBridgeTests(unittest.TestCase):
    def test_parse_and_validate(self):
        self.assertEqual(validate(VALUE, OWNER), VALUE)
        self.assertEqual(parse_intent(json.dumps(VALUE)), VALUE)

    def test_reject_unexpected_action_fields(self):
        for extra in ({"shell": "echo hi"}, {"at": "2026-11-06T00:00:00Z"}):
            with self.subTest(extra=extra), self.assertRaises(Refused):
                parse_intent(json.dumps({**VALUE, **extra}))

    def test_reject_arbitrary_destination(self):
        for bad in ("another/repo", "mhatipog/repo-guardian", "https://x", "../../y"):
            with self.subTest(bad=bad), self.assertRaises(IssueRefused):
                validate({**VALUE, "fork": bad}, OWNER)

    def test_reject_branch_injection(self):
        for bad in ("../../main", "fix//branch", "https://host", "a@{b}"):
            with self.subTest(bad=bad), self.assertRaises(IssueRefused):
                validate({**VALUE, "head": bad}, OWNER)

    def test_public_exposure_and_exact_head_required(self):
        for change in ({"acknowledge_public_exposure": False},
                       {"expected_head_sha": "unknown"},
                       {"title": "title\nsecond line"},
                       {"body": "too short"}):
            with self.subTest(change=change), self.assertRaises(IssueRefused):
                validate({**VALUE, **change}, OWNER)

    def test_submit_and_verify_without_upstream_url_in_controller_reply(self):
        calls = []
        def api(*args):
            calls.append(args)
            return fake_response(*args)
        result = submit(VALUE, api, OWNER)
        self.assertIn("Verified upstream issue number 42", result)
        self.assertNotIn("https://", result)
        self.assertEqual([("POST", "/repos/" + UPSTREAM + "/issues")],
                         [c[:2] for c in calls if c[0] == "POST"])

    def test_idempotent_existing_issue(self):
        calls = []
        def api(*args):
            calls.append(args)
            return fake_response(*args, existing=True)
        self.assertIn("verified head", submit(VALUE, api, OWNER).replace("reviewed head", "verified head"))
        self.assertEqual(0, sum(c[0] == "POST" for c in calls))

    def test_refuse_other_token_actor_before_target_write(self):
        calls = []
        def api(*args):
            calls.append(args)
            return fake_response(*args, actor="somebody")
        with self.assertRaisesRegex(IssueRefused, "personal token"):
            submit(VALUE, api, OWNER)
        self.assertEqual([("GET", "/user")], [c[:2] for c in calls])

    def test_refuse_parent_mismatch(self):
        calls = []
        def api(*args):
            calls.append(args)
            return fake_response(*args, parent="different/project")
        with self.assertRaisesRegex(IssueRefused, "public fork"):
            submit(VALUE, api, OWNER)
        self.assertFalse(any(c[0] == "POST" for c in calls))

    def test_refuse_changed_head(self):
        calls = []
        def api(*args):
            calls.append(args)
            return fake_response(*args, head_sha="a" * 40)
        with self.assertRaisesRegex(IssueRefused, "reviewed SHA"):
            submit(VALUE, api, OWNER)
        self.assertFalse(any(c[0] == "POST" for c in calls))

    def test_refuse_issues_disabled(self):
        with self.assertRaisesRegex(IssueRefused, "public issue destination"):
            submit(VALUE, lambda *args: fake_response(*args, has_issues=False), OWNER)

    def test_refuse_same_title_edited_or_other_author(self):
        for changes in ({"issue_author": "another"}, {"existing_body": "different"}):
            with self.subTest(changes=changes), self.assertRaisesRegex(IssueRefused, "already exists"):
                submit(VALUE, lambda *args: fake_response(*args, existing=True, **changes), OWNER)

    def test_controller_dispatch_uses_new_action(self):
        control = Control("issue-token", "admin-token")
        calls = []
        def admin(*args):
            calls.append(args)
            return fake_response(*args)
        control.admin = admin
        msg = control.execute(VALUE)
        self.assertIn("upstream issue number 42", msg)
        self.assertEqual(1, sum(c[0] == "POST" for c in calls))


if __name__ == "__main__":
    unittest.main()
