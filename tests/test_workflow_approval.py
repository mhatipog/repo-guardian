"""Security and idempotency tests for first-time fork workflow approvals."""
import copy
import json
import unittest
from unittest.mock import Mock

from repoguardian.controller import Refused, parse_intent
from repoguardian.workflow_approval import WorkflowApprovalRefused, approve, validate

SHA = "a417977e773407864b84f8b4279bed862aeec2a5"
INTENT = {
    "version": 1, "action": "approve_fork_workflows",
    "repo": "mhatipog/dbt-chaos", "expected_repo_id": 1461046133,
    "pr_number": 5, "expected_pr_author": "jarichb",
    "expected_head_sha": SHA, "run_ids": [44550384408, 44550384329],
    "expected_workflow_paths": [
        ".github/workflows/framework.yml",
        ".github/workflows/commerce-chaos.yml",
    ],
    "acknowledge_untrusted_code_execution": True,
}


def fixtures():
    repo = {
        "id": 1461046133, "full_name": "mhatipog/dbt-chaos",
        "owner": {"login": "mhatipog"}, "fork": False, "archived": False,
    }
    fork = {
        "full_name": "jarichb/dbt-chaos", "fork": True,
        "parent": {"full_name": "mhatipog/dbt-chaos"},
    }
    pr = {
        "number": 5, "state": "open", "draft": False,
        "user": {"login": "jarichb"},
        "base": {"repo": {"full_name": "mhatipog/dbt-chaos"}},
        "head": {
            "sha": SHA, "ref": "model2data-commerce-dataset",
            "repo": {"full_name": "jarichb/dbt-chaos",
                     "owner": {"login": "jarichb"}, "fork": True},
        },
    }
    runs = {}
    for run_id, path in zip(INTENT["run_ids"], INTENT["expected_workflow_paths"]):
        runs[run_id] = {
            "id": run_id, "path": path,
            "repository": {"id": 1461046133, "full_name": "mhatipog/dbt-chaos"},
            "head_repository": {"full_name": "jarichb/dbt-chaos"},
            "head_sha": SHA, "head_branch": "model2data-commerce-dataset",
            "actor": {"login": "jarichb"}, "event": "pull_request",
            "status": "completed", "conclusion": "action_required",
        }
    return repo, fork, pr, runs


def backend(repo, fork, pr, runs):
    posts = []
    def admin(method, path, payload=None):
        if method == "POST":
            posts.append(path)
            return {}
        if path == "/repos/mhatipog/dbt-chaos":
            return copy.deepcopy(repo)
        if path == "/repos/jarichb/dbt-chaos":
            return copy.deepcopy(fork)
        if path == "/repos/mhatipog/dbt-chaos/pulls/5":
            return copy.deepcopy(pr)
        prefix = "/repos/mhatipog/dbt-chaos/actions/runs/"
        if path.startswith(prefix):
            return copy.deepcopy(runs[int(path[len(prefix):])])
        raise AssertionError("Unexpected API request " + method + " " + path)
    return admin, posts


class WorkflowApprovalTests(unittest.TestCase):
    def intent(self):
        return copy.deepcopy(INTENT)

    def test_valid_request(self):
        self.assertEqual(self.intent(), validate(self.intent(), "mhatipog"))
        self.assertEqual(INTENT, parse_intent(json.dumps(INTENT)))

    def test_no_acknowledgment(self):
        value = self.intent()
        value["acknowledge_untrusted_code_execution"] = False
        with self.assertRaises(WorkflowApprovalRefused):
            validate(value, "mhatipog")

    def test_unknown_fields_rejected(self):
        value = self.intent()
        value["shell"] = "echo unsafe"
        with self.assertRaises(Refused):
            parse_intent(json.dumps(value))

    def test_other_owner_rejected(self):
        value = self.intent()
        value["repo"] = "other/dbt-chaos"
        with self.assertRaises(WorkflowApprovalRefused):
            validate(value, "mhatipog")

    def test_duplicate_run_ids_rejected(self):
        value = self.intent()
        value["run_ids"][1] = value["run_ids"][0]
        with self.assertRaises(WorkflowApprovalRefused):
            validate(value, "mhatipog")

    def test_unexpected_workflow_path_rejected(self):
        value = self.intent()
        value["expected_workflow_paths"][0] = "../security.yml"
        with self.assertRaises(WorkflowApprovalRefused):
            validate(value, "mhatipog")

    def test_all_runs_approved_only_after_validated(self):
        api, posts = backend(*fixtures())
        result = approve(self.intent(), api, "mhatipog")
        self.assertIn("44550384408", result)
        self.assertEqual([
            "/repos/mhatipog/dbt-chaos/actions/runs/44550384408/approve",
            "/repos/mhatipog/dbt-chaos/actions/runs/44550384329/approve",
        ], posts)

    def test_head_mismatch_causes_zero_writes(self):
        repo, fork, pr, runs = fixtures()
        runs[44550384329]["head_sha"] = "0" * 40
        api, posts = backend(repo, fork, pr, runs)
        with self.assertRaisesRegex(WorkflowApprovalRefused, "run does not match"):
            approve(self.intent(), api, "mhatipog")
        self.assertEqual([], posts)

    def test_fork_parent_mismatch_causes_zero_writes(self):
        repo, fork, pr, runs = fixtures()
        fork["parent"]["full_name"] = "not-target/example"
        api, posts = backend(repo, fork, pr, runs)
        with self.assertRaisesRegex(WorkflowApprovalRefused, "Fork parent"):
            approve(self.intent(), api, "mhatipog")
        self.assertEqual([], posts)

    def test_run_author_mismatch_causes_zero_writes(self):
        repo, fork, pr, runs = fixtures()
        runs[44550384408]["actor"]["login"] = "other"
        api, posts = backend(repo, fork, pr, runs)
        with self.assertRaisesRegex(WorkflowApprovalRefused, "run does not match"):
            approve(self.intent(), api, "mhatipog")
        self.assertEqual([], posts)

    def test_already_progressed_is_idempotent(self):
        repo, fork, pr, runs = fixtures()
        for run in runs.values():
            run["status"] = "completed"
            run["conclusion"] = "success"
        api, posts = backend(repo, fork, pr, runs)
        message = approve(self.intent(), api, "mhatipog")
        self.assertEqual([], posts)
        self.assertIn("2 had already progressed", message)

    def test_no_write_after_review_head_moves(self):
        repo, fork, pr, runs = fixtures()
        api, posts = backend(repo, fork, pr, runs)
        count = [0]
        def drifting_api(method, path, payload=None):
            if method == "GET" and path.endswith("/pulls/5"):
                count[0] += 1
                if count[0] == 2:
                    changed = copy.deepcopy(pr)
                    changed["head"]["sha"] = "f" * 40
                    return changed
            return api(method, path, payload)
        with self.assertRaisesRegex(WorkflowApprovalRefused, "PR state"):
            approve(self.intent(), drifting_api, "mhatipog")
        self.assertEqual([], posts)


if __name__ == "__main__":
    unittest.main()
