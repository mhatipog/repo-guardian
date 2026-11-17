"""Private vulnerability reporting for third-party GitHub repositories.

The request lives only in the private controller repository. Never fall back to
GitHub's public issues, pull requests, or maintainer-only advisory endpoint.
"""
import re

from .pr_bridge import repo, PrRefused


class SecurityReportRefused(Exception):
    pass


GHSA = re.compile(r"GHSA-[a-zA-Z0-9]{4}-[a-zA-Z0-9]{4}-[a-zA-Z0-9]{4}\\Z")
CWE = re.compile(r"CWE-[1-9][0-9]{0,5}\\Z")
ECOSYSTEMS = frozenset({
    "rubygems", "npm", "pip", "maven", "nuget", "composer",
    "go", "rust", "erlang", "actions", "pub", "other", "swift",
})


def validate(value, owner):
    """Fail closed on malformed or public-facing requests."""
    allowed = {
        "version", "action", "upstream", "summary", "description",
        "severity", "cwe_ids", "vulnerabilities",
        "acknowledge_private_submission",
    }
    if (not isinstance(value, dict) or set(value) - allowed
            or value.get("version") != 1
            or value.get("action") != "report_vulnerability"):
        raise SecurityReportRefused("Invalid private security report request")
    try:
        target = repo(value.get("upstream"))
    except PrRefused as exc:
        raise SecurityReportRefused(str(exc)) from None
    if target.split("/")[0].casefold() == owner.casefold():
        raise SecurityReportRefused(
            "This action is for reporting to third-party repositories; "
            "use the maintainer advisory workflow for owned repositories"
        )
    summary = value.get("summary")
    if (not isinstance(summary, str) or not 12 <= len(summary) <= 180
            or summary != summary.strip() or any(ord(c) < 32 for c in summary)):
        raise SecurityReportRefused("Summary must be a single line of 12-180 characters")
    description = value.get("description")
    if (not isinstance(description, str)
            or not 300 <= len(description) <= 28000
            or any(x in description for x in ("\\x00", "\\r"))):
        raise SecurityReportRefused("Description must be 300-28000 characters of Markdown")
    for section in ("## Summary", "## Details", "## Proof of concept", "## Impact"):
        if section not in description:
            raise SecurityReportRefused("Missing report section: " + section)
    if value.get("acknowledge_private_submission") is not True:
        raise SecurityReportRefused("Private submission requires explicit acknowledgement")
    severity = value.get("severity")
    if severity is not None and severity not in {"low", "medium", "high", "critical"}:
        raise SecurityReportRefused("Severity must be low, medium, high, critical, or null")
    cwe_ids = value.get("cwe_ids", [])
    if (not isinstance(cwe_ids, list) or len(cwe_ids) > 5 or
            any(not isinstance(x, str) or not CWE.fullmatch(x) for x in cwe_ids) or
            len(set(cwe_ids)) != len(cwe_ids)):
        raise SecurityReportRefused("Invalid CWE identifiers")
    vulns = value.get("vulnerabilities", [])
    if not isinstance(vulns, list) or len(vulns) > 3:
        raise SecurityReportRefused("Limit affected packages to three")
    for v in vulns:
        if not isinstance(v, dict) or set(v) - {
            "package", "vulnerable_version_range", "patched_versions", "vulnerable_functions"
        }:
            raise SecurityReportRefused("Unsupported package fields")
        p = v.get("package")
        if (not isinstance(p, dict) or set(p) != {"ecosystem", "name"}
                or p.get("ecosystem") not in ECOSYSTEMS
                or not isinstance(p.get("name"), str)
                or not 1 <= len(p["name"]) <= 200):
            raise SecurityReportRefused("Invalid package descriptor")
        for key in ("vulnerable_version_range", "patched_versions"):
            if key in v and (not isinstance(v[key], str) or len(v[key]) > 150):
                raise SecurityReportRefused("Invalid " + key)
        if "vulnerable_functions" in v:
            fn = v["vulnerable_functions"]
            if (not isinstance(fn, list) or len(fn) > 10 or any(
                    not isinstance(x, str) or not 1 <= len(x) <= 150 for x in fn)):
                raise SecurityReportRefused("Invalid vulnerable_functions")
    return value


def submit(value, admin, owner):
    """Submit once to GitHub's researcher reporting endpoint.

    No retries after an uncertain POST. The outer controller records RG_FAILED
    and prevents another reconciliation from creating duplicate reports.
    """
    validate(value, owner)
    actor = admin("GET", "/user")
    if (not isinstance(actor, dict)
            or actor.get("login", "").casefold() != owner.casefold()
            or actor.get("type") != "User"):
        raise SecurityReportRefused("Requires controller owner's personal GitHub token")

    upstream = value["upstream"]
    metadata = admin("GET", "/repos/" + upstream)
    if (not isinstance(metadata, dict)
            or metadata.get("full_name", "").casefold() != upstream.casefold()
            or metadata.get("private") is not False
            or metadata.get("archived") is True):
        raise SecurityReportRefused("Target must be the exact public, active repository")

    payload = {"summary": value["summary"], "description": value["description"]}
    for key in ("severity", "cwe_ids", "vulnerabilities"):
        if key in value:
            payload[key] = value[key]
    # Important: /reports is a PRIVATE research report; /security-advisories
    # is for maintainers and /issues is PUBLIC. Never substitute either one.
    endpoint = "/repos/" + upstream + "/security-advisories/reports"
    created = admin("POST", endpoint, payload)
    if (not isinstance(created, dict)
            or not isinstance(created.get("ghsa_id"), str)
            or not GHSA.fullmatch(created["ghsa_id"])
            or created.get("summary") != value["summary"]):
        raise SecurityReportRefused(
            "Submission response was unexpected; it might have succeeded. "
            "Inspect security advisories manually; do not retry"
        )
    author = created.get("author")
    if isinstance(author, dict) and author.get("login", "").casefold() != owner.casefold():
        raise SecurityReportRefused("Unexpected reporter identity; inspect manually")
    state = created.get("state")
    if state not in ("triage", "draft", None):
        raise SecurityReportRefused("Unexpected report state; inspect manually")
    return "Private vulnerability report accepted: " + created["ghsa_id"]
