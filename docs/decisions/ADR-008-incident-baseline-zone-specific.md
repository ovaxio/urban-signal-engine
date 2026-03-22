# ADR-008 — Zone-specific incident baseline (no-incident fallback)

**Date**: 2026-03-22
**Status**: Accepted
**Source**: Claude Code session — architectural fix false-positive incident signal

## Decision
When no incidents are active for a zone, use the zone-calibrated `µ_incident` as fallback
instead of the global constant 1.70, so that z_incident ≈ 0 for quiet zones.

## Values
```python
# Before (wrong)
_INCIDENT_BASELINE_MU = 1.70  # global constant used everywhere
current[z] = _zone_score_from_weights([])  # → 1.70 for all zones

# After (correct)
mu_inc = _effective_baseline(z)["incident"]["mu"]  # zone-specific
current[z] = _zone_score_from_weights([], fallback_mu=mu_inc)
# Croix-Rousse: mu≈0.95 → z_incident≈0 → score ~36 instead of 47
```

## Rationale
- Global fallback 1.70 produced z_incident ≈ +1.5σ for zones with µ<1.70 (Croix-Rousse, Fourvière, Confluence)
- Calibration derives per-zone µ from historical data precisely to avoid this mismatch
- "No incidents" is semantically equivalent to "baseline level" — z should be ≈ 0

## Consequences
- Zones with calibrated µ_incident < 1.70 no longer get phantom tension from the incident signal
- Score impact: −10 to −15 points for quiet zones during no-incident periods
- Three fix sites: `neutral_c`, `current[z]`, `schedule[z]` in `fetch_incidents()`
- `_zone_score_from_weights` now requires `fallback_mu` parameter (default 0.0)

## DO NOT
- Do NOT revert to a global constant fallback — this is the root cause of the false positive
- Do NOT use `fallback_mu=0.0` for incident signal (0.0 means "no data", not "quiet zone")
- Do NOT exclude zones from calibration to work around this — fix the fallback instead

## Triggers
Re-read when: `ingestion.py fetch_incidents()`, `_zone_score_from_weights`, `_effective_baseline`,
`scoring.py ZONE_BASELINES`, `calibration_loop`, `admin.py recalibrate`
