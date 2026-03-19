# ADR-005 — Product architecture and MVP constraints
Date: 2026-03-19 | Status: Accepted | Source: Claude Code Phase 1/2/audit/PDF sessions
## Decision
SQLite + FastAPI + Next.js stays until first paying customer. No premature infra migration.
## Stack (immutable until first paying customer)
- **Backend**: FastAPI 0.128 + SQLite | **Frontend**: Next.js 16 + CSS Modules (no Tailwind)
- **Deploy**: Render free (backend) + Vercel (frontend) | No auth on public API
- **PDF**: fpdf2 (pure Python) | **RSS**: Lyon Capitale, 10min cache, enrichment-only (no scoring)
## Operational endpoints
- /zones/simulate (24h), /reports/pre-event/{name} + /pdf, /reports/impact/{name}
- /admin/calibration (audit), signals_history (incident_label since 2026-03-15)
- forecast_history (MAE, incident_surprise), /zones/forecast/accuracy
## Known issues (do not re-investigate)
- Deploy jump in history chart: seed freshness, root cause unknown
- Waze: 403/404 on all endpoints — needs Waze for Cities partnership
- X/Twitter: $100/mois API — not worth before first customer
## DO NOT
- Migrate Postgres, start Tailwind, add auth before first paying customer
- Add dependencies without justification (current: 8 + fpdf2)
- Fetch RSS >1x/10min or add RSS to scoring. Implement auto email before manual Resend.
## Triggers
Re-read when: new dependency, infra change, new signal source, frontend stack, DB migration
