# ADR-013 — Incident decay for extended forecast horizons

**Date**: 2026-03-23
**Status**: Accepted
**Source**: Claude Code session — fix forecast over-estimation at 6/12/24h

## Decision
Apply exponential decay (half-life 4h) to incident signal in extended horizon forecasts. Blend with historical baseline instead of raw max().

## Values
- `INCIDENT_FORECAST_HALFLIFE_MIN = 240` (config.py)
- Formula: `hist_inc + 0.5^(h/240) * max(inc_val - hist_inc, 0)`
- At 6h: 35% excess preserved, 12h: 12.5%, 24h: 1.6%
- Measured bias before fix: 6h=-8.2, 12h=-11.8, 24h=-15.4 pts

## Rationale
- Criter events have endtime but resolve early in practice (road clears before declared end)
- TomTom already decays to 0 beyond 120min — only Criter persists at extended horizons
- Historical profile (rush hour patterns) preserved as floor via `hist_inc`
- phi amplification preserved — applied downstream in compute_risk()
- Double decay on structural events is intentional (time-of-day × persistence)

## Consequences
- Extended forecast bias expected to reduce to -2 to -4 pts range
- Short horizons (30/60/120 min) NOT affected (different model, ADR-012)
- Rush hour patterns fully preserved (profile_at_h + phi_future intact)

## DO NOT
- Apply this decay to short horizons (they use 3-scenario model, ADR-012)
- Set half-life below 2h (eliminates incident signal at 6h) or above 8h (does not fix the bias)
- Remove `max(inc_val - hist_inc, 0)` guard — prevents decayed incidents from pulling below baseline

## Triggers
Re-read when: scoring.py _forecast_extended_horizon, config.py INCIDENT_FORECAST_HALFLIFE_MIN, forecast bias analysis
