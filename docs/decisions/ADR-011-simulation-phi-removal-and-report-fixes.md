# ADR-011 — Remove double-phi in simulation + align report thresholds

**Date**: 2026-03-23
**Status**: Accepted
**Source**: Claude Code session — fix simulation/report parity with live scoring

## Decision
Remove `compute_phi` from simulation raw signal generation — phi is already applied inside `score_all_zones`. Align report recommendation thresholds with scoring levels (35/55/72).

## Values
- `simulation.py`: `traffic_base = bl["traffic"]["mu"] * (1 + ev_sig * 0.8)` — no phi_t multiplier
- `reports.py _recommendation_level`: 0→<35, 1→<55, 2→<72, 3→>=72 (was 56/76)
- `critical_zones` scoped to `focus_zones` (was `all_event_zones`)
- BLUF dominant signal: computed from breakdown (was hardcoded "trafic")
- DPS staffing: scaled by event weight multiplier (1.0/1.5/2.0)
- Confidence: `days_ahead < 0` → "retrospective"

## Rationale
- phi(t) was applied twice: once as raw signal modifier in simulation, once in `compute_risk()` via `score_all_zones` — inflating simulated scores vs live
- Recommendation thresholds 56/76 did not match scoring levels TENDU(55)/CRITIQUE(72)
- `critical_zones` was only checking event zones, missing neighbor spillover zones

## Consequences
- Simulated scores now match live scoring path exactly
- Reports use consistent threshold definitions across all components
- Staffing estimates scale with event weight (Fete des Lumieres gets more staff than a small event)

## DO NOT
- Re-add phi/temporal modifiers to raw signal generation in simulation — phi lives in `compute_risk` only
- Use different threshold values in reports vs `score_level()` — single source of truth in scoring.py

## Triggers
Re-read when: simulation.py, reports.py pre_event_report, _recommendation_level, scoring.py compute_phi, DPS staffing
