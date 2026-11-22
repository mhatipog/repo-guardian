"""Read-only, offline evidence gate for security-fix downstream impact studies.

Never executes a target repository, downloads dependencies, publishes findings,
or interprets a recorded test matrix as independent proof of production impact.
"""
from __future__ import annotations

import hashlib
import json
import re
import tomllib
from pathlib import Path
from typing import Any


class EvidenceError(ValueError):
    """Invalid or ungrounded evidence inputs."""


_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*")
_SHA = re.compile(r"^[0-9a-f]{40}$")
_SYMBOL = re.compile(r"^[A-Za-z_][A-Za-z_0-9.]*$")
_EXPECTED = {
    "positive": ("accept", "accept"),
    "negative": ("reject", "reject"),
    "defect": ("accept", "reject"),
}


def _name(value: str) -> str:
    match = _NAME.match(value.strip())
    if match is None:
        raise EvidenceError("Expected a valid package name")
    return re.sub(r"[-_.]+", "-", match.group(0)).lower()


def _file(path: Path, *, root: Path | None = None, limit: int = 2_000_000) -> bytes:
    resolved = path.resolve(strict=True)
    if root is not None and not resolved.is_relative_to(root.resolve(strict=True)):
        raise EvidenceError("The callsite must be inside the selected project")
    if not resolved.is_file() or resolved.stat().st_size > limit:
        raise EvidenceError("Expected a regular bounded-size evidence file")
    return resolved.read_bytes()


def _mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise EvidenceError(f"{label} must be a JSON object")
    return value


def _case_gates(raw_cases: Any) -> tuple[dict[str, bool], list[str]]:
    if not isinstance(raw_cases, list) or not 1 <= len(raw_cases) <= 64:
        raise EvidenceError("cases must be a list of 1-64 recorded controls")
    seen: set[str] = set()
    checks = {role: False for role in _EXPECTED}
    faults = []
    for case in raw_cases:
        case = _mapping(case, "case")
        name = case.get("name")
        role = case.get("role")
        before, after = case.get("vulnerable"), case.get("fixed")
        if not isinstance(name, str) or not name.strip() or name in seen:
            raise EvidenceError("Case names must be nonempty and unique")
        seen.add(name)
        if role not in _EXPECTED:
            raise EvidenceError("Case role must be positive, negative, or defect")
        if before not in ("accept", "reject") or after not in ("accept", "reject"):
            raise EvidenceError("Outcomes must be accept or reject")
        if (before, after) != _EXPECTED[role]:
            faults.append(f"Case {name!r} contradicts {role} control")
        else:
            checks[role] = True
    return checks, faults


def analyze(
    project: str | Path,
    callsite: str,
    symbol: str,
    matrix_path: str | Path,
) -> dict[str, Any]:
    """Check local dependency/callsite evidence and a recorded CI test matrix.

    Returns a decision record; never treats user-supplied CI outcomes as newly
    executed tests. The caller must independently inspect the referenced run.
    """
    root = Path(project).resolve(strict=True)
    if not root.is_dir():
        raise EvidenceError("Project must be a directory")
    if not isinstance(symbol, str) or not _SYMBOL.fullmatch(symbol):
        raise EvidenceError("Expected a Python symbol or identifier")
    source = _file(root / callsite, root=root)
    manifest = _file(root / "pyproject.toml", root=root)
    lock = _file(root / "uv.lock", root=root)
    raw = _mapping(json.loads(_file(Path(matrix_path))), "evidence matrix")
    if raw.get("schema_version") != 1:
        raise EvidenceError("Unsupported evidence schema")
    package = raw.get("package")
    if not isinstance(package, str):
        raise EvidenceError("Missing package")
    package = _name(package)
    dependencies = tomllib.loads(manifest.decode("utf-8")).get("project", {}).get("dependencies", [])
    if not isinstance(dependencies, list):
        raise EvidenceError("Missing project dependencies")
    direct = [d for d in dependencies if isinstance(d, str) and _name(d) == package]
    locked = [
        p for p in tomllib.loads(lock.decode("utf-8")).get("package", [])
        if isinstance(p, dict) and _name(str(p.get("name", ""))) == package
    ]
    if len(locked) != 1:
        raise EvidenceError("Expected exactly one selected package version in uv.lock")
    fixed_version = raw.get("fixed_version")
    commit = raw.get("downstream_commit")
    ci = raw.get("ci_run_url")
    tests = _mapping(raw.get("test_summary"), "test_summary")
    case_checks, faults = _case_gates(raw.get("cases"))
    gates = {
        "direct_dependency": bool(direct),
        "callsite_candidate": symbol.encode("utf-8") in source,
        "locked_version_differs_from_fix": (
            isinstance(fixed_version, str) and bool(fixed_version)
            and locked[0].get("version") != fixed_version
        ),
        "source_commit_documented": isinstance(commit, str) and bool(_SHA.fullmatch(commit)),
        "ci_run_documented": isinstance(ci, str) and ci.startswith("https://github.com/"),
        "positive_control": case_checks["positive"],
        "negative_control": case_checks["negative"],
        "false_acceptance_control": case_checks["defect"],
        "regressions_reported_passing": (
            type(tests.get("passed")) is int and tests["passed"] > 0
            and type(tests.get("failed")) is int and tests["failed"] == 0
        ),
    }
    ready = all(gates.values()) and not faults
    return {
        "schema_version": 1,
        "package": package,
        "recorded_locked_version": locked[0]["version"],
        "recorded_fixed_version": fixed_version,
        "source_sha256": hashlib.sha256(source).hexdigest(),
        "manifest_sha256": hashlib.sha256(manifest).hexdigest(),
        "lock_sha256": hashlib.sha256(lock).hexdigest(),
        "gates": gates,
        "matrix_errors": faults,
        "ready_for_coordinated_remediation": ready,
        "next_step": (
            "Independently review the linked CI job and prepare a narrowly scoped fix."
            if ready else "Resolve missing evidence gates and inconsistent test outcomes."
        ),
        "limitation": (
            "This read-only tool validates the consistency of recorded evidence. "
            "It does not execute test cases, verify GitHub logs, demonstrate an "
            "externally exploitable path, or establish production deployment."
        ),
    }
