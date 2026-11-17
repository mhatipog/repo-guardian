"""No-network tests for the private GitHub vulnerability-reporting bridge."""
import json
import unittest
from unittest.mock import patch

from repoguardian.controller import Control, Refused, parse_intent
from repoguardian.security_report_bridge import (
    SecurityReportRefused, submit, validate,
)


DESCRIPTION = (
    "## Summary\nA previously recorded consent decision may be applied across "
    "distinct resource contexts without a new approval.\n\n"
    "## Details\nThe remembered approval is based only on client identity "
    "and callback. Resource identity and permissions are omitted.\n\n"
    "## Proof of concept\nUse two isolated local authorization contexts and "
    "compare the remembered approval decisions. This is a test-only scenario.\n\n"
    "## Impact\nA client may reach a new authorization flow without a "
    "resource-specific consent prompt. End-to-end access is not established."
)


def request(**updates):
    v = {
        "version": 1, "action": "report_vulnerability",
        "upstream": "ExternalOrg/example", "summary": "Resource consent boundary not bound to audience",
        "description": DESCRIPTION, "severity": "medium",
        "cwe_ids": ["CWE-863"],
        "vulnerabilities": [{"package": {"ecosystem": "pip", "name": "example"}}],
        "acknowledge_private_submission": True,
    }
    v.update(updates)
    return v


class PrivateReportTests(unittest.TestCase):
    def test_parse_and_constrained_validate(self):
        value = parse_intent(json.dumps(request()))
        self.assertEqual(value["action"], "report_vulnerability")
        self.assertEqual(validate(value, "mhatipog"), value)

    def test_reject_missing_ack_and_unknown_fields(self):
        for bad in [
            request(acknowledge_private_submission=False),
            request(shell="curl something"),
            request(upstream="mhatipog/example"),
            request(upstream="ExternalOrg/../../unsafe"),
            request(severity="critical-high"),
            request(description="no actual evidence"),
            request(cwe_ids=["CWE-bad"]),
            request(vulnerabilities=[{"package": {"name": "example", "ecosystem": "other"}, "shell": "x"}]),
        ]:
            with self.subTest(bad=bad), self.assertRaises((SecurityReportRefused, Refused)):
                parse_intent(json.dumps(bad))

    def test_owner_token_private_only_no_public_issue(self):
        calls = []
        def admin(method, endpoint, payload=None):
            calls.append((method, endpoint, payload))
            if method == "GET" and endpoint == "/user":
                return {"login": "mhatipog", "type": "User"}
            if method == "GET" and endpoint == "/repos/ExternalOrg/example":
                return {"full_name": "ExternalOrg/example", "private": False, "archived": False}
            if method == "POST" and endpoint == "/repos/ExternalOrg/example/security-advisories/reports":
                self.assertEqual(payload["summary"], request()["summary"])
                self.assertEqual(payload["description"], DESCRIPTION)
                self.assertNotIn("acknowledge_private_submission", payload)
                return {
                    "ghsa_id": "GHSA-abcd-1234-wxyz", "summary": request()["summary"],
                    "state": "triage", "author": {"login": "mhatipog"},
                }
            raise AssertionError((method, endpoint, payload))
        result = submit(request(), admin, "mhatipog")
        self.assertIn("GHSA-abcd-1234-wxyz", result)
        self.assertEqual([x[1] for x in calls if x[0] == "POST"],
                         ["/repos/ExternalOrg/example/security-advisories/reports"])

    def test_reject_actor_impersonation(self):
        def admin(method, endpoint, payload=None):
            if endpoint == "/user":
                return {"login": "github-actions[bot]", "type": "Bot"}
            raise AssertionError("Must fail before contacting upstream")
        with self.assertRaises(SecurityReportRefused):
            submit(request(), admin, "mhatipog")

    def test_fail_closed_on_private_or_archived_target(self):
        for meta in [
            {"full_name": "ExternalOrg/example", "private": True, "archived": False},
            {"full_name": "ExternalOrg/example", "private": False, "archived": True},
            {"full_name": "ExternalOrg/other", "private": False, "archived": False},
        ]:
            def admin(method, endpoint, payload=None):
                if endpoint == "/user":
                    return {"login": "mhatipog", "type": "User"}
                if method == "GET" and endpoint == "/repos/ExternalOrg/example":
                    return meta
                raise AssertionError("Must fail before submission")
            with self.subTest(meta=meta), self.assertRaises(SecurityReportRefused):
                submit(request(), admin, "mhatipog")

    def test_unexpected_response_does_not_report_success(self):
        def admin(method, endpoint, payload=None):
            if endpoint == "/user":
                return {"login": "mhatipog", "type": "User"}
            if method == "GET":
                return {"full_name": "ExternalOrg/example", "private": False, "archived": False}
            return {"ghsa_id": "not-an-id", "summary": request()["summary"]}
        with self.assertRaisesRegex(SecurityReportRefused, "might have succeeded"):
            submit(request(), admin, "mhatipog")

    def test_controller_dispatch(self):
        ctrl = Control("issue-token", "admin-token")
        with patch.object(ctrl, "admin") as admin:
            admin.side_effect = [
                {"login": "mhatipog", "type": "User"},
                {"full_name": "ExternalOrg/example", "private": False, "archived": False},
                {"ghsa_id": "GHSA-abcd-1234-wxyz", "summary": request()["summary"],
                 "state": "triage", "author": {"login": "mhatipog"}},
            ]
            outcome = ctrl.execute(request())
        self.assertIn("Private vulnerability report accepted", outcome)
        self.assertEqual(admin.call_args_list[-1].args[:2],
                         ("POST", "/repos/ExternalOrg/example/security-advisories/reports"))


if __name__ == "__main__":
    unittest.main()
