Read this file + docs/decisions/README.md before any task.

# Urban Signal Engine — CLAUDE.md

## Guardrails — STOP before modifying
1. Signal weights, transport composition, smoothing → HIGH RISK → user confirmation + ADR
2. Scoring formula (sigmoid, λ, α, β, θ) → HIGH RISK → user confirmation + ADR
3. Calibration logic or baselines → HIGH RISK → user confirmation + ADR
4. seed_history.py → read fully before modifying
5. Any new dependency → justify first

## MVP constraints — non-negotiable
- Solo founder, limited time
- SQLite until first paying customer — do NOT suggest Postgres
- No Tailwind migration without explicit instruction
- No test suite required — manual testing only (but run pytest if tests exist)
- All frontend fetch via `lib/api.ts` — NEVER fetch() in components
- No "use client" without written justification
- Double counting RISK+ANOMALY+CONV is INTENTIONAL — do not "fix"

## Project
Real-time urban tension scoring API/SaaS for Lyon (12 zones, score 0-100).
Stage: MVP — first paying customer not yet signed.

## Stack
- Backend: FastAPI 0.128 + SQLite, Python 3.11, deployed on Render (free tier)
- Frontend: Next.js 16 App Router, React 19, TypeScript, CSS Modules
- Observability: Sentry + PostHog | Rate limiting: slowapi 30/min
- Dependencies: httpx, pydantic 2, sentry-sdk | recharts, react-leaflet, leaflet

## Context routing — load by task domain
Match keywords below. If a task touches multiple domains, load ALL matching modules.

| Task keywords | Load |
|--------------|------|
| score, signal, weight, calibration, phi, forecast, ingestion, anomaly, risk, spread | `context/scoring.md` |
| endpoint, API, loop, deploy, env, SQLite, alert, storage, auth, zone list | `context/backend.md` |
| component, page, dashboard, UI, map, chart, style, layout, theme | `context/frontend.md` |
| ADR, decision, architecture record | `context/adr-process.md` |

Always load `context/lessons.md` for any code change.

## Target market
Primary: securite privee / evenementielle Lyon (rapport 390 EUR HT one-shot, abo 490 EUR/mois).
Secondary (week 6+): logistique / livraison (API 149 EUR/mois).
Detail in `.claude/agents/use-gtm.md`. Segments exclus: collectivites, police, assureurs (ADR-004).

## Decision log
Decisions in `docs/decisions/`. Read relevant ADR before modifying any Triggers component.

| ADR | Title | Triggers |
|-----|-------|----------|
| 001 | Transport signal inversion | ingestion.py, passages_tcl, calibration |
| 002 | Signal weights | WEIGHTS constant, scoring weights |
| 003 | Learning + calibration | storage.py calibration, smoothing.py |
| 004 | GTM + commercial | pricing, segments, landing page copy |
| 005 | Product architecture MVP | dependencies, infra, new signal sources |
| 006 | Zone centroids source of truth | config.py ZONE_CENTROIDS, frontend/domain/constants.ts, ZoneMap.tsx |
| 007 | Request logging strategy | main.py middleware, storage.py request_logs |
| 008 | Zone-specific incident baseline | ingestion.py fetch_incidents(), _effective_baseline |
| 009 | Time-slot baselines | storage.py calibration, scoring.py _effective_baseline |
| 010 | Clamp z negatifs dans RISK | scoring.py compute_risk, _NEUTRAL_WHEN_LOW |
| 011 | Remove double-phi + align report thresholds | simulation.py, reports.py, DPS staffing |
| 012 | Forecast weighted average | scoring.py _forecast_short_horizon, forecast bias |
| 013 | Incident decay extended forecast | scoring.py _forecast_extended_horizon, INCIDENT_FORECAST_HALFLIFE_MIN |
| 014 | Incident_surprise thresholds | forecast_storage.py evaluate_forecasts, flag_incident_surprises |
| 015 | Calibration snapshot fallback | main.py _apply_calibration, storage.py calibration, refresh_seed.sh |
| 016 | Modular context architecture | CLAUDE.md, context/, .claude/agents/, SoloCraft context-modules |
| 017 | WMO granular weather score scale | config.py WEATHER_WMO_SCORE, ingestion.py _weather_score_from_values, _wmo_contribution |

## Known issues — do not re-investigate without new data
- Deploy jump in history chart: seed is fresh (pre-commit, ~2-3min delta)
- Transport TCL signal was inflated (activity model bug) → fixed by inversion (ADR-001)

## Self-improvement
After any correction by Guillaume, add a rule in the relevant context/ module.
Append only — never rewrite existing rules.

## SoloCraft

### stack
FastAPI 0.128 + SQLite + Python 3.11, Render | Next.js 16 + React 19 + TS + CSS Modules, Vercel

### target
Securite privee Lyon: rapport 390 EUR HT, abo 490 EUR/mois | Logistique (S6+): API 149 EUR/mois

### constraints
SQLite only, no Tailwind, no deps without justification, manual testing, fetch via lib/api.ts

### high-risk-zones
config.py WEIGHTS/LAMBDA/ALPHA/BETA/THETA, scoring.py sigmoid, ingestion.py transport, storage.py+main.py calibration, seed_history.py

### context-modules
Before analyzing or implementing, load the relevant context modules based on files touched:
- Scoring/signals/config/forecast → read `context/scoring.md`
- Backend/API/storage/deploy → read `context/backend.md`
- Frontend/UI/components → read `context/frontend.md`
- Any code change → read `context/lessons.md`

### domain-agents
| Domain | Agent |
|--------|-------|
| Scoring / calibration / signaux | scoring-guardian |
| Commercial / GTM / pricing | use-gtm |
| Deploiement / ops | use-ops |

### decisions-dir
docs/decisions/

### adr-format
Max 30 lines, sections: Decision, Values, Rationale, Consequences, DO NOT (min 2), Triggers. Full spec: context/adr-process.md
