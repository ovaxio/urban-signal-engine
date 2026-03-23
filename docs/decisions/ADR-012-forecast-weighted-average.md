# ADR-012 — Forecast short-horizon: weighted average replaces max strategy

**Date**: 2026-03-23
**Status**: Accepted
**Source**: Claude Code session — forecast bias correction (-4.1 pts on 30/60min)

## Decision
Short-horizon forecast (30/60/120 min) uses weighted average of 3 scenarios instead of max(). Safety floor at 70% of max scenario.

## Values
- `W_MAINTAINED = 0.55` (0.70 when no fa_proj)
- `W_PERSIST = 0.25` (0.30 when no fa_proj)
- `W_PROJ = 0.20` (only when incident_schedule active)
- Safety floor: `fa = max(fa_avg, fa_max * 0.70)`
- Target residual bias: +1 to +2 pts (intentional over-estimation)

## Rationale
- max() caused systematic -4.1 pts over-estimation on 30/60 min horizons
- Maintained scenario is most likely at short horizons (signals persist + phi adjustment)
- Security segment prefers slight over-estimation over under-estimation
- Safety floor prevents average from dropping >30% below worst-case

## Consequences
- Forecast MAE expected to improve by ~2-3 pts on 30/60 min
- Residual positive bias preserved for security use case
- Extended horizons (6/12/24h) unchanged (structural model, not scenario-based)

## DO NOT
- Set W_MAINTAINED below 0.50 (it is the most probable scenario by definition)
- Remove the safety floor (fa_max * 0.70) — it protects against under-estimation
- Apply weighted average to extended horizons (different model, different assumptions)
- Target zero bias — positive bias is intentional for security segment

## Triggers
Re-read when: scoring.py _forecast_short_horizon, forecast bias analysis, scenario weights
