---
name: PR Map-Reduce Orchestrator
description: Evidence-first, multi-agent pull-request triage, conflict-aware batching, serial merge execution, CI event barriers, and deployment gating for the ERP repository
---

# PR Map-Reduce Orchestrator

## Mission

Process every open pull request targeting \`main\` as an independently verified work unit. Converge approved, green, conflict-free changes into \`main\` in bounded batches, then verify the exact resulting main commit before any staging deployment.

The orchestrator is a control plane. It must preserve repository correctness, branch protections, reviewer decisions, and deployment boundaries. It must never trade correctness for merge throughput.

## Execution topology

1. **Discover**: snapshot open PR numbers, head SHAs, base SHAs, draft state, and target branch.
2. **Map**: execute independent PR workers in parallel. Each worker retrieves current PR metadata, changed files, check runs, combined commit status, and submitted reviews.
3. **Reduce**: join the worker reports, classify risk, detect changed-file overlap, and choose a bounded non-overlapping batch.
4. **Execute**: serialize merges. Immediately before each merge, repeat the full live preflight and use the expected head SHA as the merge compare-and-swap guard. When the repository uses a merge queue, the existing CI workflow must also execute on `merge_group: checks_requested`.
5. **Verify**: after every merge, wait for the CI workflow on the exact merge commit SHA. Stop the batch at the first failed or missing main-branch CI run.
6. **Deploy**: staging is a separate, explicit dispatch after the entire selected batch merges and passes main CI. Production requires the repository's versioned release path and is never triggered by this skill.

## OpenCode agent topology

Project-scoped agents are defined in .opencode/agents:

- pr-orchestrator: primary coordinator; can delegate only to the listed specialist agents.
- pr-scope-mapper: ownership, scope, cross-PR dependency and risk mapping.
- pr-backend-reviewer: API, persistence, migration and runtime correctness.
- pr-frontend-reviewer: canonical React/Vite, PWA and UI contract compatibility.
- pr-security-reviewer: security and software supply-chain review.
- pr-platform-reviewer: CI/CD, images, deployment and rollback.
- pr-test-reviewer: exact-head test and CI evidence.
- pr-docs-reviewer: operational documentation and source-of-truth drift.

The specialist subagents are read-only and cannot launch nested subagents. The primary coordinator can invoke them in parallel. They return independent findings; the deterministic GitHub Actions map/reduce workflow remains the only merge executor. The GitHub Actions workflow does not itself invoke OpenCode or these AI subagents; specialist review must be run separately through the OpenCode primary coordinator. Do not represent unexecuted agent reviews as completed evidence.

## Zero-shot task contract

Every worker receives the same immutable envelope:

\`\`\`json
{
  "repository": "owner/repository",
  "target_branch": "main",
  "pr_number": 0,
  "expected_head_sha": "40-character SHA",
  "expected_base_sha": "40-character SHA",
  "mode": "plan",
  "max_parallel": 8,
  "max_merges": 5,
  "policy_version": "1"
}
\`\`\`

The worker must independently retrieve live evidence. The envelope is a snapshot, not authority to merge. A mismatch between the current GitHub state and either expected SHA blocks that PR.

### Specialist roles

Dispatch one or more read-only specialist reviews by path/risk classification. These are analytical roles, not independent merge authorities.

| Role | Scope | Required output |
|---|---|---|
| Architecture reviewer | boundaries, dependencies, data contracts, migration order | incompatibilities and affected PR dependencies |
| Backend reviewer | API, persistence, migrations, runtime imports, tests | correctness risks and required tests |
| Frontend reviewer | build graph, dependency compatibility, UI tests | compatibility and regression risks |
| Security reviewer | secrets, auth, dependency CVEs, containers, permissions | severity, exploitability evidence, remediation |
| Platform reviewer | CI, container build, deployment, rollback, observability | release/deployment blockers |
| Documentation reviewer | operational instructions and source-of-truth drift | stale or contradictory instructions |

A specialist may recommend \`PASS\`, \`BLOCK\`, or \`NEEDS_EVIDENCE\`; it cannot change GitHub review state, approve a PR, or merge it.

## Deterministic map output

Each map worker writes one JSON report:

\`\`\`json
{
  "schema_version": 1,
  "number": 0,
  "head_sha": "40-character SHA",
  "base_sha": "40-character SHA",
  "eligible": false,
  "status": "blocked",
  "risk": "unknown",
  "risk_order": 99,
  "changed_files": [],
  "approved_reviewers": [],
  "reasons": []
}
\`\`\`

Eligibility requires: open PR, not draft, same repository head, base \`main\`, unchanged head/base snapshot, confirmed clean mergeability, successful combined commit status, all check runs completed with \`success\`, \`skipped\`, or \`neutral\`, and no latest reviewer decision of \`CHANGES_REQUESTED\`.

An \`APPROVED\` review is recorded as evidence but this tool does not invent or override repository review requirements. GitHub's merge endpoint and branch protection remain authoritative. Missing or unreadable evidence is a block, never an implicit pass.

## Reduce rules

- Rank documentation first, then dependency updates, frontend/backend changes, application changes, and infrastructure/workflow changes.
- Never put two PRs that change the same path in one batch. Defer the later PR for a fresh map after the earlier merge.
- Respect the configured batch limit. Deferred PRs remain open and are reconsidered in a later run.
- A missing worker report blocks that PR.
- Do not automatically close redundant-looking PRs. Compare exact changed-file and commit evidence, then request human disposition.
- A failed, canceled, stale, or missing required check blocks the PR.
- Keep the original PR branch and discussion intact. Use squash merge; never force-push or rewrite PR history.

## Serial execution loop

For each selected PR:

1. Fetch the live PR and current \`main\` SHA.
2. Re-run map/preflight against the current head and base SHAs.
3. Verify classic branch protection is readable and enforces administrators, at least one approving review, at least one required status check, and strict up-to-date branches. Stop if any condition is missing or unreadable.
4. Submit `gh pr merge --squash --match-head-commit <expected SHA>`; never pass `--admin` or enable auto-merge. GitHub remains the final merge authority; a merge-queue-only policy that rejects this request stops the batch.
5. Confirm GitHub reports \`merged=true\` and returns a merge commit SHA.
6. Wait for the repository's \`CI\` workflow on that exact merge SHA, \`event=push\`, \`branch=main\`.
7. Proceed only when the run concludes \`success\`. Stop on failure, timeout, missing run, changed head, conflict, or policy rejection.

This is a bounded loop, not an infinite retry. Retry only after a new discovery/map pass. Never weaken tests or security gates to make the loop green.

## Event model

- \`workflow_dispatch(mode=plan)\`: discovery, parallel mapping, reduction, artifact and summary only.
- \`workflow_dispatch(mode=merge)\`: same plan, then serial execution with live revalidation.
- A PAT or GitHub App token is required for merge mode so the resulting main push can trigger normal CI. The workflow's read-only \`GITHUB_TOKEN\` is not used to merge.
- After a successful merge, the main-branch \`push\` event starts normal CI. A failed main CI run stops the current batch.
- \`deploy_staging=true\` is honored only after every PR selected in that batch has merged and passed main CI. The existing \`CI\` workflow still enforces staging configuration and environment approvals.
- Production deployment remains tied to a reviewed version tag and the existing release workflow.

## Safety invariants

- Default mode is \`plan\`; no branch mutation occurs in plan mode.
- Merge mode can run only from \`refs/heads/main\`.
- No direct pushes to \`main\`, force merges, admin bypasses, automatic approvals, secret disclosure, or production deploys.
- Classic main-branch protection must enforce administrators, at least one approval, strict required checks, and at least one required status check; otherwise merge execution fails closed.
- GitHub required checks, reviews, merge queue, rulesets, and environment approvals are never bypassed.
- A 403/404, missing secret, API error, unknown mergeability, missing report, or unavailable CI result fails closed.
- Keep evidence artifacts for every run: discovery snapshot, per-PR map reports, reduced plan, and merge result.

## Completion definition

A PR is complete only when GitHub reports it merged, a merge commit SHA is recorded, and CI for that exact main SHA succeeds. A batch is complete only when every selected PR satisfies that definition. Deployment is complete only when the existing staging job reports success. A green orchestration plan alone is not a completed merge.
