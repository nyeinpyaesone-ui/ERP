# Technical Standards for jev-dynamic-detect

## Purpose
Provide configuration and execution standards for technical staff operating Jev AI integrated OpenCode agents in ERP.

## Design Principles
1. **Deterministic Routing**: Router scoring must be transparent, keyword-based, reproducible.
2. **Simulation First**: Default mode is agent_simulation. Real Jev calls require explicit approval.
3. **Audit Trail**: All decisions must record timestamp, duration, config version, standards compliance.
4. **Performance**: Context gathering cached with TTL. Git/CI calls minimized.
5. **Security**: No secrets in logs. Keys presence check only.

## Configuration Standards
Config file: `config.json`
- router.min_score: 2
- router.cache_ttl_seconds: 300
- erp_context.sources: git_last_commit, git_dirty, ci_status, test_coverage, error_budget
- jev.require_approval_for_real: true
- standards.compliance: ISO/IEC 27001, SOC 2
- output.pretty_print: true for human review

## Execution Style
- Entry point: `scripts/detect_optimized.py`
- Input: natural language task
- Output: Jev-compatible envelope with needs_review=true
- Never auto-execute actions. Decisions are advisory only.

## Performance Optimization
- lru_cache for git_last_commit and git_dirty
- Config loaded once per process
- Router invoked via subprocess with minimal args
- Audit duration_ms recorded for SLA monitoring

## Review Gates
- needs_review flag mandatory
- approval_required for real Jev
- Compliance check against ISO/IEC 27001 and SOC 2

## Operational Runbook
1. Run detect_optimized.py with task
2. Review routed_skill and scores
3. If routed_with_template, adapt template state with ERP evidence
4. Record decision in audit log
5. Escalate to human gate if needs_review true

## Change Management
- Update config.json for threshold changes
- Version config with git tags
- Validate templates with dry-run before release
