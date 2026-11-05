"""Constrained, idempotent upstream issue publication from an owned public fork.

Only the controller owner's personal token may publish. An exact fork-parent and
reviewed commit check prevents the private controller from becoming a general
arbitrary-issue posting API. Never return linkable upstream URLs in bot comments.
"""
from .pr_bridge import PrRefused, branch, repo, SHA


class IssueRefused(Exception):
    pass


def validate(value, owner):
    allowed = {"version", "action", "fork", "upstream", "head",
               "expected_head_sha", "title", "body", "acknowledge_public_exposure"}
    if set(value) - allowed or value.get("version") != 1 or value.get("action") != "open_issue":
        raise IssueRefused("Invalid upstream issue request")
    try:
        source, target = repo(value.get("fork")), repo(value.get("upstream"))
        branch(value.get("head"))
    except PrRefused as exc:
        raise IssueRefused(str(exc)) from None
    if source.split("/")[0].lower() != owner.lower() or source.lower() == target.lower():
        raise IssueRefused("Issue must be associated with an owner-controlled upstream fork")
    if not isinstance(value.get("expected_head_sha"), str) or not SHA.fullmatch(value["expected_head_sha"]):
        raise IssueRefused("Supply the reviewed head's exact 40-character SHA")
    title = value.get("title")
    if not isinstance(title, str) or not 8 <= len(title) <= 200 or title.strip() != title:
        raise IssueRefused("Issue title must contain 8–200 printable characters")
    if any(ord(c) < 32 or ord(c) == 127 for c in title):
        raise IssueRefused("Issue title must be a single line")
    body = value.get("body")
    if not isinstance(body, str) or not 100 <= len(body) <= 12000:
        raise IssueRefused("Issue body must be 100–12000 characters")
    if value.get("acknowledge_public_exposure") is not True:
        raise IssueRefused("Public issue creation requires acknowledgement")
    return value


def submit(value, admin, owner):
    """Verify the owner, fork, head lease, and issue identity before/after POST."""
    validate(value, owner)
    actor = admin("GET", "/user")
    if (not isinstance(actor, dict) or actor.get("login", "").lower() != owner.lower()
            or actor.get("type") != "User"):
        raise IssueRefused("Issue publication requires the owner's personal token")
    source, target = value["fork"], value["upstream"]
    fork = admin("GET", "/repos/" + source)
    if (fork.get("fork") is not True or fork.get("private") is not False
            or fork.get("archived") or fork.get("full_name", "").lower() != source.lower()
            or fork.get("parent", {}).get("full_name", "").lower() != target.lower()):
        raise IssueRefused("Source is not the owner's public fork of the requested upstream")
    upstream = admin("GET", "/repos/" + target)
    if (upstream.get("private") or upstream.get("archived")
            or not upstream.get("has_issues", False)
            or upstream.get("full_name", "").lower() != target.lower()):
        raise IssueRefused("Upstream is not a writable public issue destination")
    head_ref = admin("GET", "/repos/" + source + "/git/ref/heads/" + value["head"])
    if head_ref.get("object", {}).get("sha", "").lower() != value["expected_head_sha"].lower():
        raise IssueRefused("Head branch differs from reviewed SHA; refusing publication")

    # POST can succeed while the controller times out before recording RG_DONE.
    # Check recent issues before creating to keep reconciliation idempotent.
    recent = admin("GET", "/repos/" + target + "/issues?state=all&per_page=100")
    if not isinstance(recent, list):
        raise IssueRefused("Could not enumerate recent issues")
    matches = [issue for issue in recent if issue.get("title") == value["title"]
               and not issue.get("pull_request")]
    if len(matches) > 1:
        raise IssueRefused("Multiple same-title upstream issues; review manually")
    if matches:
        found = matches[0]
        if (found.get("user", {}).get("login", "").lower() != owner.lower()
                or found.get("body") != value["body"]):
            raise IssueRefused("An issue with this title already exists; review manually")
    else:
        found = admin("POST", "/repos/" + target + "/issues",
                      {"title": value["title"], "body": value["body"]})
    number = found.get("number")
    if type(number) is not int or number < 1:
        raise IssueRefused("GitHub did not return a valid issue number")
    issue = admin("GET", "/repos/" + target + "/issues/" + str(number))
    if (issue.get("number") != number or issue.get("pull_request")
            or issue.get("state") != "open"
            or issue.get("title") != value["title"] or issue.get("body") != value["body"]
            or issue.get("user", {}).get("login", "").lower() != owner.lower()
            or issue.get("html_url") != "https://github.com/" + target + "/issues/" + str(number)):
        raise IssueRefused("Upstream issue failed post-write verification")
    return "Verified upstream issue number " + str(number) + " (reviewed head " + value["expected_head_sha"][:12] + ")"
