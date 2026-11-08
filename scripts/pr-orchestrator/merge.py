"""Serial, fail-closed PR merge executor with a main-CI event barrier."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlencode

from client import (
    GitHubAPIError,
    api_get,
    api_paginate,
    api_post,
    api_put,
    repo_api_path,
    write_json,
)
from map_pr import build_pr_report


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


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
            run = sorted(matches, key=lambda item: item.get("created_at", ""))[-1]
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
    started_at = utc_now()
    api_post(
        repo_api_path("/actions/workflows/ci.yml/dispatches"),
        {"ref": "main", "inputs": {"deploy_staging": "true"}},
    )
    deadline = time.monotonic() + timeout_seconds
    workflow_run: dict[str, Any] | None = None

    while time.monotonic() < deadline:
        query = urlencode(
            {"branch": "main", "event": "workflow_dispatch", "per_page": 100}
        )
        response = api_get(repo_api_path("/actions/runs") + f"?{query}")
        candidates = [
            item
            for item in response.get("workflow_runs", [])
            if item.get("name") == "CI"
            and item.get("created_at", "") >= started_at
        ]
        if candidates:
            workflow_run = sorted(
                candidates, key=lambda item: item.get("created_at", "")
            )[-1]
            workflow_run = api_get(
                repo_api_path(f"/actions/runs/{workflow_run['id']}")
            )
            if workflow_run.get("status") == "completed":
                run_id = workflow_run["id"]
                jobs = api_paginate(
                    repo_api_path(f"/actions/runs/{run_id}/jobs?per_page=100")
                )
                staging = next(
                    (
                        job
                        for job in jobs
                        if job.get("name") == "Deploy to Staging"
                    ),
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


def execute(plan: list[dict[str, Any]], timeout_minutes: int, deploy_staging: bool) -> dict[str, Any]:
    repository = os.environ["GITHUB_REPOSITORY"]
    timeout_seconds = timeout_minutes * 60
    merged: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    stopped_reason = ""

    for candidate in plan:
        number = int(candidate["number"])
        expected_head = str(candidate["head_sha"])
        main = api_get(repo_api_path("/branches/main"))
        main_sha = main["commit"]["sha"]

        try:
            report = build_pr_report(
                number, expected_head, main_sha, repository
            )
        except Exception as error:
            skipped.append(
                {
                    "number": number,
                    "reason": f"live_preflight_error:{type(error).__name__}:{error}",
                }
            )
            continue

        if not report.get("eligible"):
            skipped.append(
                {
                    "number": number,
                    "reason": ",".join(report.get("reasons", [])),
                }
            )
            continue

        try:
            merge_response, status = api_put(
                repo_api_path(f"/pulls/{number}/merge"),
                {"sha": expected_head, "merge_method": "squash"},
            )
        except GitHubAPIError as error:
            skipped.append(
                {"number": number, "reason": f"GitHub blocked merge: {error}"}
            )
            if error.status in {409, 422}:
                stopped_reason = "merge race or conflict; remaining candidates deferred"
                break
            continue

        if status != 200 or merge_response.get("merged") is not True:
            skipped.append(
                {
                    "number": number,
                    "reason": merge_response.get("message", "merge_not_confirmed"),
                }
            )
            continue

        merge_sha = str(merge_response.get("sha", ""))
        if not merge_sha:
            stopped_reason = f"PR #{number} merged without a returned merge SHA"
            break

        pr_after = api_get(repo_api_path(f"/pulls/{number}"))
        if pr_after.get("merged") is not True:
            stopped_reason = f"PR #{number} merge was not confirmed by GitHub"
            break

        ci_ok, ci_detail = wait_for_main_ci(merge_sha, timeout_seconds)
        merged.append(
            {
                "number": number,
                "head_sha": expected_head,
                "merge_sha": merge_sha,
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
    all_selected_merged = len(merged) == len(plan) and not skipped and not stopped_reason
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
                for item in result["merged"]:
                    file.write(
                        f"- Merged PR #{item['number']} — "
                        f"main CI: {item['ci']}\n"
                    )
                for item in result["skipped"]:
                    file.write(
                        f"- Skipped PR #{item['number']} — {item['reason']}\n"
                    )
        print(json.dumps(result, indent=2))

        if not result["all_selected_merged"]:
            return 1
        if result["staging"] and not result["staging"]["success"]:
            return 1
        return 0
    except Exception as error:
        print(
            f"Merge executor failed closed: {type(error).__name__}: {error}",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
