"""Hardening against malformed privileged report commands."""
import json
import unittest
from repoguardian.controller import Refused, parse_intent


REPORT = {
    "version": 1, "action": "report_vulnerability",
    "upstream": "ExternalOrg/example",
    "summary": "Separate resource consent boundary investigation",
    "description": (
        "## Summary\n" + "A" * 75 + "\n"
        "## Details\n" + "B" * 75 + "\n"
        "## Proof of concept\n" + "C" * 75 + "\n"
        "## Impact\n" + "D" * 75
    ),
    "acknowledge_private_submission": True,
}


class HardeningTests(unittest.TestCase):
    def check_fails(self, **updates):
        d = dict(REPORT, **updates)
        with self.assertRaises(Refused):
            parse_intent(json.dumps(d))

    def test_rejects_control_characters(self):
        self.check_fails(description=REPORT["description"] + "\u0000")
        self.check_fails(summary=REPORT["summary"] + "\nExtra")

    def test_blocks_public_substitution(self):
        self.check_fails(action="open_issue")
        self.check_fails(endpoint="/repos/ExternalOrg/example/issues")
        self.check_fails(upstream="https://github.com/ExternalOrg/example")

    def test_rejects_unvalidated_severity_type(self):
        self.check_fails(severity=["medium"])
        self.check_fails(severity={"medium": True})

    def test_rejects_untrusted_extra_fields(self):
        self.check_fails(token="secret")
        self.check_fails(shell="echo hello")
        self.check_fails(start_private_fork=True)


if __name__ == "__main__":
    unittest.main()
