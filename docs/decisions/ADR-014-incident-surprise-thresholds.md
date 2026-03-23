# ADR-014 — Harden incident_surprise detection thresholds

**Date**: 2026-03-23
**Status**: Accepted
**Source**: Claude Code session — reduce false-positive incident_surprise flags (41.6% → expected ~20%)

## Decision
Raise incident_surprise thresholds from `|delta| > 10 AND raw_incident > 0` to `|delta| > 15 AND raw_incident > 0.5`.

## Values
- Delta threshold: 15 (was 10)
- raw_incident threshold: 0.5 (was 0.0)
- Applied in: `evaluate_forecasts()` inline + `flag_incident_surprises()` backfill

## Rationale
- 41.6% of evaluations flagged as incident_surprise — captures routine incident decay, not genuine surprises
- Delta=11 with raw_incident=0.1 (minor event) is not a "surprise", it's normal forecast variance
- raw_incident > 0 catches any non-zero signal including baseline noise; 0.5 requires a real incident
- MAE clean was artificially flattering by excluding too many evaluations

## Consequences
- Fewer evaluations excluded from MAE clean → MAE clean rises slightly but becomes more honest
- MAE global drops as fewer high-delta evals are "explained away" by incident flag
- Historical flags in DB unchanged (only new evaluations use new thresholds)
- Backfill function also updated for consistency if re-run

## DO NOT
- Set delta threshold below 12 (would re-include normal forecast variance)
- Set raw_incident threshold above 1.0 (only major incidents would qualify, losing legitimate surprises)
- Backfill-reset existing incident_surprise flags without explicit instruction

## Triggers
Re-read when: forecast_storage.py evaluate_forecasts, flag_incident_surprises, incident_surprise thresholds
