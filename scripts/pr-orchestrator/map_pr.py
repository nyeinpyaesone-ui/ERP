"""Map one PR into a deterministic, evidence-backed eligibility report."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections.abc import Iterable
from typing import Any
from urllib.parse import urlencode

from client import api_get, api_paginate, api_paginate_field, repo_api_path, write_json

ALLOWED_CHECK_CONCLUSIONS = {"success", "skipped", "neutral"}
RISK_ORDER = {
    "documentation": 1,
    "dependency": 2,
    "frontend": 3,
    "backend": 4,
    "application": 5,
    "infrastructure": 6,
}


def latest_check_runs(check_runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep the newest observation for each check name and GitHub App."""
    latest: dict[tuple[str, int | None], dict[str, Any]] = {}
    for check in check_runs:
        app_id = (check.get("app") or {}).get("id")
        key = (str(check.get("name", "unnamed")), app_id)
        timestamp = check.get("completed_at") or check.get("started_at") or ""
        previous = latest.get(key)
        previous_timestamp = (
            previous.get("completed_at") or previous.get("started_at") or ""
            if previous
            else ""
        )
        if previous is None or timestamp >= previous_timestamp:
            latest[key] = check
    return list(latest.values())


def classify_risk(paths: Iterable[str]) -> str:
    files = list(paths)
    if not files:
        return "application"
    infrastructure_prefixes = (
        ".github/",
        "infra/",
        "scripts/",
        "docker/",
    )
    infrastructure_files = {
        "Dockerfile",
        "docker-compose.yml",
        "docker-compose.prod.yml",
        "nginx.conf",
        "install.sh",
    }
    if any(
        path.startswith(infrastructure_prefixes)
        or path in infrastructure_files
        or path.endswith((".workflow",))
        for path in files
    ):
        return "infrastructure"
    dependency_names = (
        "requirements.txt",
        "requirements-runtime.txt",
        "pyproject.toml",
        "poetry.lock",
        "Pipfile.lock",
        "package.json",
        "package-lock.json",
        "pnpm-lock.yaml",
        "yarn.lock",
        "Cargo.toml",
        "Cargo.lock",
        "go.mod",
        "go.sum",
    )
    if any(
        path.endswith(dependency_names)
        or path.startswith(".github/dependabot")
        for path in files
    ):
        return "dependency"
    if all(
        path.startswith(("docs/", ".opencode/", "AGENTS PROFILE/"))
        or path in {"README.md", "CHANGELOG.md", "CONTRIBUTING.md"}
        for path in files
    ):
        return "documentation"
    if any(path.startswith("backend/frontend-react/") for path in files):
        return "frontend"
    if any(path.startswith(("backend/app/", "backend/alembic/")) for path in files):
        return "backend"
    return "application"


def _latest_reviews_by_user(reviews: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for review in reviews:
        user = review.get("user", {}).get("login")
        if not user or review.get("state") in {"PENDING", "DISMISSED"}:
            continue
        previous = latest.get(user)
        timestamp = review.get("submitted_at") or ""
        if previous is None or timestamp >= (previous.get("submitted_at") or ""):
            latest[user] = review
    return latest


def evaluate_pr(
    pr: dict[str, Any],
    check_runs: list[dict[str, Any]],
    combined_status: dict[str, Any],
    reviews: list[dict[str, Any]],
    files: list[dict[str, Any]],
    expected_head_sha: str,
    expected_base_sha: str,
    repository: str,
) -> dict[str, Any]:
    """Pure eligibility evaluation; GitHub remains the final merge authority."""
    reasons: list[str] = []
    number = int(pr.get("number", 0))
    head_sha = pr.get("head", {}).get("sha", "")
    base_sha = pr.get("base", {}).get("sha", "")
    base_ref = pr.get("base", {}).get("ref", "")
    head_repo = pr.get("head", {}).get("repo") or {}
    changed_files = sorted(
        {str(item.get("filename", "")) for item in files if item.get("filename")}
    )

    if pr.get("state") != "open":
        reasons.append("pr_not_open")
    if pr.get("draft"):
        reasons.append("draft_pr")
    if base_ref != "main":
        reasons.append("base_not_main")
    if (head_repo.get("full_name") or "") != repository:
        reasons.append("head_repository_is_not_internal")
    if head_sha != expected_head_sha:
        reasons.append("head_sha_changed")
    if base_sha != expected_base_sha:
        reasons.append("base_sha_changed_during_discovery")
    if pr.get("mergeable") is not True:
        reasons.append("mergeability_not_confirmed")
    if pr.get("mergeable_state") != "clean":
        reasons.append(f"mergeable_state_{pr.get('mergeable_state') or 'unknown'}")
    if not changed_files:
        reasons.append("changed_files_unavailable_or_empty")

    effective_checks = latest_check_runs(check_runs)
    if not effective_checks:
        reasons.append("check_runs_missing")
    else:
        incomplete = [
            run.get("name", "unnamed")
            for run in effective_checks
            if run.get("status") != "completed"
            or run.get("conclusion") not in ALLOWED_CHECK_CONCLUSIONS
        ]
        if incomplete:
            reasons.append("checks_not_green:" + ",".join(sorted(set(incomplete))))

    # GitHub's classic commit-status API is independent of Actions check-runs.
    # A pending combined status with zero contexts is not a failure when the
    # check-runs API above contains completed successful checks.
    classic_statuses = combined_status.get("statuses") or []
    if classic_statuses and combined_status.get("state") != "success":
        reasons.append(
            f"commit_status_{combined_status.get('state') or 'missing'}"
        )

    latest_reviews = _latest_reviews_by_user(reviews)
    requested_changes = [
        user
        for user, review in latest_reviews.items()
        if review.get("state") == "CHANGES_REQUESTED"
    ]
    if requested_changes:
        reasons.append("changes_requested:" + ",".join(sorted(requested_changes)))
    approvals = sorted(
        user
        for user, review in latest_reviews.items()
        if review.get("state") == "APPROVED"
    )

    risk = classify_risk(changed_files)
    return {
        "schema_version": 1,
        "number": number,
        "title": pr.get("title", ""),
        "url": pr.get("html_url", ""),
        "head_sha": head_sha,
        "base_sha": base_sha,
        "base_ref": base_ref,
        "mergeable_state": pr.get("mergeable_state"),
        "risk": risk,
        "risk_order": RISK_ORDER[risk],
        "changed_files": changed_files,
        "approved_reviewers": approvals,
        "approval_count": len(approvals),
        "eligible": not reasons,
        "status": "eligible" if not reasons else "blocked",
        "reasons": reasons,
        "updated_at": pr.get("updated_at"),
    }


def build_pr_report(
    number: int,
    expected_head_sha: str,
    expected_base_sha: str,
    repository: str,
) -> dict[str, Any]:
    token_query = urlencode({"per_page": 100})
    pr = api_get(repo_api_path(f"/pulls/{number}"))
    for _ in range(5):
        if pr.get("mergeable") is not None:
            break
        time.sleep(2)
        pr = api_get(repo_api_path(f"/pulls/{number}"))
    head_sha = pr.get("head", {}).get("sha", "")
    checks = api_paginate_field(
        repo_api_path(f"/commits/{head_sha}/check-runs") + f"?{token_query}",
        "check_runs",
    )
    combined_status = api_get(
        repo_api_path(f"/commits/{head_sha}/status")
    )
    reviews = api_paginate(
        repo_api_path(f"/pulls/{number}/reviews") + f"?{token_query}"
    )
    files = api_paginate(
        repo_api_path(f"/pulls/{number}/files") + f"?{token_query}"
    )
    return evaluate_pr(
        pr,
        checks,
        combined_status,
        reviews,
        files,
        expected_head_sha,
        expected_base_sha,
        repository,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--number", type=int, required=True)
    parser.add_argument("--expected-head", required=True)
    parser.add_argument("--expected-base", required=True)
    parser.add_argument("--output", default="map-report.json")
    args = parser.parse_args()

    repository = os.environ.get("GITHUB_REPOSITORY", "")
    try:
        report = build_pr_report(
            args.number, args.expected_head, args.expected_base, repository
        )
    except Exception as error:
        report = {
            "schema_version": 1,
            "number": args.number,
            "head_sha": args.expected_head,
            "base_sha": args.expected_base,
            "eligible": False,
            "status": "blocked",
            "risk": "unknown",
            "risk_order": 99,
            "changed_files": [],
            "reasons": [f"map_worker_error:{type(error).__name__}:{error}"],
        }
    write_json(args.output, report)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
