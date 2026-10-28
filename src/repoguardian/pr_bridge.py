"""A constrained public upstream PR operation for the private Repo Guardian controller."""
import re
from urllib.parse import quote

REPO_PART = re.compile(r"[A-Za-z0-9_.-]{1,100}\Z")
BRANCH = re.compile(r"[A-Za-z0-9_-]+(?:/[A-Za-z0-9_.-]+)*\Z")
SHA = re.compile(r"[a-fA-F0-9]{40}\Z")


class PrRefused(Exception):
    pass


def repo(value):
    if not isinstance(value, str) or value.count("/") != 1:
        raise PrRefused("Expected owner/repo")
    owner, name = value.split("/")
    if (not REPO_PART.fullmatch(owner) or not REPO_PART.fullmatch(name)
            or owner in (".", "..") or name in (".", "..")):
        raise PrRefused("Invalid repository identifier")
    return value


def branch(value):
    if not isinstance(value, str) or len(value) > 140 or not BRANCH.fullmatch(value):
        raise PrRefused("Invalid branch name")
    if ".." in value or value.endswith(".") or "/." in value or value.startswith("."):
        raise PrRefused("Unsafe branch name")
    return value


def validate(value, owner):
    allowed = {"version", "action", "fork", "upstream", "head", "base",
               "expected_head_sha", "title", "body", "draft", "acknowledge_public_exposure"}
    if set(value) - allowed:
        raise PrRefused("Unsupported PR request fields")
    if value.get("action") != "open_pr" or value.get("version") != 1:
        raise PrRefused("Invalid PR intent")
    source = repo(value.get("fork"))
    target = repo(value.get("upstream"))
    if source.split("/")[0].lower() != owner.lower() or source.lower() == target.lower():
        raise PrRefused("PR head must be a fork owned by the controller owner")
    branch(value.get("head"))
    branch(value.get("base"))
    if not isinstance(value.get("expected_head_sha"), str) or not SHA.fullmatch(value["expected_head_sha"]):
        raise PrRefused("Supply the exact 40-character expected commit SHA")
    if not isinstance(value.get("title"), str) or not 8 <= len(value["title"]) <= 200:
        raise PrRefused("PR title must be 8-200 characters")
    if any(ord(c) < 32 and c not in "\t\n" for c in value["title"]):
        raise PrRefused("PR title has control characters")
    if not isinstance(value.get("body"), str) or not 20 <= len(value["body"]) <= 12000:
        raise PrRefused("PR body must be 20-12000 characters")
    if not isinstance(value.get("draft", False), bool):
        raise PrRefused("draft must be a boolean")
    if value.get("draft", False):
        raise PrRefused("Repo Guardian does not publish draft PRs")
    if value.get("acknowledge_public_exposure") is not True:
        raise PrRefused("Opening a public PR requires acknowledge_public_exposure: true")
    return value


def submit(value, admin, owner):
    """Verify fork relationship/head lease and verify created or existing PR."""
    validate(value, owner)
    # Publishing must use the owner's personal token, never a bot or another user.
    actor = admin("GET", "/user")
    if (not isinstance(actor, dict)
            or actor.get("login", "").lower() != owner.lower()
            or actor.get("type", "User") != "User"):
        raise PrRefused("Publishing an upstream PR requires the owner's personal GitHub token")
    source, target, head, base = (value[k] for k in ("fork", "upstream", "head", "base"))
    expected_sha = value["expected_head_sha"].lower()
    fork = admin("GET", "/repos/" + source)
    if (fork.get("fork") is not True or fork.get("private") is not False
            or fork.get("archived") or fork.get("full_name", "").lower() != source.lower()
            or fork.get("parent", {}).get("full_name", "").lower() != target.lower()):
        raise PrRefused("Head is not a verified public fork of the requested upstream")
    upstream = admin("GET", "/repos/" + target)
    if upstream.get("private") or upstream.get("archived") or upstream.get("full_name", "").lower() != target.lower():
        raise PrRefused("Upstream identity or availability mismatch")

    head_ref = admin("GET", "/repos/" + source + "/git/ref/heads/" + head)
    if head_ref.get("object", {}).get("sha", "").lower() != expected_sha:
        raise PrRefused("Head branch changed since review; inspect and reauthorize")
    base_ref = admin("GET", "/repos/" + target + "/git/ref/heads/" + base)
    if not SHA.fullmatch(base_ref.get("object", {}).get("sha", "")):
        raise PrRefused("Base branch cannot be verified")

    query = "head=" + quote(owner + ":" + head, safe="") + "&base=" + quote(base, safe="") + "&state=open&per_page=100"
    existing = admin("GET", "/repos/" + target + "/pulls?" + query)
    if not isinstance(existing, list):
        raise PrRefused("Could not enumerate existing PRs")
    if len(existing) >= 100:
        raise PrRefused("Existing PR enumeration is incomplete")
    if existing:
        if len(existing) != 1:
            raise PrRefused("More than one existing PR found for this head")
        created = existing[0]
    else:
        created = admin("POST", "/repos/" + target + "/pulls", {
            "title": value["title"], "body": value["body"],
            "head": owner + ":" + head, "base": base,
            "draft": False, "maintainer_can_modify": True,
        })
    number = created.get("number")
    if type(number) is not int or number <= 0:
        raise PrRefused("PR number missing; inspect upstream before retry")
    verified = admin("GET", "/repos/" + target + "/pulls/" + str(number))
    if (verified.get("state") != "open"
            or verified.get("head", {}).get("sha", "").lower() != expected_sha
            or verified.get("head", {}).get("repo", {}).get("full_name", "").lower() != source.lower()
            or verified.get("base", {}).get("repo", {}).get("full_name", "").lower() != target.lower()
            or verified.get("base", {}).get("ref") != base
            or verified.get("user", {}).get("login", "").lower() != owner.lower()
            or verified.get("draft") is not False):
        raise PrRefused("PR was created or found but failed identity/head verification")
    url = verified.get("html_url", "")
    if url != "https://github.com/" + target + "/pull/" + str(number):
        raise PrRefused("PR URL mismatch")
    # Keep public URLs out of private GitHub Actions bot status comments.
    # They create an unwanted cross-reference on the upstream conversation.
    return "Verified upstream pull request number " + str(number) + " (head " + expected_sha[:12] + ")"
