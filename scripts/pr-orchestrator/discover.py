"""Discover a bounded set of open PRs targeting main for map workers."""

from __future__ import annotations

import json
import os
import sys
from urllib.parse import urlencode

from client import api_paginate, repo_api_path, write_json


def main() -> int:
    try:
        maximum = int(os.environ.get("MAX_PRS", "50"))
        if not 1 <= maximum <= 100:
            raise ValueError("MAX_PRS must be between 1 and 100")

        query = urlencode({"state": "open", "per_page": 100, "sort": "created", "direction": "asc"})
        pulls = api_paginate(f"{repo_api_path('/pulls')}?{query}")
        matching = [pull for pull in pulls if pull.get("base", {}).get("ref") == "main"]
        matching.sort(key=lambda item: (item.get("created_at", ""), item.get("number", 0)))
        selected = matching[:maximum]

        matrix = {
            "include": [
                {
                    "number": int(pull["number"]),
                    "head_sha": pull["head"]["sha"],
                    "base_sha": pull["base"]["sha"],
                }
                for pull in selected
            ]
        }
        result = {
            "matrix": matrix,
            "count": len(selected),
            "total_open_main_prs": len(matching),
            "truncated": len(matching) > maximum,
            "pr_numbers": [item["number"] for item in matrix["include"]],
        }
        write_json("discovery.json", result)

        output = os.environ.get("GITHUB_OUTPUT")
        if output:
            with open(output, "a", encoding="utf-8") as file:
                file.write(f"matrix={json.dumps(matrix, separators=(',', ':'))}\n")
                file.write(f"count={len(selected)}\n")
                file.write(
                    "pr_numbers="
                    + json.dumps(result["pr_numbers"], separators=(",", ":"))
                    + "\n"
                )
                file.write(f"total={len(matching)}\n")
                file.write(f"truncated={str(result['truncated']).lower()}\n"
                )
        print(json.dumps(result, indent=2))
        return 0
    except Exception as error:  # fail the discovery job, never invent a matrix
        print(f"PR discovery failed closed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
