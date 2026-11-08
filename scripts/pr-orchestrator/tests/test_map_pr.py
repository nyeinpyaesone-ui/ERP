"""Tests for deterministic map-worker eligibility decisions."""

from __future__ import annotations

import unittest

from map_pr import classify_risk, evaluate_pr


class MapPRTests(unittest.TestCase):
    def setUp(self) -> None:
        self.pr = {
            "number": 42,
            "title": "Test PR",
            "html_url": "https://github.com/example/repo/pull/42",
            "state": "open",
            "draft": False,
            "mergeable": True,
            "mergeable_state": "clean",
            "updated_at": "2026-11-09T00:00:00Z",
            "head": {
                "sha": "head-sha",
                "repo": {"full_name": "example/repo"},
            },
            "base": {"sha": "base-sha", "ref": "main"},
        }
        self.check_runs = [
            {"name": "CI", "status": "completed", "conclusion": "success"}
        ]
        self.status = {"state": "success"}
        self.reviews = [
            {
                "user": {"login": "reviewer"},
                "state": "APPROVED",
                "submitted_at": "2026-11-09T00:00:00Z",
            }
        ]
        self.files = [{"filename": "backend/app/main.py"}]

    def report(self, **overrides):
        values = {
            "pr": self.pr,
            "check_runs": self.check_runs,
            "combined_status": self.status,
            "reviews": self.reviews,
            "files": self.files,
            "expected_head_sha": "head-sha",
            "expected_base_sha": "base-sha",
            "repository": "example/repo",
        }
        values.update(overrides)
        return evaluate_pr(**values)

    def test_green_internal_pr_is_eligible(self) -> None:
        report = self.report()
        self.assertTrue(report["eligible"])
        self.assertEqual(report["status"], "eligible")
        self.assertEqual(report["risk"], "backend")
        self.assertEqual(report["approved_reviewers"], ["reviewer"])

    def test_draft_is_blocked(self) -> None:
        draft = {**self.pr, "draft": True}
        report = self.report(pr=draft)
        self.assertFalse(report["eligible"])
        self.assertIn("draft_pr", report["reasons"])

    def test_unfinished_or_failed_check_is_blocked(self) -> None:
        checks = [{"name": "CI", "status": "completed", "conclusion": "failure"}]
        report = self.report(check_runs=checks)
        self.assertFalse(report["eligible"])
        self.assertTrue(
            any(reason.startswith("checks_not_green:") for reason in report["reasons"])
        )

    def test_changes_requested_is_blocked(self) -> None:
        reviews = self.reviews + [
            {
                "user": {"login": "reviewer"},
                "state": "CHANGES_REQUESTED",
                "submitted_at": "2026-11-09T00:01:00Z",
            }
        ]
        report = self.report(reviews=reviews)
        self.assertFalse(report["eligible"])
        self.assertTrue(
            any(reason.startswith("changes_requested:") for reason in report["reasons"])
        )

    def test_empty_classic_status_contexts_do_not_override_green_checks(self) -> None:
        report = self.report(
            combined_status={"state": "pending", "total_count": 0, "statuses": []}
        )
        self.assertTrue(report["eligible"])

    def test_failed_classic_status_context_blocks(self) -> None:
        report = self.report(
            combined_status={
                "state": "failure",
                "total_count": 1,
                "statuses": [{"context": "legacy-check", "state": "failure"}],
            }
        )
        self.assertFalse(report["eligible"])
        self.assertIn("commit_status_failure", report["reasons"])

    def test_latest_check_result_supersedes_older_same_app_run(self) -> None:
        from map_pr import latest_check_runs

        checks = [
            {
                "name": "CI",
                "app": {"id": 1},
                "status": "completed",
                "conclusion": "failure",
                "completed_at": "2026-11-08T00:00:00Z",
            },
            {
                "name": "CI",
                "app": {"id": 1},
                "status": "completed",
                "conclusion": "success",
                "completed_at": "2026-11-09T00:00:00Z",
            },
        ]
        latest = latest_check_runs(checks)
        self.assertEqual(len(latest), 1)
        self.assertEqual(latest[0]["conclusion"], "success")

    def test_head_or_base_drift_is_blocked(self) -> None:
        report = self.report(expected_head_sha="different")
        self.assertFalse(report["eligible"])
        self.assertIn("head_sha_changed", report["reasons"])

    def test_fork_head_is_blocked(self) -> None:
        pr = {
            **self.pr,
            "head": {"sha": "head-sha", "repo": {"full_name": "fork/repo"}},
        }
        report = self.report(pr=pr)
        self.assertFalse(report["eligible"])
        self.assertIn("head_repository_is_not_internal", report["reasons"])

    def test_risk_classification(self) -> None:
        self.assertEqual(classify_risk(["docs/README.md"]), "documentation")
        self.assertEqual(
            classify_risk(["backend/requirements-runtime.txt"]), "dependency"
        )
        self.assertEqual(classify_risk([".github/workflows/ci.yml"]), "infrastructure")
        self.assertEqual(
            classify_risk(["backend/frontend-react/src/App.tsx"]), "frontend"
        )


if __name__ == "__main__":
    unittest.main()
