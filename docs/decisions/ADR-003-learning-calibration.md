# ADR-003 — Learning mechanism and calibration
Date: 2026-03-19 | Status: Accepted | Source: Claude Code audit + implementation
## Decision
Manual-assisted validation only. No automatic weight updates. Recalibration: mu/sigma only, weekly batch.
## Values (immutable until explicitly changed)
- **Recalibration**: weekly 03:00 Paris, min_count=500 (startup: 96)
- **Filters**: `source='live' AND ts >= CALIBRATION_CUTOFF_TS`, min 50 rows/signal
- **MIN_SIGMA**: traffic=0.15, weather=0.10, transport=0.20, incident=0.15
- **incident_surprise**: `ABS(delta) > 10 AND raw_incident > 0` via get_raw_incident_at()
- **Forecast eval**: +/-5min window, `actual_score IS NULL` prevents double-eval
## Safeguards
- calibration_log table: per-signal audit (old/new mu/sigma, row_count, skipped)
- /admin/calibration: last 50 entries + large_shifts (>15%). /health: stale_warning >25h
- Event signal excluded from calibration (non-stationary)
## DO NOT
- Implement auto weight gradients, online calibration, or ML forecast model
- Recalibrate on <50 rows or data before CALIBRATION_CUTOFF_TS
- Remove calibration_log audit trail
## Triggers
Re-read when: storage.py calibration, evaluate_forecasts(), smoothing.py, "learning"/"auto-improving"
