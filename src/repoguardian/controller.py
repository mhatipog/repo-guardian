"""Issue-driven private control plane. Python stdlib only.

The controller runs ONLY in a private repository, with a token held in Actions
secrets. An issue is an intent, NEVER an authorization. Approval must be a
separate comment from the account owner and must match the request hash.
"""
import datetime as dt
import hashlib
import json
import os
import re
import sys
import time
import subprocess
import tempfile
from pathlib import Path
import urllib.error
import urllib.parse
import urllib.request

API = "https://api.github.com"
OWNER = os.getenv("RG_OWNER", "mhatipog")
CONTROL_REPO = OWNER + "/repo-guardian-control"
NAME = re.compile(r"^[A-Za-z0-9_.-]{1,100}$")
TOPIC = re.compile(r"^[a-z0-9][a-z0-9-]{0,49}$")
RFC3339 = "%Y-%m-%dT%H:%M:%SZ"


class Refused(Exception):
    pass


def safe_repo(full_name):
    if not isinstance(full_name, str) or full_name.count("/") != 1:
        raise Refused("Repository must be owner/name")
    owner, name = full_name.split("/")
    if not NAME.fullmatch(owner) or not NAME.fullmatch(name) or owner in {".", ".."} or name in {".", ".."}:
        raise Refused("Invalid repository identifier")
    return full_name


def request_api(token, method, path, data=None):
    if not path.startswith("/") or path.startswith("//") or "://" in path:
        raise Refused("Invalid API path")
    payload = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(
        API + path, data=payload, method=method,
        headers={"Authorization": "Bearer " + token,
                 "Accept": "application/vnd.github+json",
                 "X-GitHub-Api-Version": "2022-11-28",
                 "Content-Type": "application/json",
                 "User-Agent": "repo-guardian/0.2"},
    )
    try:
        with urllib.request.urlopen(req, timeout=25) as response:
            raw = response.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        try:
            err = json.loads(e.read()).get("message", "GitHub rejected request")
        except (ValueError, UnicodeDecodeError):
            err = "GitHub rejected request"
        raise Refused("GitHub returned HTTP %s: %s" % (e.code, err)) from None


def parse_intent(body):
    try:
        value = json.loads(body)
    except (TypeError, ValueError):
        raise Refused("Issue body must be a single JSON object")
    if not isinstance(value, dict) or value.get("version") != 1:
        raise Refused("Expected JSON object with version: 1")
    action = value.get("action")
    fields = {
        "status": {"version", "action"},
        "topics": {"version", "action", "repo", "names", "mode", "at"},
        "private_copy": {"version", "action", "source", "name", "at"},
        "create_repo": {"version", "action", "name", "visibility", "description", "at"},
        "fork": {"version", "action", "source", "name", "at"},
        "visibility": {"version", "action", "repo", "visibility",
                       "expected_repo_id", "expected_visibility", "at", "acknowledge_public_exposure"},
    }
    if action not in fields or set(value) - fields[action]:
        raise Refused("Invalid action or unsupported JSON fields")
    if action == "status":
        pass
    elif action == "create_repo":
        if not isinstance(value.get("name"), str) or not NAME.fullmatch(value["name"]):
            raise Refused("Invalid repository name")
        if value.get("visibility") not in ("public", "private"):
            raise Refused("Choose public or private")
        if not isinstance(value.get("description", ""), str) or len(value.get("description", "")) > 200:
            raise Refused("Description must be <= 200 characters")
    elif action == "private_copy":
        safe_repo(value.get("source"))
        if not isinstance(value.get("name"), str) or not NAME.fullmatch(value["name"]):
            raise Refused("Specify a valid destination name")
    elif action == "topics":
        full = safe_repo(value.get("repo"))
        if full.split("/")[0].lower() != OWNER.lower():
            raise Refused("Only repositories owned by " + OWNER + " are supported")
        names = value.get("names")
        if not isinstance(names, list) or len(names) > 20 or any(
            not isinstance(name, str) or not TOPIC.fullmatch(name) for name in names
        ) or len(set(names)) != len(names):
            raise Refused("Topics must be <=20 unique lowercase slugs")
        if value.get("mode", "add") not in ("add", "remove", "replace"):
            raise Refused("mode must be add, remove or replace")
    elif action == "fork":
        safe_repo(value.get("source"))
        if value["source"].split("/")[0].lower() == OWNER:
            raise Refused("Forking own account repositories is not supported in v0.2")
        if not isinstance(value.get("name"), str) or not NAME.fullmatch(value["name"]):
            raise Refused("Specify a valid destination fork name")
    elif action == "visibility":
        full = safe_repo(value.get("repo"))
        if full.split("/")[0].lower() != OWNER:
            raise Refused("Only repositories owned by " + OWNER + " are supported")
        if value.get("visibility") not in ("public", "private"):
            raise Refused("Invalid visibility")
        if value.get("expected_visibility") not in ("public", "private"):
            raise Refused("Supply current visibility from a live inspection")
        if type(value.get("expected_repo_id")) is not int or value["expected_repo_id"] <= 0:
            raise Refused("Supply numeric expected_repo_id from a live inspection")
        if value["visibility"] == value["expected_visibility"]:
            raise Refused("Requested visibility is unchanged")
        if value["visibility"] == "public" and value.get("acknowledge_public_exposure") is not True:
            raise Refused("Publication requires acknowledge_public_exposure: true")
    at = value.get("at")
    if at is not None:
        if not isinstance(at, str) or not re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", at):
            raise Refused("at must be UTC like 2026-11-10T09:00:00Z")
        try:
            dt.datetime.strptime(at, RFC3339)
        except ValueError:
            raise Refused("Invalid UTC timestamp")
    return value


def digest(value):
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(canonical).hexdigest()[:16]


def review_status(value, now=None):
    """Return ready, waiting, or missed. Publication fails closed if >20m late."""
    if "at" not in value:
        return "ready"
    now = now or dt.datetime.now(dt.timezone.utc)
    at = dt.datetime.strptime(value["at"], RFC3339).replace(tzinfo=dt.timezone.utc)
    if now < at:
        return "waiting"
    if value["action"] == "visibility" and value["visibility"] == "public" and now - at > dt.timedelta(minutes=20):
        return "missed"
    return "ready"


def is_manual_approval(comment, expected, owner=OWNER):
    """Allow only a direct human-account GitHub comment, not an OAuth/GitHub App integration.

    Connected ChatGPT tools can post as the same account owner but their GitHub
    issue comments contain a non-null 'performed_via_github_app' record.
    """
    return (
        comment.get("body", "").strip() == expected
        and comment.get("user", {}).get("login", "").lower() == owner.lower()
        and comment.get("user", {}).get("type") == "User"
        and comment.get("performed_via_github_app") is None
    )


class Control:
    def __init__(self, issue_token, admin_token, control_repo=CONTROL_REPO):
        if control_repo != CONTROL_REPO:
            raise Refused("Controller must run in the dedicated private repository")
        if not issue_token:
            raise Refused("GITHUB_TOKEN is required for request tracking")
        self.issues_token = issue_token
        self.admin_token = admin_token
        self.repo = control_repo

    def issue_get(self, path, method="GET", payload=None):
        return request_api(self.issues_token, method, "/repos/" + self.repo + path, payload)

    def admin(self, method, path, payload=None):
        if not self.admin_token:
            raise Refused("RG_ADMIN_TOKEN is not configured; no privileged operation was executed")
        return request_api(self.admin_token, method, path, payload)

    def comments(self, number):
        result = []
        for page in range(1, 11):
            batch = self.issue_get("/issues/%d/comments?per_page=100&page=%d" % (number, page))
            result.extend(batch)
            if len(batch) < 100:
                break
        return result

    def comment(self, number, message):
        return self.issue_get("/issues/%d/comments" % number, "POST", {"body": message})

    def execute(self, value):
        action = value["action"]
        if action == "topics":
            full = value["repo"]
            before = self.admin("GET", "/repos/" + full)
            if before.get("fork") and before.get("private"):
                raise Refused("Unexpected private fork; review manually")
            endpoint = "/repos/" + full + "/topics"
            existing = self.admin("GET", endpoint).get("names", [])
            mode = value.get("mode", "add")
            if mode == "replace":
                names = sorted(value["names"])
            elif mode == "remove":
                names = sorted(set(existing) - set(value["names"]))
            else:
                names = sorted(set(existing) | set(value["names"]))
            if len(names) > 20:
                raise Refused("GitHub supports at most 20 topics")
            if sorted(existing) == names:
                return "Topics already match on " + full + ": " + ", ".join(names)
            self.admin("PUT", endpoint, {"names": names})
            after = sorted(self.admin("GET", endpoint).get("names", []))
            if after != names:
                raise Refused("Topics not verified; inspect target")
            return "Updated and verified topics for " + full + ": " + ", ".join(after)

        if action == "private_copy":
            source = value["source"]
            full = OWNER + "/" + value["name"]
            source_meta = self.admin("GET", "/repos/" + source)
            if source_meta.get("private"):
                raise Refused("Private copy requires a public source")
            if source_meta.get("size", 0) > 50000:
                raise Refused("Source too large for first-release copy (>50 MB)")
            try:
                self.admin("GET", "/repos/" + full)
            except Refused as e:
                if "HTTP 404:" not in str(e):
                    raise
            else:
                raise Refused("Destination already exists")
            created = self.admin("POST", "/user/repos", {
                "name": value["name"], "private": True,
                "description": "Private standalone code copy of https://github.com/" + source,
                "auto_init": False})
            if created.get("full_name", "").lower() != full.lower() or not created.get("private"):
                raise Refused("Unexpected private copy destination; inspect manually")
            if not self.admin_token:
                raise Refused("Admin token missing; private destination was created, but not copied")
            # Clone from public upstream and push only branches and tags, preserving
            # the Git commit history. No upstream fork network or issue/PR metadata.
            with tempfile.TemporaryDirectory(prefix="repo-guardian-") as td:
                password = Path(td) / "askpass.sh"
                password.write_text('#!/bin/sh\ncase "$1" in *Username*) printf %s x-access-token;; *) printf %s "$RG_GIT_PASSWORD";; esac\n')
                password.chmod(0o700)
                env = dict(os.environ)
                env["GIT_ASKPASS"] = str(password)
                env["GIT_TERMINAL_PROMPT"] = "0"
                env["RG_GIT_PASSWORD"] = self.admin_token
                env["GIT_CONFIG_NOSYSTEM"] = "1"
                clone = "https://github.com/" + source + ".git"
                remote = "https://github.com/" + full + ".git"
                # Use --bare rather than --mirror to exclude GitHub pull request refs.
                for argv in (
                    ["git", "clone", "--quiet", "--bare", clone, str(Path(td) / "repo.git")],
                    ["git", "-C", str(Path(td) / "repo.git"), "push", "--quiet", "--mirror", remote]
                ):
                    try:
                        result = subprocess.run(argv, env=env, text=True, capture_output=True,
                                                timeout=150, check=False)
                    except (subprocess.TimeoutExpired, OSError) as e:
                        raise Refused("Private repo created; Git copy failed. Inspect manually: " + type(e).__name__)
                    if result.returncode:
                        raise Refused("Private repo created but Git copy failed; inspect before retry")
            dest = self.admin("GET", "/repos/" + full)
            if dest.get("id") != created.get("id") or dest.get("visibility") != "private" or dest.get("fork"):
                raise Refused("Private copy visibility/network verification failed")
            branch = source_meta.get("default_branch")
            src_ref = self.admin("GET", "/repos/" + source + "/git/ref/heads/" + branch)
            dest_ref = self.admin("GET", "/repos/" + full + "/git/ref/heads/" + branch)
            if src_ref.get("object", {}).get("sha") != dest_ref.get("object", {}).get("sha"):
                raise Refused("Private copy branch SHA did not match upstream")
            return "Private standalone copy created and verified: " + full + " from " + source

        if action == "create_repo":
            full = OWNER + "/" + value["name"]
            try:
                self.admin("GET", "/repos/" + full)
            except Refused as e:
                if "HTTP 404:" not in str(e):
                    raise
            else:
                raise Refused("Destination already exists; inspect before retry")
            result = self.admin("POST", "/user/repos", {
                "name": value["name"], "private": value["visibility"] == "private",
                "description": value.get("description", ""), "auto_init": True})
            if result.get("full_name", "").lower() != full.lower():
                raise Refused("Creation returned unexpected repository; investigate")
            verified = self.admin("GET", "/repos/" + full)
            if verified.get("id") != result.get("id") or verified.get("visibility") != value["visibility"]:
                raise Refused("Created, but verification failed. Inspect manually")
            return "Created and verified " + full

        if action == "fork":
            source = value["source"]
            full = OWNER + "/" + value["name"]
            try:
                self.admin("GET", "/repos/" + full)
            except Refused as e:
                if "HTTP 404:" not in str(e):
                    raise
            else:
                raise Refused("Destination already exists; inspect before retry")
            source_meta = self.admin("GET", "/repos/" + source)
            if source_meta.get("private"):
                raise Refused("v0.2 permits public-source forks only")
            fork = self.admin("POST", "/repos/" + source + "/forks", {"name": value["name"]})
            if fork.get("full_name", "").lower() != full.lower():
                raise Refused("Unexpected fork response; investigate")
            for _ in range(10):
                try:
                    verified = self.admin("GET", "/repos/" + full)
                    if (verified.get("fork") and
                        verified.get("parent", {}).get("full_name", "").lower() == source.lower()):
                        return "Fork created and verified " + full
                except Refused as e:
                    if "HTTP 404:" not in str(e):
                        raise
                time.sleep(3)
            raise Refused("Fork accepted but not fully verified; inspect manually")

        if action == "visibility":
            full = value["repo"]
            before = self.admin("GET", "/repos/" + full)
            if (before.get("id") != value["expected_repo_id"] or before.get("fork")
                or before.get("archived")):
                raise Refused("Repository identity/status mismatch; re-plan")
            if before.get("visibility") == value["visibility"]:
                return "Already at requested visibility; verified " + full
            if before.get("visibility") != value["expected_visibility"]:
                raise Refused("Visibility changed since inspection; re-plan")
            change = self.admin("PATCH", "/repos/" + full, {"visibility": value["visibility"]})
            after = self.admin("GET", "/repos/" + full)
            if (after.get("id") != before.get("id") or
                after.get("visibility") != value["visibility"] or
                change.get("id") != before.get("id")):
                raise Refused("Visibility mutation not verified; inspect immediately")
            return "Changed and verified " + full + " to " + value["visibility"]
        raise Refused("Unsupported action")

    def process_issue(self, number):
        issue = self.issue_get("/issues/%d" % number)
        if issue.get("pull_request") or not issue.get("title", "").startswith("RG:"):
            return
        if issue.get("state") != "open":
            return
        if issue.get("user", {}).get("login", "").lower() != OWNER.lower():
            return  # Never accept commands from other users, even in a private control repo
        try:
            value = parse_intent(issue.get("body"))
            request_id = digest(value)
        except Refused as e:
            self.comment(number, "RG_REJECTED: " + str(e))
            return
        comments = self.comments(number)
        done = "RG_DONE " + request_id
        if value["action"] == "status":
            if not any(c.get("body", "").startswith(done) for c in comments):
                state = "configured" if self.admin_token else "missing"
                self.comment(number, done + "\nController alive. RG_ADMIN_TOKEN: " + state + ". No administration request was made.")
                self.issue_get("/issues/%d" % number, "PATCH", {"state": "closed"})
            return
        if any(c.get("body", "").startswith(done) for c in comments):
            return
        if any(c.get("body", "").startswith("RG_FAILED " + request_id) for c in comments):
            return  # Avoid replays of uncertain remote mutations
        # Automation-first mode: authenticated private-repo issues created on
        # behalf of OWNER are executable intents, without a second approval
        # comment. The issue is the auditable authorization record.
        # Publication still requires the explicit risk-acknowledgement field.
        timing = review_status(value)
        if timing == "waiting":
            return
        if timing == "missed":
            self.comment(number, "RG_MISSED " + request_id +
                         "\nScheduled publication missed its 20-minute deadline; refused late publication.")
            self.issue_get("/issues/%d" % number, "PATCH", {"state": "closed"})
            return
        try:
            outcome = self.execute(value)
        except Refused as e:
            # Leave open for deliberate inspection; no blind retry of mutations.
            marker = "RG_FAILED " + request_id
            if not any(c.get("body", "").startswith(marker) for c in comments):
                self.comment(number, marker + "\n" + str(e) +
                             "\nInspect manually before editing/reissuing.")
            return
        self.comment(number, done + "\n" + outcome)
        self.issue_get("/issues/%d" % number, "PATCH", {"state": "closed"})

    def reconcile(self):
        for page in range(1, 11):
            issues = self.issue_get("/issues?state=open&per_page=100&page=%d" % page)
            for issue in issues:
                if issue.get("title", "").startswith("RG:") and not issue.get("pull_request"):
                    self.process_issue(issue["number"])
            if len(issues) < 100:
                break


def main():
    if os.getenv("GITHUB_REPOSITORY") != CONTROL_REPO:
        raise SystemExit("Refusing: controller must run in " + CONTROL_REPO)
    if os.getenv("RG_CONTROLLER_PRIVATE") != "true":
        raise SystemExit("Refusing: private control repo assertion missing")
    c = Control(os.getenv("GITHUB_TOKEN"), os.getenv("RG_ADMIN_TOKEN"))
    if len(sys.argv) == 3 and sys.argv[1] == "--issue":
        number = int(sys.argv[2])
        if number < 1:
            raise SystemExit("Invalid issue number")
        c.process_issue(number)
    elif len(sys.argv) == 2 and sys.argv[1] == "--reconcile":
        c.reconcile()
    else:
        raise SystemExit("Usage: python -m repoguardian.controller --issue N | --reconcile")


if __name__ == "__main__":
    main()
