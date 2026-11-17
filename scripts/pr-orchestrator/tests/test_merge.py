"""Tests for guarded merge, queue handling, and exact-event verification."""

from __future__ import annotations

import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import merge


class MergeExecutorTests(unittest.TestCase):
    def test_main_merge_policy_requires_admin_review_and_strict_checks(self) -> None:
        protection = {
            "enforce_admins": {"enabled": True},
            "required_pull_request_reviews": {"required_approving_review_count": 1},
            "required_status_checks": {
                "strict": True,
                "contexts": ["CI"],
                "checks": [],
            },
        }
        with patch("merge.api_get", return_value=protection):
            allowed, detail = merge.verify_main_merge_policy()
        self.assertTrue(allowed)
        self.assertIn("administrator enforcement enabled", detail)
        self.assertIn("strict checks enabled", detail)

    def test_missing_main_merge_protection_fails_closed(self) -> None:
        protection = {
            "enforce_admins": {"enabled": False},
            "required_pull_request_reviews": None,
            "required_status_checks": None,
        }
        with patch("merge.api_get", return_value=protection):
            allowed, detail = merge.verify_main_merge_policy()
        self.assertFalse(allowed)
        self.assertIn("enforce rules for administrators", detail)

    def test_non_strict_status_checks_fail_closed(self) -> None:
        protection = {
            "enforce_admins": {"enabled": True},
            "required_pull_request_reviews": {"required_approving_review_count": 1},
            "required_status_checks": {"strict": False, "contexts": ["CI"]},
        }
        with patch("merge.api_get", return_value=protection):
            allowed, detail = merge.verify_main_merge_policy()
        self.assertFalse(allowed)
        self.assertIn("up to date", detail)

    def test_unreadable_main_merge_protection_fails_closed(self) -> None:
        with patch(
            "merge.api_get",
            side_effect=merge.GitHubAPIError(403, "forbidden"),
        ):
            allowed, detail = merge.verify_main_merge_policy()
        self.assertFalse(allowed)
        self.assertIn("could not be verified", detail)

    def test_merge_request_uses_exact_head_and_never_admin_bypass(self) -> None:
        completed = SimpleNamespace(returncode=0, stdout="queued", stderr="")
        with (
            patch("merge.shutil.which", return_value="/usr/bin/gh"),
            patch("merge.subprocess.run", return_value=completed) as run,
            patch.dict(os.environ, {"PR_ORCHESTRATOR_TOKEN": "test-token"}),
        ):
            accepted, detail = merge.gh_merge_or_enqueue(
                157, "example/repo", "expected-head-sha"
            )

        self.assertTrue(accepted)
        self.assertEqual(detail, "queued")
        command = run.call_args.args[0]
        self.assertIn("--match-head-commit", command)
        self.assertEqual(
            command[command.index("--match-head-commit") + 1], "expected-head-sha"
        )
        self.assertNotIn("--auto", command)
        self.assertNotIn("--admin", command)
        self.assertEqual(run.call_args.kwargs["env"]["GH_TOKEN"], "test-token")

    def test_missing_merge_credential_fails_closed(self) -> None:
        with (
            patch("merge.shutil.which", return_value="/usr/bin/gh"),
            patch.dict(os.environ, {}, clear=True),
        ):
            accepted, detail = merge.gh_merge_or_enqueue(
                157, "example/repo", "expected-head-sha"
            )
        self.assertFalse(accepted)
        self.assertIn("PR_ORCHESTRATOR_TOKEN", detail)

    def test_merge_wait_requires_github_merged_confirmation(self) -> None:
        with patch(
            "merge.api_get",
            return_value={
                "state": "closed",
                "merged": True,
                "merge_commit_sha": "merge-commit-sha",
            },
        ):
            merged, sha, detail = merge.wait_for_pr_merge(157, timeout_seconds=1)
        self.assertTrue(merged)
        self.assertEqual(sha, "merge-commit-sha")
        self.assertIn("confirmed", detail)

    def test_staging_wait_correlates_new_run_by_id(self) -> None:
        responses = [
            {
                "workflow_runs": [
                    {"id": 100, "name": "CI", "event": "workflow_dispatch"}
                ]
            },
            {
                "workflow_runs": [
                    {"id": 100, "name": "CI", "event": "workflow_dispatch"},
                    {"id": 101, "name": "CI", "event": "workflow_dispatch"},
                ]
            },
            {"id": 101, "status": "completed"},
            {"jobs": [{"name": "Deploy to Staging", "conclusion": "success"}]},
        ]
        with (
            patch("merge.api_get", side_effect=responses),
            patch("merge.api_post", return_value=(None, 204)),
            patch("merge.time.monotonic", side_effect=[0, 0]),
            patch("merge.time.sleep"),
        ):
            success, detail = merge.dispatch_and_wait_for_staging(30)

        self.assertTrue(success)
        self.assertIn("run 101", detail)


if __name__ == "__main__":
    unittest.main()
