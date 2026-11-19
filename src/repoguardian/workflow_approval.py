"""Owner-authorized approval of blocked GitHub Actions runs from fork PRs.

The private controller is the only caller. This module has no shell execution,
does not accept arbitrary API paths, and never merges or approves a PR review.
"""
import re

class WorkflowApprovalRefused(Exception):
    pass

SHA = re.compile(r"^[0-9a-f]{40}$")
WORKFLOW = re.compile(r"^\.github/workflows/[A-Za-z0-9_.-]+\.ya?ml$")
REPO_NAME = re.compile(r"^[A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,100}$")
LOGIN = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?$")


def validate(value, owner):
    expected = {
        "version", "action", "repo", "expected_repo_id", "pr_number",
        "expected_pr_author", "expected_head_sha", "run_ids",
        "expected_workflow_paths", "acknowledge_untrusted_code_execution",
    }
    if not isinstance(value, dict) or set(value) != expected:
        raise WorkflowApprovalRefused("Supply the complete, exact approval intent")
    if value.get("version") != 1 or value.get("action") != "approve_fork_workflows":
        raise WorkflowApprovalRefused("Unsupported approval request")
    repo = value.get("repo")
    if not isinstance(repo, str) or not REPO_NAME.fullmatch(repo):
        raise WorkflowApprovalRefused("Invalid repository")
    if repo.split("/")[0].lower() != owner.lower():
        raise WorkflowApprovalRefused("Can approve workflows only in owner's repositories")
    if type(value.get("expected_repo_id")) is not int or value["expected_repo_id"] <= 0:
        raise WorkflowApprovalRefused("Inspected numeric repository id required")
    if type(value.get("pr_number")) is not int or value["pr_number"] <= 0:
        raise WorkflowApprovalRefused("Pull request number required")
    author = value.get("expected_pr_author")
    if not isinstance(author, str) or not LOGIN.fullmatch(author) or author.lower() == owner.lower():
        raise WorkflowApprovalRefused("Expected author must be a separate GitHub account")
    sha = value.get("expected_head_sha")
    if not isinstance(sha, str) or not SHA.fullmatch(sha):
        raise WorkflowApprovalRefused("Exact lowercase 40-character head SHA required")
    ids = value.get("run_ids")
    paths = value.get("expected_workflow_paths")
    if (not isinstance(ids, list) or not 1 <= len(ids) <= 6
            or any(type(x) is not int or x <= 0 for x in ids)
            or len(set(ids)) != len(ids)):
        raise WorkflowApprovalRefused("Supply one to six distinct inspected workflow run IDs")
    if (not isinstance(paths, list) or len(paths) != len(ids)
            or any(not isinstance(p, str) or not WORKFLOW.fullmatch(p) for p in paths)
            or len(set(paths)) != len(paths)):
        raise WorkflowApprovalRefused("Supply one exact allowed workflow path per run")
    if value.get("acknowledge_untrusted_code_execution") is not True:
        raise WorkflowApprovalRefused("Must acknowledge that fork workflow code will execute")
    return value


def _verify_repo(value, repo):
    if (repo.get("id") != value["expected_repo_id"]
            or repo.get("full_name", "").lower() != value["repo"].lower()
            or repo.get("fork") or repo.get("archived")
            or not repo.get("owner", {}).get("login", "").lower() ==
            value["repo"].split("/")[0].lower()):
        raise WorkflowApprovalRefused("Repository identity changed")


def _verify_pr(value, pr):
    if (pr.get("number") != value["pr_number"] or pr.get("state") != "open"
            or pr.get("draft") or pr.get("head", {}).get("sha") != value["expected_head_sha"]
            or pr.get("user", {}).get("login", "").lower() !=
            value["expected_pr_author"].lower()
            or pr.get("base", {}).get("repo", {}).get("full_name", "").lower() !=
            value["repo"].lower()
            or pr.get("head", {}).get("repo", {}).get("owner", {}).get("login", "").lower() !=
            value["expected_pr_author"].lower()
            or not pr.get("head", {}).get("repo", {}).get("fork"):
        raise WorkflowApprovalRefused("PR state, author, fork relationship or head changed")


def _verify_run(value, run, run_id, path, pr):
    if (run.get("id") != run_id or run.get("repository", {}).get("id") !=
            value["expected_repo_id"]
            or run.get("repository", {}).get("full_name", "").lower() !=
            value["repo"].lower()
            or run.get("head_sha") != value["expected_head_sha"]
            or run.get("head_branch") != pr["head"]["ref"]
            or run.get("head_repository", {}).get("full_name", "").lower() !=
            pr["head"]["repo"]["full_name"].lower()
            or run.get("event") != "pull_request"
            or run.get("actor", {}).get("login", "").lower() !=
            value["expected_pr_author"].lower()
            or run.get("path") != path):
        raise WorkflowApprovalRefused("Workflow run does not match authorized fork PR")
    if run.get("conclusion") == "action_required" and run.get("status") == "completed":
        return "pending"
    if run.get("conclusion") != "action_required":
        return "already_progressed"
    raise WorkflowApprovalRefused("Workflow run in unexpected state")


def approve(value, admin, owner):
    """Preflight every run before approving any; verify all GitHub identities first."""
    validate(value, owner)
    endpoint = "/repos/" + value["repo"]
    repo = admin("GET", endpoint)
    _verify_repo(value, repo)
    pr = admin("GET", endpoint + "/pulls/" + str(value["pr_number"]))
    _verify_pr(value, pr)
    fork_name = pr["head"]["repo"]["full_name"]
    fork = admin("GET", "/repos/" + fork_name)
    if (fork.get("full_name", "").lower() != fork_name.lower()
            or not fork.get("fork")
            or fork.get("parent", {}).get("full_name", "").lower() != value["repo"].lower()):
        raise WorkflowApprovalRefused("Fork parent does not match the target repository")
    inspections = []
    for run_id, path in zip(value["run_ids"], value["expected_workflow_paths"]):
        run = admin("GET", endpoint + "/actions/runs/" + str(run_id))
        inspections.append((run_id, path, _verify_run(value, run, run_id, path, pr)))
    approved = []
    for run_id, path, state in inspections:
        if state == "already_progressed":
            continue
        # Recheck the PR and the run immediately before each privileged write.
        _verify_pr(value, admin("GET", endpoint + "/pulls/" + str(value["pr_number"])))
        run = admin("GET", endpoint + "/actions/runs/" + str(run_id))
        current = _verify_run(value, run, run_id, path, pr)
        if current == "already_progressed":
            continue
        admin("POST", endpoint + "/actions/runs/" + str(run_id) + "/approve")
        approved.append(run_id)
    # Never call this a test pass: GitHub accepted approval, not the workflow outcome.
    return ("GitHub accepted fork workflow approval for run IDs "
            + ", ".join(str(x) for x in approved)
            + "; " + str(len(inspections) - len(approved))
            + " had already progressed. Check workflow outcomes separately.")
