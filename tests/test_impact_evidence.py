"""Unit tests for the read-only vulnerability-to-impact evidence gates."""
import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from repoguardian import cli
from repoguardian.impact_evidence import EvidenceError, analyze


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.top = Path(self.temp.name)
        self.root = self.top / "backend"
        (self.root / "app").mkdir(parents=True)
        (self.root / "pyproject.toml").write_text(
            '[project]\ndependencies = ["signxml>=5.1,<5.2"]\n'
        )
        (self.root / "uv.lock").write_text(
            'version = 1\n[[package]]\nname = "signxml"\nversion = "5.1.0"\n'
        )
        (self.root / "app" / "firma.py").write_text(
            "def verify():\n    return expect_signature_policy\n"
        )
        self.evidence = {
            "schema_version": 1,
            "package": "signxml",
            "fixed_version": "5.3.1",
            "downstream_commit": "a" * 40,
            "ci_run_url": "https://github.com/org/private/actions/runs/123",
            "test_summary": {"passed": 1004, "failed": 0},
            "cases": [
                {"name": "matching", "role": "positive", "vulnerable": "accept", "fixed": "accept"},
                {"name": "wrong", "role": "negative", "vulnerable": "reject", "fixed": "reject"},
                {"name": "missing", "role": "defect", "vulnerable": "accept", "fixed": "reject"},
            ],
        }
        self.matrix = self.top / "evidence.json"
        self.write()

    def write(self):
        self.matrix.write_text(json.dumps(self.evidence))

    def check(self, callsite="app/firma.py", symbol="expect_signature_policy"):
        self.write()
        return analyze(self.root, callsite, symbol, self.matrix)

    def test_good_case_requires_independent_review(self):
        record = self.check()
        self.assertTrue(record["ready_for_coordinated_remediation"])
        self.assertEqual(record["recorded_locked_version"], "5.1.0")
        self.assertEqual(len(record["lock_sha256"]), 64)
        self.assertIn("does not execute", record["limitation"])
        self.assertNotIn("production_exploit_confirmed", record)

    def test_symbol_is_a_candidate_not_confirmed_reachability(self):
        record = self.check(symbol="another_symbol")
        self.assertFalse(record["gates"]["callsite_candidate"])
        self.assertFalse(record["ready_for_coordinated_remediation"])

    def test_missing_positive_control_blocks_decision(self):
        self.evidence["cases"] = self.evidence["cases"][1:]
        record = self.check()
        self.assertFalse(record["gates"]["positive_control"])
        self.assertFalse(record["ready_for_coordinated_remediation"])

    def test_wrong_result_blocks_decision(self):
        self.evidence["cases"][-1]["fixed"] = "accept"
        record = self.check()
        self.assertFalse(record["ready_for_coordinated_remediation"])
        self.assertEqual(len(record["matrix_errors"]), 1)

    def test_failed_tests_block_decision(self):
        self.evidence["test_summary"]["failed"] = 1
        record = self.check()
        self.assertFalse(record["gates"]["regressions_reported_passing"])

    def test_unanchored_commit_blocks_decision(self):
        self.evidence["downstream_commit"] = "main"
        record = self.check()
        self.assertFalse(record["gates"]["source_commit_documented"])

    def test_unchanged_dependency_blocks_decision(self):
        self.evidence["fixed_version"] = "5.1.0"
        record = self.check()
        self.assertFalse(record["gates"]["locked_version_differs_from_fix"])

    def test_missing_dependency_blocks_decision(self):
        (self.root / "pyproject.toml").write_text(
            '[project]\ndependencies = ["other>=1"]\n'
        )
        record = self.check()
        self.assertFalse(record["gates"]["direct_dependency"])

    def test_callsite_path_traversal_is_rejected(self):
        (self.top / "outside.py").write_text("expect_signature_policy")
        with self.assertRaises(EvidenceError):
            self.check(callsite="../outside.py")

    def test_duplicate_control_rejected(self):
        self.evidence["cases"].append(dict(self.evidence["cases"][0]))
        with self.assertRaises(EvidenceError):
            self.check()

    def test_invalid_symbol_rejected(self):
        with self.assertRaises(EvidenceError):
            self.check(symbol="check; rm -rf /")

    def test_missing_lock_version_rejected(self):
        (self.root / "uv.lock").write_text('version = 1\n')
        with self.assertRaises(EvidenceError):
            self.check()

    def test_cli_offline_does_not_require_token(self):
        output = io.StringIO()
        self.write()
        with patch.dict(os.environ, {"RG_ADMIN_TOKEN": "", "GH_TOKEN": ""}):
            with contextlib.redirect_stdout(output):
                code = cli.main([
                    "impact-check", "--project", str(self.root),
                    "--callsite", "app/firma.py",
                    "--symbol", "expect_signature_policy",
                    "--matrix", str(self.matrix),
                ])
        self.assertEqual(code, 0)
        self.assertIn('"ready_for_coordinated_remediation": true', output.getvalue())


if __name__ == "__main__":
    unittest.main()
