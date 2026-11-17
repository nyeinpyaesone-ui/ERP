"""Tests for deterministic and conflict-aware PR reduction."""

from __future__ import annotations

import unittest

from reduce import build_plan


def report(number, risk, risk_order, paths):
    return {
        "number": number,
        "head_sha": f"head-{number}",
        "title": f"PR {number}",
        "url": f"https://github.com/example/repo/pull/{number}",
        "risk": risk,
        "risk_order": risk_order,
        "changed_files": paths,
        "eligible": True,
        "reasons": [],
    }


class ReduceTests(unittest.TestCase):
    def test_lower_risk_is_selected_first(self) -> None:
        plan = build_plan(
            [
                report(2, "backend", 4, ["backend/app/main.py"]),
                report(1, "documentation", 1, ["docs/guide.md"]),
            ],
            [1, 2],
            max_merges=2,
        )
        self.assertEqual(
            [item["number"] for item in plan["selected"]],
            [1, 2],
        )

    def test_overlapping_files_defer_later_pr(self) -> None:
        plan = build_plan(
            [
                report(2, "dependency", 2, ["backend/requirements.txt"]),
                report(1, "dependency", 2, ["backend/requirements.txt"]),
            ],
            [1, 2],
            max_merges=2,
        )
        self.assertEqual([item["number"] for item in plan["selected"]], [1])
        self.assertEqual(plan["deferred"][0]["number"], 2)
        self.assertEqual(plan["deferred"][0]["overlaps_with_prs"], [1])

    def test_missing_map_report_is_blocked(self) -> None:
        plan = build_plan([], [10], max_merges=1)
        self.assertEqual(plan["blocked"][0]["number"], 10)
        self.assertIn("map_report_missing", plan["blocked"][0]["reasons"])

    def test_batch_limit_defers_remaining_safe_candidates(self) -> None:
        plan = build_plan(
            [
                report(1, "documentation", 1, ["docs/a.md"]),
                report(2, "backend", 4, ["backend/app/a.py"]),
            ],
            [1, 2],
            max_merges=1,
        )
        self.assertEqual(len(plan["selected"]), 1)
        self.assertEqual(plan["deferred"][0]["deferred_reason"], "batch_limit")


if __name__ == "__main__":
    unittest.main()
