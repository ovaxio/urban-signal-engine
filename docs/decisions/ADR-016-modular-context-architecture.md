# ADR-016 — Modular Context Architecture

**Date**: 2026-03-23
**Status**: Accepted
**Source**: Claude Code session — context engineering audit and refactoring

## Decision
Split CLAUDE.md (479 lines) into a routing file (<110 lines) + 5 domain modules in `context/`. SoloCraft agents load modules via `### context-modules` section.

## Values
- `context/scoring.md` — formula, signals, calibration, forecast
- `context/backend.md` — endpoints, loops, SQLite, APIs, env vars
- `context/frontend.md` — Next.js conventions, api.ts, styling
- `context/lessons.md` — gotchas from past bugs (loaded on every code change)
- `context/adr-process.md` — ADR triggers, format, lifecycle
- Routing: keyword-based, ambiguity-tolerant (load all matching modules)

## Rationale
- 0/5 critical rules were in the first 100 lines (guardrails at line 213)
- 48% of tokens were noise/derivable/duplicated for any given task
- SoloCraft agents without context-modules could identify risk but not evaluate changes
- scoring-guardian.md had stale transport weights (0.55/0.15 vs code 0.50/0.20)

## Consequences
- Guardrails now at lines 6-10, MVP constraints at lines 12-19
- Context loaded per task reduced by ~60%
- SoloCraft agents follow `### context-modules` to load domain knowledge

## DO NOT
- Put domain detail back in CLAUDE.md — keep it in context/ modules
- Create a context/ module under 15 lines — merge into existing module or CLAUDE.md
- Remove `context/lessons.md` from the "always load" rule — it prevents known regressions

## Triggers
Re-read when: CLAUDE.md structure, context/ modules, SoloCraft agent instructions, new context module
