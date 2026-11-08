"""Small, dependency-free GitHub API client for the PR orchestrator."""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

API_ROOT = "https://api.github.com"
API_VERSION = "2022-11-28"


class GitHubAPIError(RuntimeError):
    """Raised when the GitHub API returns a non-success response."""

    def __init__(self, status: int, message: str) -> None:
        super().__init__(f"GitHub API {status}: {message}")
        self.status = status


def token_from_env() -> str:
    token = (
        os.environ.get("PR_ORCHESTRATOR_TOKEN")
        or os.environ.get("GH_TOKEN")
        or os.environ.get("GITHUB_TOKEN")
    )
    if not token:
        raise RuntimeError("A GitHub API token is required in the environment")
    return token


def api_request(
    method: str,
    path_or_url: str,
    payload: dict[str, Any] | None = None,
    token: str | None = None,
) -> tuple[Any, dict[str, str], int]:
    """Call GitHub REST and return decoded body, response headers, and status."""
    url = (
        path_or_url
        if path_or_url.startswith("https://")
        else f"{API_ROOT}{path_or_url}"
    )
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token or token_from_env()}",
        "User-Agent": "erp-pr-map-reduce-orchestrator",
        "X-GitHub-Api-Version": API_VERSION,
    }
    data = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode("utf-8")

    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read()
            body = json.loads(raw.decode("utf-8")) if raw else None
            return body, dict(response.headers.items()), response.status
    except urllib.error.HTTPError as error:
        raw_error = error.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(raw_error)
            message = parsed.get("message", raw_error)
        except json.JSONDecodeError:
            message = raw_error
        raise GitHubAPIError(error.code, str(message)) from error
    except urllib.error.URLError as error:
        raise RuntimeError(f"GitHub API network error: {error.reason}") from error


def api_get(path_or_url: str, token: str | None = None) -> Any:
    body, _, _ = api_request("GET", path_or_url, token=token)
    return body


def api_put(
    path: str, payload: dict[str, Any], token: str | None = None
) -> tuple[Any, int]:
    body, _, status = api_request("PUT", path, payload, token)
    return body, status


def api_post(
    path: str, payload: dict[str, Any], token: str | None = None
) -> tuple[Any, int]:
    body, _, status = api_request("POST", path, payload, token)
    return body, status


def api_paginate(path_or_url: str, token: str | None = None) -> list[Any]:
    """Read all pages from a GitHub list endpoint."""
    current_url = (
        path_or_url
        if path_or_url.startswith("https://")
        else f"{API_ROOT}{path_or_url}"
    )
    results: list[Any] = []
    next_pattern = re.compile(r'<([^>]+)>;\s*rel="next"')
    while current_url:
        page, headers, _ = api_request("GET", current_url, token=token)
        if not isinstance(page, list):
            raise RuntimeError(f"Expected a paginated list from {current_url}")
        results.extend(page)
        link_header = next(
            (value for key, value in headers.items() if key.lower() == "link"), ""
        )
        match = next_pattern.search(link_header)
        current_url = match.group(1) if match else ""
    return results


def api_paginate_field(
    path_or_url: str, field: str, token: str | None = None
) -> list[Any]:
    """Read a paginated list nested inside an object response."""
    current_url = (
        path_or_url
        if path_or_url.startswith("https://")
        else f"{API_ROOT}{path_or_url}"
    )
    results: list[Any] = []
    next_pattern = re.compile(r'<([^>]+)>;\s*rel="next"')
    while current_url:
        page, headers, _ = api_request("GET", current_url, token=token)
        if not isinstance(page, dict) or not isinstance(page.get(field), list):
            raise RuntimeError(
                f"Expected list field {field!r} from {current_url}"
            )
        results.extend(page[field])
        link_header = next(
            (value for key, value in headers.items() if key.lower() == "link"), ""
        )
        match = next_pattern.search(link_header)
        current_url = match.group(1) if match else ""
    return results


def repo_slug() -> str:
    repository = os.environ.get("GITHUB_REPOSITORY", "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        raise RuntimeError("GITHUB_REPOSITORY must be owner/repository")
    return repository


def repo_api_path(suffix: str) -> str:
    return f"/repos/{repo_slug()}{suffix}"


def write_json(path: str, value: Any) -> None:
    with open(path, "w", encoding="utf-8") as file:
        json.dump(value, file, indent=2, sort_keys=True)
        file.write("\n")
