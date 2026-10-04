# AGENTS PROFILE — Index

Companion profile set for the root [`AGENTS.md`](../AGENTS.md) (the authoritative
operational instructions for this repo). This folder holds the **agent identity,
memory, and coordination layer** that AGENTS.md deliberately does not carry.

> Rule of one source of truth: **AGENTS.md owns repo facts** (structure, commands,
> pitfalls). This folder owns **state, identity, and coordination** (what changed,
> who does what, when to verify). Never duplicate a fact here that lives in
> AGENTS.md — link to it instead.

## Files & Responsibilities (non-overlapping)

| File | Scope | Read when |
|------|-------|-----------|
| [README.md](README.md) | This index, load order, sync rules | Session start |
| [MEMORY.md](MEMORY.md) | Durable cross-session state: snapshots, decisions, progress, drift, open threads | Session start + end |
| [SOUL.md](SOUL.md) | Identity, values, tone, ethics, anti-patterns | Session start (loaded with MEMORY) |
| [SUB-AGENTS.md](SUB-AGENTS.md) | Sub-agent roster, routing rules, prompt templates | Delegating work |
| [TOOLS.md](TOOLS.md) | Tool/MCP inventory, permission gates, command cheatsheet | Before using a tool/MCP |
| [HEARTBEATS.md](HEARTBEATS.md) | Cadence: start/mid/end checklists, verification gates | Each task milestone |
| [SKILLS.md](SKILLS.md) | Task → skill/approach → verification matrix | Planning any task |
| [IMPROVEMENTS.md](IMPROVEMENTS.md) | Prioritized repo system-improvement backlog (P0–P2) | Picking up work |

## Load order (opencode `instructions` in `../opencode.json`)

1. `AGENTS.md` — repo facts, commands, pitfalls (always).
2. `AGENTS PROFILE/MEMORY.md` — state & drift (always).
3. Everything else — **on demand**, opened via Read when the task type calls for it
   (see routing in [SKILLS.md](SKILLS.md)). Keeping SOUL/TOOLS/HEARTBEATS/SUB-AGENTS
   out of the auto-load path avoids context bloat and staleness.

## Sync rules

- **AGENTS.md is ahead** on repo structure/commands; this folder is ahead on
  *verified runtime state* (e.g., npm availability, migration count, dirty worktree).
  When MEMORY.md records a delta against AGENTS.md, it is an **open thread** until
  AGENTS.md is corrected — see `MEMORY.md → Drift vs AGENTS.md`.
- Every claim in MEMORY.md's Verification Ledger must come from a command actually
  run in a session (tool output), never from assumption.
- `IMPROVEMENTS.md` is the only place the improvement backlog lives; MEMORY.md links
  to its items by ID (`IMP-P0-1`), never re-lists them.
- No secrets, tokens, or `.env` values anywhere in this folder (names only).
- Session artifacts (`session-*.md`, `.opencode/session*`) are gitignored — do not
  store durable memory there.

## Maintenance

- Update `MEMORY.md` at **session end** (append, don't rewrite history).
- Quarterly or on any merge to `main`: re-verify SOUL/TOOLS/HEARTBEATS facts.
- New profile file? Add a row above, a routing rule in `SKILLS.md`, and link it
  from `AGENTS.md → Agent Profile`.
