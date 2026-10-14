#!/usr/bin/env bash
# repo-guard.sh — fast repo integrity check (guards against the T-019 incident class:
# a stray `git init`/clone nested in the repo hides deletions from `git status`).
# Run via `make guard` or directly. Exits non-zero on any finding.
set -u
cd "$(git rev-parse --show-toplevel)" || exit 2
fail=0

# 1. No nested git repositories (only ./.git is legitimate)
while IFS= read -r g; do
  echo "FAIL: nested git repository at ${g%/}/.git (hides worktree damage from git status)"
  fail=1
done < <(find . \( -name .git -o -name node_modules \) -prune -o -type d -name .git -print 2>/dev/null)

# 2. Every tracked file must exist in the worktree
missing=$(git ls-files | while IFS= read -r f; do [ -e "$f" ] || echo "$f"; done)
if [ -n "$missing" ]; then
  echo "FAIL: tracked files missing from the worktree:"
  echo "$missing"
  fail=1
fi

# 3. scripts/*.sh must be non-empty
for s in scripts/*.sh; do
  [ -s "$s" ] || { echo "FAIL: empty or missing $s"; fail=1; }
done

[ "$fail" -eq 0 ] && echo "repo-guard: OK ($(git ls-files | wc -l) tracked files, no nested .git)"
exit "$fail"
