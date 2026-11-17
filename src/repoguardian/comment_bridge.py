"""Owner-authorized public PR comment, tied to a reviewed commit and prior comment."""
import hashlib
import re

from .pr_bridge import repo, SHA, PrRefused

COMMENT_HASH = re.compile(r"[0-9a-f]{64}\Z")


class CommentRefused(Exception):
    pass


def validate(value, owner):
    allowed = {"version", "action", "fork", "upstream", "pr_number",
               "expected_head_sha", "reply_to_comment_id", "expected_comment_author",
               "expected_comment_sha256", "body", "acknowledge_public_exposure"}
    if set(value) - allowed or value.get("version") != 1 or value.get("action") != "comment_pr":
        raise CommentRefused("Invalid PR comment request")
    try:
        source, target = repo(value.get("fork")), repo(value.get("upstream"))
    except PrRefused as e:
        raise CommentRefused(str(e)) from None
    if source.split("/")[0].lower() != owner.lower() or source.lower() == target.lower():
        raise CommentRefused("PR must originate from an owner-controlled upstream fork")
    if type(value.get("pr_number")) is not int or value["pr_number"] < 1:
        raise CommentRefused("Supply a positive PR number")
    if type(value.get("reply_to_comment_id")) is not int or value["reply_to_comment_id"] < 1:
        raise CommentRefused("Supply an existing maintainer comment ID")
    if not isinstance(value.get("expected_head_sha"), str) or not SHA.fullmatch(value["expected_head_sha"]):
        raise CommentRefused("Supply an exact reviewed head SHA")
    author = value.get("expected_comment_author")
    if (not isinstance(author, str) or not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})", author)
            or author.lower() == owner.lower()):
        raise CommentRefused("Supply the other comment author's exact GitHub login")
    digest = value.get("expected_comment_sha256")
    if not isinstance(digest, str) or not COMMENT_HASH.fullmatch(digest):
        raise CommentRefused("Supply the original comment's exact SHA-256")
    body = value.get("body")
    if (not isinstance(body, str) or not 20 <= len(body) <= 1000 or body.strip() != body
            or any(ord(c) < 32 and c not in "\t\n" for c in body)
            or any(ord(c) == 127 for c in body)):
        raise CommentRefused("Comment must be 20-1000 printable characters")
    if value.get("acknowledge_public_exposure") is not True:
        raise CommentRefused("Public reply requires explicit acknowledgement")
    return value


def submit(value, admin, owner):
    """Fail closed unless the user's existing open PR and reviewed comment still match."""
    validate(value, owner)
    actor = admin("GET", "/user")
    if (not isinstance(actor, dict) or actor.get("login", "").lower() != owner.lower()
            or actor.get("type") != "User"):
        raise CommentRefused("Public replies require the owner's personal GitHub token")

    source, target = value["fork"], value["upstream"]
    source_meta = admin("GET", "/repos/" + source)
    if (source_meta.get("fork") is not True or source_meta.get("private") is not False
            or source_meta.get("archived")
            or source_meta.get("full_name", "").lower() != source.lower()
            or source_meta.get("parent", {}).get("full_name", "").lower() != target.lower()):
        raise CommentRefused("Source is not the owner's public fork of this upstream")
    upstream_meta = admin("GET", "/repos/" + target)
    if (upstream_meta.get("private") or upstream_meta.get("archived")
            or upstream_meta.get("full_name", "").lower() != target.lower()):
        raise CommentRefused("Upstream identity mismatch")

    base_path = "/repos/" + target
    number = value["pr_number"]
    pr = admin("GET", base_path + "/pulls/" + str(number))
    if (pr.get("number") != number or pr.get("state") != "open" or pr.get("draft") is not False
            or pr.get("user", {}).get("login", "").lower() != owner.lower()
            or pr.get("head", {}).get("sha", "").lower() != value["expected_head_sha"].lower()
            or pr.get("head", {}).get("repo", {}).get("full_name", "").lower() != source.lower()
            or pr.get("base", {}).get("repo", {}).get("full_name", "").lower() != target.lower()
            or pr.get("html_url") != "https://github.com/" + target + "/pull/" + str(number)):
        raise CommentRefused("PR author, state, fork, or reviewed head changed")

    comment_id = value["reply_to_comment_id"]
    prior = admin("GET", base_path + "/issues/comments/" + str(comment_id))
    if (prior.get("id") != comment_id
            or prior.get("issue_url") != "https://api.github.com" + base_path + "/issues/" + str(number)
            or prior.get("user", {}).get("login", "").lower() != value["expected_comment_author"].lower()
            or hashlib.sha256((prior.get("body") or "").encode()).hexdigest()
            != value["expected_comment_sha256"]):
        raise CommentRefused("Original comment changed or is from another PR or author")

    # Search BEFORE POST. If an earlier run succeeded but lost its response,
    # a controller retry must not post another copy of the same reply.
    for page in range(1, 11):
        existing = admin("GET", base_path + "/issues/" + str(number) +
                         "/comments?per_page=100&page=" + str(page))
        if not isinstance(existing, list):
            raise CommentRefused("Could not verify existing PR comments")
        for item in existing:
            if (item.get("user", {}).get("login", "").lower() == owner.lower()
                    and item.get("body") == value["body"]):
                return "Public reply already exists and was verified on pull request " + str(number)
        if len(existing) < 100:
            break
    else:
        raise CommentRefused("Comment enumeration exceeded 1000 entries; refusing duplicate risk")

    created = admin("POST", base_path + "/issues/" + str(number) + "/comments",
                    {"body": value["body"]})
    created_id = created.get("id")
    if type(created_id) is not int or created_id < 1:
        raise CommentRefused("Reply POST returned no comment ID; inspect before retry")
    verified = admin("GET", base_path + "/issues/comments/" + str(created_id))
    if (verified.get("id") != created_id or verified.get("body") != value["body"]
            or verified.get("user", {}).get("login", "").lower() != owner.lower()
            or verified.get("issue_url") != "https://api.github.com" + base_path + "/issues/" + str(number)):
        raise CommentRefused("Reply posted but post-write verification failed")
    # Keep public links out of the controller's bot status comments.
    return "Verified owner-authored public reply on pull request " + str(number) + " (comment " + str(created_id) + ")"
