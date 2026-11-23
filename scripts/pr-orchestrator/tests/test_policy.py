"""Guard the coded policy against drift from its documentation."""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from policy import REQUIRED_GREEN_CHECKS

DOC_PATH = (
    Path(__file__).resolve().parents[3] / "docs" / "PR_MAP_REDUCE_ORCHESTRATION.md"
)
LIST_PATTERN = re.compile(r"`success`:\s*(?P<items>.+?\.)(?:\s|$)")


def documented_required_checks() -> set[str]:
    """Extract the mandatory-check list from the eligibility-policy doc line."""
    text = DOC_PATH.read_text(encoding="utf-8")
    line = next(
        (
            candidate
            for candidate in text.splitlines()
            if "mandatory checks must each be present" in candidate
        ),
        None,
    )
    if line is None:
        raise AssertionError("mandatory-check line missing from policy documentation")

    # The sentence continues after the list; capture only up to its first
    # sentence-ending period, so trailing prose cannot leak into the set.
    match = LIST_PATTERN.search(line)
    if match is None:
        raise AssertionError("could not parse mandatory-check list from documentation")
    items = match.group("items").rstrip(".").replace(", and ", ", ")
    return {name.strip().rstrip(".") for name in items.split(", ")}


class PolicyDocumentationTests(unittest.TestCase):
    def test_documented_mandatory_checks_match_code(self) -> None:
        self.assertEqual(documented_required_checks(), set(REQUIRED_GREEN_CHECKS))

    def test_mandatory_check_list_is_not_empty(self) -> None:
        self.assertTrue(REQUIRED_GREEN_CHECKS)
        self.assertIn("Tests", REQUIRED_GREEN_CHECKS)
        self.assertIn("Security Scan", REQUIRED_GREEN_CHECKS)


if __name__ == "__main__":
    unittest.main()
