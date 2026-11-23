"""Single source of truth for PR orchestration eligibility policy.

This policy is mirrored in docs/PR_MAP_REDUCE_ORCHESTRATION.md.
tests/test_policy.py guards the two against drifting apart.
"""

from __future__ import annotations

# Conclusions accepted for non-mandatory checks. A mandatory check must be
# exactly "success" (enforced separately in map_pr.evaluate_pr).
ALLOWED_CHECK_CONCLUSIONS = frozenset({"success", "skipped", "neutral"})

# Checks that must be present and completed with conclusion == "success".
REQUIRED_GREEN_CHECKS = frozenset(
    {
        "Code Quality",
        "CodeQL",
        "Deploy Configuration",
        "Frontend Build",
        "Build Backend Image",
        "Build Frontend Image",
        "Security Scan",
        "Secret Scan (Gitleaks)",
        "Tests",
    }
)

# Lower risk is merged first; same-path PRs are never batched together.
RISK_ORDER = {
    "documentation": 1,
    "dependency": 2,
    "frontend": 3,
    "backend": 4,
    "application": 5,
    "infrastructure": 6,
}
