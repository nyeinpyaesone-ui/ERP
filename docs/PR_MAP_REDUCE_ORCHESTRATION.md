# Pull Request Map-Reduce Orchestration

## Purpose

The PR Map-Reduce Orchestrator processes all open pull requests targeting `main` as independent, evidence-backed work units. It uses GitHub Actions matrix workers for parallel inspection, a reducer for dependency/risk ordering, and one serial executor for guarded merges.

It does not pretend that a language-model sub-agent has approved code. The accompanying OpenCode skill defines zero-shot specialist review tasks; GitHub Actions performs the deterministic API checks and event orchestration.

## OpenCode specialist agents

The repository includes project-scoped OpenCode agent definitions under .opencode/agents. The primary pr-orchestrator delegates read-only specialist work to the scope, backend, frontend, security, platform, tests, and documentation agents. Their task envelopes include the exact PR head/base SHAs. They return PASS, BLOCK, or NEEDS_EVIDENCE with source evidence; they cannot approve or merge.

The deterministic GitHub Actions workflow is the execution authority for merge eligibility, changed-file overlap, serial merges, and main-CI barriers.

## Workflow

File: `.github/workflows/pr-map-reduce-orchestrator.yml`

| Stage | Mechanism | Output |
|---|---|---|
| Discover | Snapshot open PRs based on `main` | PR number + immutable head/base SHA |
| Map | Matrix workers, up to 8 in parallel | One JSON evidence report per PR |
| Reduce | Sort by risk; block missing evidence; detect changed-file overlap | Immutable bounded merge plan |
| Execute | One serial merge worker | Per-PR merge result |
| Verify | Wait for `CI` on the exact merge SHA | Pass/fail barrier before next PR |
| Deploy | Optional existing `CI` workflow dispatch | Staging deployment result |

### Run modes

Use **Actions → PR Map-Reduce Orchestrator → Run workflow** on the `main` branch.

| Input | Default | Meaning |
|---|---:|---|
| `mode` | `plan` | `plan` is read-only; `merge` enables the guarded merge stage |
| `max_prs` | 50 | Discovery cap, 1–100 |
| `max_merges` | 5 | Maximum selected PRs per batch, 1–20 |
| `ci_wait_minutes` | 20 | CI/deployment wait timeout per barrier, 1–30 |
| `deploy_staging` | false | Dispatch staging only after all selected PRs merge and their exact main CI runs pass |

The workflow has no schedule and does not recursively dispatch itself. Re-run it for the next batch. Discovery reports when the open queue exceeds the configured cap.

## Eligibility policy

A map report is eligible only when:

- The PR is open, non-draft, based on `main`, and from this repository.
- The head SHA and base SHA still match the discovery snapshot.
- GitHub confirms `mergeable=true` and `mergeable_state=clean`.
- The combined commit status is `success`.
- The newest observation for every check name/GitHub App is completed with `success`, `skipped`, or `neutral`.
- No reviewer's latest submitted review is `CHANGES_REQUESTED`.
- Changed-file data is available.

Approvals are recorded as evidence, but the orchestrator does not invent a review policy. The GitHub merge API and repository rules remain the authority: required approvals, required status checks, merge queues, branch protection, and rulesets cannot be bypassed by this workflow.

Missing, stale, contradictory, or unavailable evidence blocks that PR. Fork-head PRs are not automatically merged by this workflow.

## Reduction policy

Risk order is documentation → dependency → frontend → backend → application → infrastructure/workflow. PRs that modify the same path are not selected into the same batch; the lower-priority PR is deferred for a new discovery after the earlier merge. Missing worker artifacts are blocked.

The default batch size is five. The plan artifact includes selected, blocked, and deferred PRs with reasons.

## Merge and event loop

Merge mode is allowed only for a workflow dispatch on `refs/heads/main`. Before each merge, the executor refreshes the PR, the current main SHA, reviews, checks, statuses, and changed files. It submits the request through GitHub CLI auto-merge with the expected head SHA as a compare-and-swap guard. This lets GitHub place changes into a required merge queue; the workflow never uses the administrator bypass flag. It waits for GitHub to confirm the PR is merged before checking the exact merge SHA.

GitHub merge queues require the repository `CI` workflow to subscribe to `merge_group: checks_requested`. That CI path builds temporary backend/frontend images locally, runs the HIGH/CRITICAL Trivy gate, and never publishes those images. After GitHub confirms a merge, the executor waits for the repository's `CI` workflow for that exact merge SHA with `event=push` and `branch=main`. A failed, missing, canceled, or timed-out run stops the batch. Later PRs are not merged until the preceding main CI barrier succeeds.

Staging is dispatched through the existing `ci.yml` workflow only after the entire selected batch has merged and passed main CI. The existing staging environment rules and reviewer gates still apply. Production release remains a separate version-tagged release process and is never auto-triggered here.

## Required merge credential

Plan mode uses the workflow's read-only `GITHUB_TOKEN`. Merge mode requires the repository Actions secret:

- `PR_ORCHESTRATOR_TOKEN`

Use a narrowly scoped GitHub App token or fine-grained token for this repository with only the permissions required by the selected mode:

| Permission | Access |
|---|---|
| Contents | Read/write (merge commit and branch update) |
| Pull requests | Read/write |
| Checks | Read |
| Commit statuses | Read |
| Actions | Read; write only when staging dispatch is enabled |
| Metadata | Read |

Do not grant repository/ruleset bypass. Do not use a personal credential with broader access than required. Never place token values in workflow inputs, files, logs, or chat. The workflow fails before merging when this secret is absent.

The token used for merge mode must create normal push events so that the main-branch CI workflow starts. The default workflow `GITHUB_TOKEN` is intentionally not used for merges because GitHub suppresses most workflow-triggering events caused by that token.

## Evidence and artifacts

Every run preserves:
- Discovery snapshot.
- Per-PR map reports.
- Reduced orchestration plan.
- Merge results and exact merge/CI SHAs.

Unit tests cover eligibility, stale heads, draft/fork blocking, reviewer changes, risk classification, overlap reduction, missing reports, and batch limits.

## Current limitations

- Branch-protection details were not readable through the connected API identity during implementation (GitHub returned 403). Mergeability and status evidence are rechecked; GitHub's own merge/merge-queue service still enforces the actual repository policy.
- CI run and staging deployment waits are bounded. Missing credentials, unavailable permissions, or unmet environment approvals produce an explicit blocked/failed result, not a success claim.
- A single batch is bounded and serial after the parallel map phase. Deferred or blocked PRs remain open for a later re-map; the orchestrator never closes or force-merges them.
