# Architecture Decision Records

Read relevant ADR before modifying any component listed in Triggers.

| ADR | Title | Status | Date | Triggers |
|-----|-------|--------|------|----------|
| [001](ADR-001-transport-signal-inversion.md) | Transport signal inversion | Accepted | 2026-03-15 | ingestion.py, passages_tcl, calibration queries |
| [002](ADR-002-signal-weights.md) | Signal weights | Accepted | 2026-03-12 | WEIGHTS constant, scoring weights, segment eval |
| [003](ADR-003-learning-calibration.md) | Learning + calibration | Accepted | 2026-03-19 | storage.py calibration, smoothing.py, evaluate_forecasts |
| [004](ADR-004-gtm-commercial.md) | GTM + commercial | Accepted | 2026-03-10 | pricing, segments, landing page copy |
| [005](ADR-005-product-architecture-mvp.md) | Product architecture MVP | Accepted | 2026-03-19 | dependencies, infra, new signal sources, DB migration |
