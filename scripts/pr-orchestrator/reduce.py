"""Reduce per-PR map reports into a conflict-aware merge batch."""

from __future__ import annotations

import argparse
import glob
import json
import os
from typing import Any

from client import write_json


def build_plan(
    reports: list[dict[str, Any]],
    expected_numbers: list[int],
    max_merges: int,
    truncated: bool = False,
) -> dict[str, Any]:
    by_number = {
        int(report["number"]): report
        for report in reports
        if report.get("number") is not None
    }
    blocked: list[dict[str, Any]] = []
    eligible: list[dict[str, Any]] = []

    for number in expected_numbers:
        report = by_number.get(number)
        if report is None:
            blocked.append(
                {
                    "number": number,
                    "eligible": False,
                    "reasons": ["map_report_missing"],
                }
            )
        elif report.get("eligible") is True:
            eligible.append(report)
        else:
            blocked.append(report)

    eligible.sort(
        key=lambda item: (
            int(item.get("risk_order", 99)),
            int(item.get("number", 0)),
        )
    )

    selected: list[dict[str, Any]] = []
    deferred: list[dict[str, Any]] = []
    claimed_paths: dict[str, int] = {}

    for report in eligible:
        number = int(report["number"])
        paths = set(report.get("changed_files", []))
        overlap = sorted(path for path in paths if path in claimed_paths)
        if overlap:
            owners = sorted({claimed_paths[path] for path in overlap})
            item = dict(report)
            item["deferred_reason"] = "changed_file_overlap"
            item["overlaps_with_prs"] = owners
            item["overlapping_files"] = overlap
            deferred.append(item)
            continue
        if len(selected) >= max_merges:
            item = dict(report)
            item["deferred_reason"] = "batch_limit"
            deferred.append(item)
            continue
        selected.append(report)
        for path in paths:
            claimed_paths[path] = number

    return {
        "schema_version": 1,
        "mode": os.environ.get("ORCHESTRATOR_MODE", "plan"),
        "selected": [
            {
                "number": int(item["number"]),
                "head_sha": item["head_sha"],
                "title": item.get("title", ""),
                "risk": item.get("risk", "unknown"),
                "url": item.get("url", ""),
            }
            for item in selected
        ],
        "selected_count": len(selected),
        "mapped_count": len(reports),
        "expected_count": len(expected_numbers),
        "truncated_discovery": truncated,
        "blocked": blocked,
        "deferred": deferred,
        "eligible_before_batching": len(eligible),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-prs", required=True)
    parser.add_argument("--max-merges", type=int, default=5)
    parser.add_argument("--truncated", action="store_true")
    parser.add_argument("--reports-dir", default="map-reports")
    parser.add_argument("--output", default="orchestration-plan.json")
    args = parser.parse_args()

    if not 1 <= args.max_merges <= 20:
        parser.error("--max-merges must be between 1 and 20")

    expected = [int(value) for value in json.loads(args.expected_prs)]
    reports: list[dict[str, Any]] = []
    for path in glob.glob(os.path.join(args.reports_dir, "map-report-*.json")):
        with open(path, encoding="utf-8") as file:
            reports.append(json.load(file))

    plan = build_plan(reports, expected, args.max_merges, args.truncated)
    write_json(args.output, plan)

    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with open(output, "a", encoding="utf-8") as file:
            file.write(
                "selected_prs="
                + json.dumps(plan["selected"], separators=(",", ":"))
                + "\n"
            )
            file.write(f"selected_count={plan['selected_count']}\n")

    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    lines = [
        "## PR Map-Reduce Plan",
        "",
        f"- PRs discovered: **{plan['expected_count']}**",
        f"- Map reports received: **{plan['mapped_count']}**",
        f"- Eligible before conflict reduction: **{plan['eligible_before_batching']}**",
        f"- Selected for this batch: **{plan['selected_count']}**",
        f"- Blocked: **{len(plan['blocked'])}**",
        f"- Deferred: **{len(plan['deferred'])}**",
        f"- Discovery truncated: **{plan['truncated_discovery']}**",
        "",
        "| PR | Risk | Decision | Detail |",
        "|---:|---|---|---|",
    ]
    for item in plan["selected"]:
        lines.append(
            f"| #{item['number']} | {item['risk']} | selected | "
            f"[Open PR]({item['url']}) |"
        )
    for item in plan["blocked"]:
        detail = ", ".join(item.get("reasons", [])) or "blocked"
        lines.append(
            f"| #{item['number']} | {item.get('risk', 'unknown')} | blocked | {detail} |"
        )
    for item in plan["deferred"]:
        detail = item.get("deferred_reason", "deferred")
        owners = item.get("overlaps_with_prs", [])
        if owners:
            detail += "; overlaps " + ", ".join(f"#{number}" for number in owners)
        lines.append(
            f"| #{item['number']} | {item.get('risk', 'unknown')} | deferred | {detail} |"
        )
    if summary:
        with open(summary, "a", encoding="utf-8") as file:
            file.write("\n".join(lines) + "\n")
    print(json.dumps(plan, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
