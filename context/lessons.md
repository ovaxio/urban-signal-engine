# Lessons & Known Gotchas — context/lessons.md

Load for any code change. Fast-access rules from past bugs and corrections.
For full decision context, see the relevant ADR in docs/decisions/.

## Scoring gotchas
- raw=0 → score≈29 is NORMAL (sigmoid baseline) — not a bug
- Double counting RISK+ANOMALY+CONV is INTENTIONAL — do not "fix"
- Transport passages_tcl is INVERTED (ADR-001) — do not "correct" the inversion
- ANOMALY uses max(z, 0) not abs(z) — abs caused calm nights to score MODERE
- Spread must NOT be double-counted in forecast — pass to compute_urban_score only
- Traffic fallback is _TRAFFIC_NEUTRAL (1.95), not 1.0 — wrong fallback collapses scores to 0
- top_causes only shows z > 0.5 — negative z are not causes of tension
- Event signal excluded from calibration (non-stationary)
- Seed data excluded from EWM smoothing (source != 'live')
- CALIBRATION_CUTOFF_TS filters pre-2026-03-15 data

## Workflow rules
- Run `python -m pytest tests/ -v` from backend/ before deploying
- Validate each scoring change theoretically + empirically (against real data)
- Minimum viable change first — no big-bang rewrites
- Pre-commit hook enforces pytest on staged .py files

## Frontend gotchas
- Never call fetch() directly — always use lib/api.ts
- Zone centroids: single source of truth in config.py, mirrored to constants.ts (ADR-006)

## Infrastructure gotchas
- Render filesystem is ephemeral — data lost on redeploy
- seed_history.py takes 2-3 min — gap after deploy is expected
- Do NOT suggest Postgres before first paying customer (ADR-005)
