# Architecture Decision Records

Read relevant ADR before modifying any component listed in Triggers.

| ADR | Title | Status | Date | Triggers |
|-----|-------|--------|------|----------|
| [001](ADR-001-transport-signal-inversion.md) | Transport signal inversion | Accepted | 2026-03-15 | ingestion.py, passages_tcl, calibration queries |
| [002](ADR-002-signal-weights.md) | Signal weights | Accepted | 2026-03-12 | WEIGHTS constant, scoring weights, segment eval |
| [003](ADR-003-learning-calibration.md) | Learning + calibration | Accepted | 2026-03-19 | storage.py calibration, smoothing.py, evaluate_forecasts |
| [004](ADR-004-gtm-commercial.md) | GTM + commercial | Accepted | 2026-03-10 | pricing, segments, landing page copy |
| [005](ADR-005-product-architecture-mvp.md) | Product architecture MVP | Accepted | 2026-03-19 | dependencies, infra, new signal sources, DB migration |
| [006](ADR-006-zone-centroids-source-of-truth.md) | Zone centroids source of truth | Accepted | 2026-03-21 | config.py ZONE_CENTROIDS, frontend/domain/constants.ts, ZoneMap.tsx |
| [007](ADR-007-request-logging-strategy.md) | Request logging strategy (SQLite MVP) | Accepted | 2026-03-21 | main.py middleware, storage.py request_logs, external logging SaaS |
| [008](ADR-008-incident-baseline-zone-specific.md) | Zone-specific incident baseline | Accepted | 2026-03-22 | ingestion.py fetch_incidents(), _zone_score_from_weights, _effective_baseline, ZONE_BASELINES |
| [009](ADR-009-time-slot-baselines.md) | Time-slot baselines | Accepted | 2026-03-23 | storage.py calibration, scoring.py _effective_baseline, main.py _apply_calibration |
| [010](ADR-010-neutral-when-low-all-signals.md) | Clamp z négatifs traffic/transport dans RISK | Accepted | 2026-03-23 | scoring.py compute_risk, _NEUTRAL_WHEN_LOW, RISK formula |
| [011](ADR-011-simulation-phi-removal-and-report-fixes.md) | Remove double-phi in simulation + align report thresholds | Accepted | 2026-03-23 | simulation.py, reports.py pre_event_report, _recommendation_level, DPS staffing |
| [012](ADR-012-forecast-weighted-average.md) | Forecast short-horizon: weighted average replaces max | Accepted | 2026-03-23 | scoring.py _forecast_short_horizon, forecast bias, scenario weights |
| [013](ADR-013-incident-decay-extended-forecast.md) | Incident decay for extended forecast horizons | Accepted | 2026-03-23 | scoring.py _forecast_extended_horizon, config.py INCIDENT_FORECAST_HALFLIFE_MIN |
| [014](ADR-014-incident-surprise-thresholds.md) | Harden incident_surprise detection thresholds | Accepted | 2026-03-23 | forecast_storage.py evaluate_forecasts, flag_incident_surprises |
| [015](ADR-015-calibration-snapshot-fallback.md) | Calibration snapshot fallback | Accepted | 2026-03-23 | main.py _apply_calibration, storage.py calibration, refresh_seed.sh, Render deploy |
| [016](ADR-016-modular-context-architecture.md) | Modular context architecture | Accepted | 2026-03-23 | CLAUDE.md structure, context/ modules, SoloCraft agent instructions |
