# ADR-018 — Forecast auto-learning (scenario weights, decay half-lives)

**Date**: 2026-03-31
**Status**: Accepted
**Source**: Claude Code session — forecast accuracy-driven parameter tuning

## Decision
Forecast parameters (scenario weights, decay/incident half-lives) are adjusted weekly via EMA from forecast_history bias, stored in calibration_snapshot.json.

## Values
- EMA alpha: 0.15 (~6 weeks memory), max step per cycle: ±0.05
- Weight bounds: each in [0.10, 0.80], normalized to sum=1
- Half-life bounds: [120, 480] min, max adjustment ±20 min/cycle
- Min evaluations per horizon before learning: 100
- Defaults: persist=0.25, maintained=0.55, proj=0.20, decay=240min, incident=240min

## Rationale
- Forecast bias drifts as traffic patterns change seasonally — static weights degrade
- EMA is conservative enough to avoid oscillation (6-week effective memory)
- Per-cycle clamps prevent catastrophic single-step jumps
- No ML library needed — pure arithmetic on existing forecast_history data

## Consequences
- forecast_learning.py owns parameter state (module-level _params)
- scoring.py reads params via get_forecast_params() — no more hardcoded weights
- calibration_snapshot.json gains `forecast_params` key (backward-compatible)
- Weekly calibration loop runs learning after baseline recalibration
- Admin endpoint GET /admin/forecast-learning exposes preview (dry-run)

## DO NOT
- Learn more frequently than weekly — insufficient new data between cycles
- Skip the min_n=100 guard — small samples produce noisy bias estimates
- Modify WEIGHTS, LAMBDA, ALPHA, BETA, THETA from this module — those are live scoring, not forecast
- Add ML libraries — EMA on bias is sufficient for this scale

## Triggers
Re-read when: forecast_learning.py, scoring.py _forecast_short_horizon, scoring.py _forecast_extended_horizon, config.py FORECAST_LEARN_*, main.py calibration_loop, admin forecast-learning endpoint
