"""Serial, fail-closed PR merge executor with a main-CI event barrier."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from typing import Any
from urllib.parse import urlencode

from client import GitHubAPIError, api_get, api_post, repo_api_path, write_json
from map_pr import build_pr_report


def gh_merge_or_enqueue(
    number: int, repository: str, expected_head: str
) -> tuple[bool, str]:
    """Ask GitHub to merge or enqueue a PR without bypassing repository rules."""
    if not shutil.which("gh"):
        return False, "GitHub CLI is unavailable on this runner"
    token = os.environ.get("PR_ORCHESTRATOR_TOKEN", "")
    if not token:
        return False, "PR_ORCHESTRATOR_TOKEN is missing"
    env = os.environ.copy()
    env["GH_TOKEN"] = token
    command = [
        "gh",
        "pr",
        "merge",
        str(number),
        "--repo",
        repository,
        "--squash",
        "--match-head-commit",
        expected_head,
    ]
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=60,
            env=env,
        )
    except subprocess.TimeoutExpired:
        return False, "GitHub CLI merge request timed out"
    if completed.returncode != 0:
        detail = (
            completed.stderr or completed.stdout or "unknown GitHub CLI error"
        ).strip()
        return False, f"GitHub refused merge/queue request: {detail[-1200:]}"
    return (
        True,
        (completed.stdout or "GitHub accepted merge/auto-merge request").strip(),
    )


def wait_for_pr_merge(
    number: int, timeout_seconds: int, poll_seconds: int = 10
) -> tuple[bool, str, str]:
    """Wait for GitHub or its merge queue to complete the requested merge."""
    deadline = time.monotonic() + timeout_seconds
    last_state = "merge request accepted; waiting for GitHub merge requirements"
    while time.monotonic() < deadline:
        pr = api_get(repo_api_path(f"/pulls/{number}"))
        if pr.get("merged") is True:
            merge_sha = str(pr.get("merge_commit_sha") or "")
            if merge_sha:
                return True, merge_sha, "GitHub confirmed the PR merge"
            return (
                False,
                "",
                "GitHub reports merged but did not return merge_commit_sha",
            )
        if pr.get("state") != "open":
            return (
                False,
                "",
                f"PR left the open state without a confirmed merge ({pr.get('state')})",
            )
        auto_merge = pr.get("auto_merge")
        last_state = (
            "GitHub auto-merge enabled; waiting for required checks/reviews"
            if auto_merge
            else "PR remains open; waiting for merge-queue or repository policy"
        )
        time.sleep(min(poll_seconds, max(1, deadline - time.monotonic())))
    return False, "", f"merge/queue wait timed out: {last_state}"


def wait_for_main_ci(
    merge_sha: str, timeout_seconds: int, poll_seconds: int = 15
) -> tuple[bool, str]:
    deadline = time.monotonic() + timeout_seconds
    run: dict[str, Any] | None = None
    while time.monotonic() < deadline:
        query = urlencode({"head_sha": merge_sha, "per_page": 100})
        candidates = api_get(repo_api_path("/actions/runs") + f"?{query}")
        matches = [
            item
            for item in candidates.get("workflow_runs", [])
            if item.get("name") == "CI"
            and item.get("event") == "push"
            and item.get("head_branch") == "main"
        ]
        if matches:
            run = max(matches, key=lambda item: item.get("created_at", ""))
            run = api_get(repo_api_path(f"/actions/runs/{run['id']}"))
            if run.get("status") == "completed":
                conclusion = run.get("conclusion") or "unknown"
                return conclusion == "success", (
                    f"CI run {run['id']} completed with {conclusion}"
                )
        time.sleep(min(poll_seconds, max(1, deadline - time.monotonic())))
    run_id = run.get("id") if run else "not-created"
    return False, f"main CI did not complete successfully before timeout (run={run_id})"


def dispatch_and_wait_for_staging(timeout_seconds: int) -> tuple[bool, str]:
    query = urlencode({"branch": "main", "event": "workflow_dispatch", "per_page": 100})
    before = api_get(repo_api_path("/actions/runs") + f"?{query}")
    previous_ids = {
        int(item["id"])
        for item in before.get("workflow_runs", [])
        if item.get("name") == "CI"
    }
    api_post(
        repo_api_path("/actions/workflows/ci.yml/dispatches"),
        {"ref": "main", "inputs": {"deploy_staging": "true"}},
    )
    deadline = time.monotonic() + timeout_seconds
    workflow_run: dict[str, Any] | None = None

    while time.monotonic() < deadline:
        response = api_get(repo_api_path("/actions/runs") + f"?{query}")
        candidates = [
            item
            for item in response.get("workflow_runs", [])
            if item.get("name") == "CI" and int(item.get("id", 0)) not in previous_ids
        ]
        if candidates:
            workflow_run = max(candidates, key=lambda item: int(item["id"]))
            workflow_run = api_get(repo_api_path(f"/actions/runs/{workflow_run['id']}"))
            if workflow_run.get("status") == "completed":
                run_id = workflow_run["id"]
                jobs_response = api_get(
                    repo_api_path(f"/actions/runs/{run_id}/jobs?per_page=100")
                )
                jobs = jobs_response.get("jobs", [])
                staging = next(
                    (job for job in jobs if job.get("name") == "Deploy to Staging"),
                    None,
                )
                if staging and staging.get("conclusion") == "success":
                    return True, f"staging deployment succeeded in run {run_id}"
                conclusion = staging.get("conclusion") if staging else "job_missing"
                return False, (
                    f"CI run {run_id} completed but staging deployment was "
                    f"{conclusion}"
                )
        time.sleep(min(15, max(1, deadline - time.monotonic())))

    run_id = workflow_run.get("id") if workflow_run else "not-created"
    return False, f"staging deployment did not complete before timeout (run={run_id})"


def verify_main_merge_policy() -> tuple[bool, str]:
    """Require active main-branch review and strict status-check protection."""
    try:
        protection = api_get(repo_api_path("/branches/main/protection"))
    except GitHubAPIError as error:
        return (
            False,
            f"main branch protection could not be verified (GitHub API {error.status}); refusing merge",
        )

    enforce_admins = protection.get("enforce_admins") or {}
    reviews = protection.get("required_pull_request_reviews") or {}
    required_approvals = int(reviews.get("required_approving_review_count") or 0)
    status_checks = protection.get("required_status_checks") or {}
    required_contexts = set(status_checks.get("contexts") or [])
    required_check_names = {
        str(item.get("context") or item.get("app_id") or "")
        for item in status_checks.get("checks") or []
        if item.get("context") or item.get("app_id")
    }

    if not enforce_admins.get("enabled"):
        return (
            False,
            "main branch protection must enforce rules for administrators; refusing merge",
        )
    if required_approvals < 1:
        return (
            False,
            "main branch protection must require at least one approving review; refusing merge",
        )
    if not required_contexts and not required_check_names:
        return (
            False,
            "main branch protection must require at least one status check; refusing merge",
        )
    if status_checks.get("strict") is not True:
        return (
            False,
            "main branch protection must require branches to be up to date before merging; refusing merge",
        )
    required_checks_count = len(required_contexts | required_check_names)
    return (
        True,
        f"main protection verified: administrator enforcement enabled, "
        f"{required_approvals} required approval(s), "
        f"{required_checks_count} required status check(s), strict checks enabled",
    )


def execute(
    plan: list[dict[str, Any]], timeout_minutes: int, deploy_staging: bool
) -> dict[str, Any]:
    repository = os.environ["GITHUB_REPOSITORY"]
    timeout_seconds = timeout_minutes * 60
    merged: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    stopped_reason = ""

    protection_ok, protection_detail = verify_main_merge_policy()
    if not protection_ok:
        skipped = [
            {"number": int(candidate["number"]), "reason": protection_detail}
            for candidate in plan
        ]
        return {
            "schema_version": 1,
            "merged": merged,
            "skipped": skipped,
            "stopped_reason": protection_detail,
            "all_selected_merged": False,
            "staging": (
                {"success": False, "detail": "staging withheld because main merge protection is not verified"}
                if deploy_staging
                else None
            ),
        }

    for candidate in plan:
        number = int(candidate["number"])
        expected_head = str(candidate["head_sha"])
        main = api_get(repo_api_path("/branches/main"))
        main_sha = main["commit"]["sha"]

        try:
            report = build_pr_report(number, expected_head, main_sha, repository)
        except (
            GitHubAPIError,
            KeyError,
            OSError,
            RuntimeError,
            TypeError,
            ValueError,
        ) as error:
            skipped.append(
                {
                    "number": number,
                    "reason": f"live_preflight_error:{type(error).__name__}:{error}",
                }
            )
            stopped_reason = f"live preflight failed for PR #{number}; stopping batch"
            break

        if not report.get("eligible"):
            skipped.append(
                {
                    "number": number,
                    "reason": ",".join(report.get("reasons", [])),
                }
            )
            stopped_reason = f"PR #{number} failed live preflight; stopping batch"
            break

        accepted, merge_request_detail = gh_merge_or_enqueue(
            number, repository, expected_head
        )
        if not accepted:
            skipped.append({"number": number, "reason": merge_request_detail})
            stopped_reason = (
                f"GitHub did not accept PR #{number} for merge; stopping batch"
            )
            break

        merged_ok, merge_sha, merge_detail = wait_for_pr_merge(number, timeout_seconds)
        if not merged_ok:
            skipped.append(
                {
                    "number": number,
                    "reason": f"{merge_request_detail}; {merge_detail}",
                }
            )
            stopped_reason = f"PR #{number} was not confirmed merged; stopping batch"
            break

        ci_ok, ci_detail = wait_for_main_ci(merge_sha, timeout_seconds)
        merged.append(
            {
                "number": number,
                "head_sha": expected_head,
                "merge_sha": merge_sha,
                "merge_confirmation": merge_detail,
                "ci": ci_detail,
                "ci_success": ci_ok,
                "url": candidate.get("url", ""),
            }
        )
        if not ci_ok:
            stopped_reason = (
                f"main CI barrier failed after PR #{number}; stopping batch"
            )
            break

    staging_result = None
    all_selected_merged = (
        len(merged) == len(plan) and not skipped and not stopped_reason
    )
    if deploy_staging:
        if all_selected_merged and merged:
            success, detail = dispatch_and_wait_for_staging(timeout_seconds)
            staging_result = {"success": success, "detail": detail}
            if not success:
                stopped_reason = detail
        else:
            staging_result = {
                "success": False,
                "detail": "staging dispatch withheld because the entire selected batch did not merge and pass main CI",
            }
            stopped_reason = stopped_reason or "staging dispatch withheld"

    return {
        "schema_version": 1,
        "merged": merged,
        "skipped": skipped,
        "stopped_reason": stopped_reason,
        "all_selected_merged": all_selected_merged,
        "staging": staging_result,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", required=True)
    parser.add_argument("--timeout-minutes", type=int, default=20)
    parser.add_argument("--deploy-staging", action="store_true")
    args = parser.parse_args()

    if not 1 <= args.timeout_minutes <= 30:
        parser.error("--timeout-minutes must be between 1 and 30")

    try:
        with open(args.plan, encoding="utf-8") as file:
            plan = json.load(file)
        candidates = plan.get("selected", [])
        if not candidates:
            print("No selected PRs; merge stage has nothing to execute.")
            return 0
        result = execute(candidates, args.timeout_minutes, args.deploy_staging)
        write_json("merge-results.json", result)

        summary = os.environ.get("GITHUB_STEP_SUMMARY")
        if summary:
            with open(summary, "a", encoding="utf-8") as file:
                file.write("## PR Merge Execution\n\n")
                file.write(f"- Merged: **{len(result['merged'])}**\n")
                file.write(f"- Skipped: **{len(result['skipped'])}**\n")
                file.write(
                    f"- Entire batch merged: **{result['all_selected_merged']}**\n"
                )
                if result["stopped_reason"]:
                    file.write(f"- Stopped: {result['stopped_reason']}\n")
                if result["staging"]:
                    file.write(
                        f"- Staging: **{result['staging']['success']}** — "
                        f"{result['staging']['detail']}\n"
                    )
                file.writelines(
                    f"- Merged PR #{item['number']} — main CI: {item['ci']}\n"
                    for item in result["merged"]
                )
                file.writelines(
                    f"- Skipped PR #{item['number']} — {item['reason']}\n"
                    for item in result["skipped"]
                )
        print(json.dumps(result, indent=2))

        if not result["all_selected_merged"]:
            return 1
        if result["staging"] and not result["staging"]["success"]:
            return 1
        return 0
    except (
        GitHubAPIError,
        KeyError,
        OSError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as error:
        print(
            f"Merge executor failed closed: {type(error).__name__}: {error}",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
