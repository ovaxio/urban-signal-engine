# ADR-015 — Calibration Snapshot Fallback

**Date**: 2026-03-23
**Status**: Accepted
**Source**: Claude Code session — fix scoring divergence between local and Render deploys

## Decision
On startup, if live calibration fails (insufficient `source='live'` rows), load baselines from a committed `calibration_snapshot.json` file before falling back to hardcoded defaults.

## Values
- Fallback chain: live data (PRIMARY) > snapshot (FALLBACK) > hardcoded BASELINE (LAST RESORT)
- Snapshot path: `backend/data/calibration_snapshot.json`
- Snapshot max age warning: 14 days
- Snapshot regenerated alongside seed in `refresh_seed.sh`

## Rationale
- Render deploys recreate the DB from seed CSV (source='seed'), calibration filters on source='live' only
- Fresh deploys had 0 live rows, causing fallback to hardcoded BASELINE (stale since initial development)
- Snapshot preserves calibrated mu/sigma from local DB where live data accumulates continuously

## Consequences
- Render scores now match local within minutes of deploy (vs hours of live data accumulation)
- `refresh_seed.sh` now also exports the snapshot — must be run before deploy
- `/health` endpoint exposes `calibration.source` field: "live", "snapshot", or "hardcoded"

## DO NOT
- Change the `source='live'` filter in `get_calibration_baselines()` — seed data has different statistical properties
- Rely on the snapshot as permanent source — live calibration must take over as data accumulates
- Commit a snapshot older than 14 days without regenerating — stale baselines degrade scoring

## Triggers
Re-read when: main.py _apply_calibration, storage.py calibration, refresh_seed.sh, Render deploy process
