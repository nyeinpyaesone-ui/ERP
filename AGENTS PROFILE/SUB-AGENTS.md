# SUB-AGENTS — Roster, Routing & Prompt Templates

Scope: **who does the work** — delegation strategy for opencode's Task tool.
Scope of *how* lives in [TOOLS.md](TOOLS.md) (tools) and [SKILLS.md](SKILLS.md)
(task → approach matrix).

## Roster (available subagent types)

| Type | Strengths | Limits | Use for |
|------|-----------|--------|---------|
| `explore` | Fast file/pattern search, reads, structured digests; low context cost | **Research only** — no writes | Finding files, summarizing docs/CI/config, "what/where" questions |
| `general` | Full autonomy across steps (search → edit → verify) | Consumes more context; must be told whether to write code | Multi-step units of work that don't need my own judgment |

Everything else (edits to profile/config, commits, permission-gated commands,
user communication) stays **with the main agent**.

## Routing rules

1. **Read-heavy fan-out → `explore`.** ≥3 files to understand, or open-ended
   search ("how does X work"), or digesting large outputs (tool-output dumps).
2. **Self-contained work unit → `general`.** Clear deliverable + verifiable
   outcome (e.g., "add tests for Y, run pytest"). Always state: write or research,
   and how to verify.
3. **Never delegate:** `opencode.json`/skill/config edits (requires
   `customize-opencode` skill), git commit/push, anything behind an ask-gate,
   writing `AGENTS PROFILE/*` (my memory must be my own observation).
4. **Parallelize** independent calls in one message (multiple Task/Bash/Glob);
   sequence only true dependencies (e.g., mkdir → write).
5. **One owner per file** — before delegating an edit, check I'm not editing the
   same file concurrently.
6. Delegation is optional for <3-file tasks; doing it directly is often cheaper.

## Handoff context (what every Task prompt must contain)

- Working dir: `/home/admin/ERP`.
- Research vs write (explicit one-word instruction).
- Exact files/paths/keywords to target; what to ignore (`node_modules`, `.git`,
  `backend/venv`, `*.heapsnapshot`, `backups/`).
- Depth: quick | medium | very thorough.
- **Return format:** compact digest with headings, no bulk file pastes, ≤N words.
- Verification expectation (command to run / evidence to quote).

## Template (copy-ready)

```
Task: <3-5 word label>
Working dir: /home/admin/ERP
Mode: research only | write code
Target: <paths/keywords>; ignore node_modules, .git, venv, *.heapsnapshot
Do: <steps> …
Verify: <command or evidence>
Return: structured digest, <max> words, headings per item, quote file:line for claims.
```

## Escalation back to main agent

Sub-agent reports any of: write conflict, unexpected dirty diff, failing test it
cannot fix within scope, request to touch secrets/prod/`opencode.json`, or a fact
that contradicts [MEMORY.md](MEMORY.md) §1 → stop and hand back with evidence;
main agent logs drift in MEMORY §4 before proceeding.

## Parallel pattern for common flows

- **Orientation (session start):** 1× `explore` (repo state digest) ∥ local
  `git status`/`git log` — then reconcile with MEMORY §1.
- **Feature/fix:** `explore` (locate) → main agent (edit) → `general` (write+run
  tests) → main agent (review diff, heartbeat check, report).
- **Doc sync:** `explore` (gather deltas) → main agent (write; only owner of
  MEMORY/AGENTS facts).
