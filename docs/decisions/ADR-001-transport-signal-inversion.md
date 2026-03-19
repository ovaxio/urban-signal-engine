# ADR-001 — Transport signal inversion
Date: 2026-03-15 | Status: Accepted | Source: Claude.ai GTM + scoring audit
## Decision
passages_tcl inverted to disruption model: `1.0 - min(count / seuil, 1.0)`. Fewer buses = higher tension.
## Values (immutable until explicitly changed)
- **Formula**: `parcrelais * 0.30 + passages_tcl * 0.55 + velov * 0.15` (passages_tcl inverted)
- **Baseline post-inversion**: mu=0.50, sigma=0.28
- **CALIBRATION_CUTOFF_TS**: `"2026-03-15T00:00:00"` in storage.py
- **Filter**: `source='live' AND ts >= CALIBRATION_CUTOFF_TS` in all calibration queries
## Rationale
- CityPulse EU FP7: active transport = good service, not tension. Old model was semantically inverted.
- All data before 2026-03-15 has corrupted transport baselines (old activity model)
## Consequences
- Seed rows and pre-cutoff live rows permanently excluded from calibration
- Per-zone transport baselines recalibrated from post-inversion data only
## DO NOT
- Revert to activity model (high count = high tension)
- Remove CALIBRATION_CUTOFF_TS filter or recalibrate on seed/pre-inversion data
- Question this without 50+ evaluated events with ground truth
## Triggers
Re-read when: ingestion.py transport, storage.py calibration queries, passages_tcl/parcrelais/velov weights
