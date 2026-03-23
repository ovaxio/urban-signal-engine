Read CLAUDE.md and docs/decisions/README.md before starting any task.

# Urban Signal Engine — CLAUDE.md

## Project overview
Real-time urban tension scoring API/SaaS for Lyon, France.
Score 0-100 per zone + 6-horizon forecast + history + impact reports.
Stage: MVP — first paying customer not yet signed.

## Stack
- Backend: FastAPI 0.128 + SQLite, Python 3.11, deployed on Render (free tier)
- Frontend: Next.js 16 App Router, React 19, TypeScript, CSS Modules (Tailwind migration planned, not started)
- Observability: Sentry (backend + frontend), PostHog analytics (frontend)
- Rate limiting: slowapi (default 30/min)
- Dependencies: httpx, pydantic 2, sentry-sdk | recharts, react-leaflet, leaflet

## Repository structure
```
urban-signal-engine/
├── backend/
│   ├── main.py               # FastAPI app, lifespan, background loops
│   ├── config.py             # WEIGHTS, LAMBDA, ALPHA, BETA, THETA, thresholds, API URLs, zone centroids
│   ├── models.py             # Pydantic response models
│   ├── routers/
│   │   ├── zones.py          # /zones/* — scores, detail, forecast, history, alerts, simulate
│   │   ├── admin.py          # /admin/* — API key CRUD (ADMIN_SECRET protected)
│   │   ├── reports.py        # /reports/* — impact reports (period + event-based)
│   │   └── contact.py        # /contact — contact form
│   ├── services/
│   │   ├── ingestion.py      # Signal fetching: weather, traffic, incidents, transport (parcrelais/TCL/velov)
│   │   ├── scoring.py        # Score model: normalize → risk/anomaly/conv/spread → sigmoid → 0-100
│   │   ├── orchestrator.py   # Refresh cycle: fetch → score → persist → forecast → alerts → cache
│   │   ├── smoothing.py      # EWM smoothing (α=0.4, window=6)
│   │   ├── storage.py        # SQLite persistence (signals_history, alerts_log, calendar_vacances)
│   │   ├── forecast_storage.py # Forecast accuracy: save, evaluate, flag incident_surprises
│   │   ├── alerts.py         # Threshold crossing detection + webhook dispatch
│   │   ├── events.py         # Static 2026 Lyon event calendar
│   │   ├── calendar.py       # Vacances scolaires refresh (education.gouv.fr API)
│   │   ├── calendar_utils.py # day_type classification (semaine/mercredi/vacances/weekend)
│   │   └── auth.py           # API key generation/validation
│   ├── scripts/
│   │   ├── seed_history.py   # Seed historical data (pre-commit hook, ~2-3min delta)
│   │   └── backup_db.py      # DB backup (auto every 6h)
│   └── data/                 # SQLite DB + seed CSV (gitignored)
└── frontend/
    ├── app/
    │   ├── layout.tsx         # Root layout (dark/light theme, Sentry, PostHog)
    │   ├── page.tsx           # Landing page (marketing)
    │   ├── dashboard/page.tsx # Main dashboard — zone grid + map + alerts
    │   ├── zones/[id]/page.tsx # Zone detail — score, components, forecast, history chart
    │   ├── admin/forecast-accuracy/page.tsx # Forecast accuracy stats
    │   ├── reports/page.tsx   # Impact report viewer
    │   ├── contact/page.tsx
    │   ├── mentions-legales/page.tsx
    │   └── politique-confidentialite/page.tsx
    ├── components/
    │   ├── zone/              # ZoneCard, ZoneGrid, ZoneForecast, ZoneSignals, ZoneTransportDetail, etc.
    │   ├── chart/             # ZoneHistoryChart (recharts)
    │   ├── map/               # ZoneMap (react-leaflet)
    │   ├── report/            # ImpactReportView, ReportViewer
    │   ├── alert/             # AlertPanel
    │   ├── layout/            # AppHeader, AppNav, DashboardHeader, FilterBar, MarketingNav, SimBanner
    │   ├── theme/             # ThemeProvider, ThemeToggle
    │   ├── analytics/         # PostHogScript
    │   └── ui/                # ScoreBar, StatCard, ErrorState
    ├── domain/
    │   ├── types.ts           # All domain types (ZoneDetail, Forecast, ImpactReport, ForecastAccuracy, etc.)
    │   ├── constants.ts       # SIGNAL_LABELS, EVENT_ICONS, ZONE_CENTROIDS, COMPONENT_KEYS
    │   └── scoring.ts         # Frontend scoring utilities
    ├── hooks/                 # useCountUp
    └── lib/
        └── api.ts             # All API calls — NEVER call fetch() directly in components
```

## Backend — scoring model

### UrbanScore formula (0-100)
```
score = sigmoid(alert + λ₄·spread) × 100
  alert  = λ₁·RISK + λ₂·ANOMALY + λ₃·CONV
  spread = K · Σ max(alert_neighbor, 0)
```
Sigmoid centered at raw=1.5 (k=0.6):
- raw=0 → score≈29 (CALME, all signals at baseline — this is neutral, NOT 0)
- raw=1.5 → score=50 (median tension)
- raw=3.0 → score≈71 (CRITIQUE threshold)

### Score levels
- 0-34: CALME — normal operation
- 35-54: MODÉRÉ — weak signals, attention recommended
- 55-71: TENDU — confirmed tension, active monitoring
- 72-100: CRITIQUE — converging strong signals

### Components
- **RISK** = φ(t) × Σ(wₛ × max(zₛ, 0)) — weighted risk, all z clampés ≥0 (ADR-010)
- **ANOMALY** = Σ(αₛ × max(zₛ, 0)) — individual peak detection (ReLU, positive only)
- **CONV** = min(Σ(βₖ × gate(zₐ) × gate(zᵦ)), 2.0) — signal convergence (co-occurrence)
- **SPREAD** = K × Σ max(alert_neighbor, 0) — spatial diffusion (contagion, not relief)
- **φ(t)** = temporal profile with 4 variants: semaine, mercredi, vacances, weekend

Double counting (RISK + ANOMALY + CONV) is intentional — each captures a different aspect.

### 5 signals (config.py)
| Signal    | Weight | Source                              | Range     |
|-----------|--------|-------------------------------------|-----------|
| traffic   | 0.35   | Grand Lyon Criter WFS (V/O/R/N)    | 0.5 – 3.0 |
| incident  | 0.25   | Criter events + TomTom incidents    | 0.0 – 3.0 |
| transport | 0.15   | TCL parcrelais + passages + Vélo'v  | 0.0 – 1.0 |
| weather   | 0.15   | Open-Meteo (precip + wind + WMO)    | 0.0 – 3.0 |
| event     | 0.10   | Static 2026 calendar                | 0.0 – 3.0 |

### Transport signal composition (ingestion.py)
```
parcrelais × 0.30 + passages_tcl × 0.50 + velov × 0.20
```
passages_tcl is INVERTED: `1.0 - min(count / seuil, 1.0)` (fewer buses = more tension).

### EWM smoothing (smoothing.py)
α=0.4, window=6 rows, reads raw_* columns from signals_history.
Only applies to source='live' rows (excludes seed data).

### Calibration (main.py)
Auto-recalibration weekly at 3:00 AM Paris time from raw_signals history.
Per-zone baselines override global baseline. Event signal excluded (non-stationary).

### Forecast model (scoring.py)
- Short horizons (30/60/120 min): 3-scenario max-wins from real-time signals
  - Persistence (decay), maintained situation (φ ratio), Criter projection
- Extended horizons (6/12/24h): structural model
  - Historical profiles + weather forecast + persistent incidents + φ(t)
- Accuracy tracked: forecast_history table with MAE per horizon, incident_surprise flags

### Background loops (main.py lifespan)
1. **refresh_loop** — fetch+score every 60s (CACHE_TTL_SECONDS)
2. **calibration_loop** — recalibrate baselines every 7 days at 3:00 AM
3. **backup_loop** — DB backup every 6h
4. **calendar_loop** — vacances scolaires refresh every 90 days

### Alert system (alerts.py)
Threshold crossing detection: TENDU (≥55), CRITIQUE (≥72), CALME return (<35).
30 min cooldown per zone. Persisted in alerts_log + webhook dispatch if configured.

## Backend — API endpoints
```
GET  /health                              # Status + baseline values
GET  /zones/scores?min_score=&level=&sort= # All 12 zones
GET  /zones/{id}/detail                   # Full detail + neighbors + incidents + transport_detail
GET  /zones/{id}/forecast                 # 6 horizons (30m/1h/2h/6h/12h/24h)
GET  /zones/{id}/history?limit=48         # Historical scores
GET  /zones/alerts?limit=50              # Threshold crossing alerts
POST /zones/refresh                       # Force refresh (background)
GET  /zones/forecast/accuracy             # MAE stats per horizon
GET  /zones/simulate?date=YYYY-MM-DD      # Event simulation for any date
GET  /zones/{id}/simulate-detail?date=    # Simulated zone detail
GET  /reports/impact?start=&end=          # Impact report (period)
GET  /reports/impact/event/{name}         # Impact report (calendar event)
GET  /reports/events                      # Available calendar events
POST /admin/api-keys                      # Create API key (ADMIN_SECRET)
GET  /admin/api-keys                      # List keys
DELETE /admin/api-keys/{prefix}           # Revoke key
```

## Frontend — key decisions

### Server/Client boundary
Not yet audited. Most components are "use client" by default.
Do not add "use client" without justification.
Prefer Server Components for data display, Client Components only for interactivity.

### API communication
All fetch calls go through `frontend/lib/api.ts` — NEVER call fetch() directly in components.
Backend base URL: `NEXT_PUBLIC_API_BASE` env var.

### Styling
Current: CSS Modules + inline styles. Tailwind migration planned but NOT started.
Do not begin Tailwind migration without explicit instruction.

## 12 Lyon zones (config.py ZONE_CENTROIDS)
part-dieu, presquile, vieux-lyon, perrache, gerland, guillotiere,
brotteaux, villette, montchat, fourviere, croix-rousse, confluence

Neighbor graph defined in scoring.py NEIGHBORS dict.

## External APIs
- **Grand Lyon Criter WFS** (open data, no quota): traffic state (pvotrafic) + incidents (pvoevenement)
- **TomTom Incident Details v5**: incidents with delay/magnitude (cached 30min, budget ≤2500 req/month)
- **Open-Meteo**: current weather + 48h hourly forecast (free, no key)
- **Grand Lyon data** (HTTP Basic Auth, GRANDLYON_LOGIN/PASSWORD): TCL passages, parcrelais, Vélo'v
- **education.gouv.fr**: vacances scolaires (refreshed every 90 days)
- Static 2026 Lyon event calendar (OpenAgenda/Ticketmaster ruled out)

## Environment variables (render.yaml)
TOMTOM_API_KEY, GRANDLYON_LOGIN, GRANDLYON_PASSWORD, ENABLE_HISTORY,
ALERT_WEBHOOK_URL, ALLOWED_ORIGINS, ADMIN_SECRET, SENTRY_DSN, SENTRY_ENV

## SQLite persistence
DB at `backend/data/urban_signal.db`. Recreated + seed loaded at each Render deploy (ephemeral filesystem).
Tables: signals_history, alerts_log, forecast_history, calendar_vacances, api_keys.
Do NOT suggest migrating to Postgres before first paying customer.

## Known issues — do not re-investigate without new data
- Deploy jump in history chart: seed is fresh (pre-commit, ~2-3min delta). Root cause not identified.
- Transport TCL signal was inflated across all zones (activity model bug). Fixed by inversion.

## MVP constraints — non-negotiable
- Solo founder, limited time on USE
- SQLite stays until first paying customer
- No test suite required — manual testing only
- No authentication layer on public API yet (admin endpoints use ADMIN_SECRET)
- Do not add dependencies without justification
- Do not begin Tailwind migration without explicit instruction

## Guardrails — changes requiring explicit confirmation
1. Signal weights, transport composition, or smoothing parameters → HIGH RISK
2. Scoring formula (sigmoid center, λ, α, β, θ) → HIGH RISK
3. Calibration logic or baseline values → HIGH RISK
4. seed_history.py → read fully before modifying
5. Any new dependency → justify first

## Decision log

Decisions are in `docs/decisions/`. Read the relevant ADR before modifying any component listed in its Triggers section.

| ADR | Title | Triggers |
|-----|-------|----------|
| 001 | Transport signal inversion | ingestion.py, passages_tcl, calibration |
| 002 | Signal weights | WEIGHTS constant, scoring weights |
| 003 | Learning + calibration | storage.py calibration, smoothing.py |
| 004 | GTM + commercial | pricing, segments, landing page copy |
| 005 | Product architecture MVP | dependencies, infra, new signal sources |
| 006 | Zone centroids source of truth | config.py ZONE_CENTROIDS, frontend/domain/constants.ts, ZoneMap.tsx |
| 007 | Request logging strategy (SQLite MVP) | main.py middleware, storage.py request_logs |
| 008 | Zone-specific incident baseline | ingestion.py fetch_incidents(), _zone_score_from_weights, _effective_baseline |
| 009 | Time-slot baselines | storage.py calibration, scoring.py _effective_baseline, main.py _apply_calibration |
| 010 | Clamp z négatifs traffic/transport dans RISK | scoring.py compute_risk, _NEUTRAL_WHEN_LOW, RISK formula |
| 011 | Remove double-phi in simulation + align report thresholds | simulation.py, reports.py pre_event_report, _recommendation_level, DPS staffing |
| 012 | Forecast short-horizon: weighted average replaces max | scoring.py _forecast_short_horizon, forecast bias, scenario weights |
| 013 | Incident decay for extended forecast horizons | scoring.py _forecast_extended_horizon, config.py INCIDENT_FORECAST_HALFLIFE_MIN |
| 014 | Harden incident_surprise detection thresholds | forecast_storage.py evaluate_forecasts, flag_incident_surprises |

## Target market (context for naming/comments)
Primary: sécurité privée / événementielle Lyon (rapport événement 390€ HT one-shot → abonnement 490€/mois)
Secondary: logistique / livraison (API 149€/mois, starts week 6+ only)

## ADR generation — standing instruction

This instruction is permanent and applies to every session.
You must detect when a decision warrants an ADR and create it without
being asked.

---

## When to create an ADR (trigger conditions)

Create an ADR automatically when ANY of these occur during a session:

### Technical triggers
- A constant, weight, threshold, or formula is changed and the reason
  is non-obvious (would need re-explaining in a future session)
- A new external dependency or data source is added or explicitly rejected
- A database schema change affects data semantics (not just adding a column)
- A signal composition or scoring logic change is made
- A bug fix changes a behavior that was previously intentional
- An architectural pattern is chosen over a documented alternative
- A performance or reliability constraint is discovered and worked around

### Product/strategy triggers
- A segment, feature, or integration is explicitly ruled out
  (NO-GO decisions are as important as GO decisions)
- A pricing, packaging, or commercial decision is made or confirmed
- A pivot condition or fallback strategy is defined
- A "do not build before X" constraint is established

### Process triggers
- A recurring mistake is identified and a prevention rule is established
- A known issue is documented as "won't fix until Y"
- An external API or service is evaluated and rejected with a reason

---

## When NOT to create an ADR

- Routine implementation (adding an endpoint that follows existing patterns)
- Bug fixes that restore intended behavior without changing the design
- Style, naming, or formatting changes
- Temporary workarounds explicitly marked as TODO
- Changes already covered by an existing ADR (update the existing one instead)

---

## Decision detection protocol

After completing any task, run this internal check silently:

1. Did I change a value that another developer (or future Claude session)
   might change back without knowing why? → ADR needed
2. Did I reject an approach that seems reasonable on the surface? → ADR needed
3. Did I establish a rule or constraint that isn't in the code itself? → ADR needed
4. Did I discover a non-obvious limitation of an external system? → ADR needed
5. Is this decision covered by an existing ADR? → Update that ADR instead

If any answer is YES → create or update the ADR before ending the session.

---

## ADR format (strict — do not deviate)

File: docs/decisions/ADR-{NNN}-{kebab-case-title}.md
Number: increment from highest existing ADR number in docs/decisions/
```markdown
# ADR-{NNN} — {Title}

**Date**: {today}
**Status**: Accepted
**Source**: Claude Code session — {brief task description}

## Decision
{One or two lines maximum — the exact decision made}

## Values
{Constants, parameters, thresholds, or rules — as code block or bullets}

## Rationale
- {Non-obvious reason 1}
- {Non-obvious reason 2}
- {Non-obvious reason 3 if needed}

## Consequences
- {What is now true}
- {What changed}
- {Side effect if any}

## DO NOT
- {Explicit prohibition 1 — derived from a real risk or past mistake}
- {Explicit prohibition 2}
- {Explicit prohibition 3 if needed}

## Triggers
Re-read when: {comma-separated list of files, functions, or topics}
```

Hard constraints on format:
- Max 30 lines total
- No prose paragraphs — bullets and short statements only
- Every line carries information — no filler
- DO NOT section is mandatory — minimum 2 items
- Triggers section is mandatory

---

## ADR lifecycle rules

### Creating a new ADR
- Check docs/decisions/ for existing ADRs that might already cover this
- Use the next available number (grep existing files for highest N)
- Create the file immediately — do not defer to end of session
- Show the created ADR content in your response

### Updating an existing ADR
- If a decision supersedes or refines an existing ADR:
  - Update Status to "Superseded by ADR-{N}" or "Updated {date}"
  - Add an "## Update {date}" section at the bottom with the change
  - Do NOT rewrite history — append only

### Conflicting decisions
- If a new decision contradicts an existing ADR:
  - Flag it explicitly: "⚠️ This conflicts with ADR-{N}"
  - Do not silently override — ask for confirmation before creating

---

## README.md maintenance

After creating or updating any ADR, update docs/decisions/README.md:

The README must always contain:
- A table with: N, Title, Status, Date, Triggers (one-line summary)
- Sorted by ADR number ascending
- Note at top: "Read relevant ADR before modifying any Triggers component"

Update CLAUDE.md decision log table to match.

---

## Response format when creating an ADR

When you create an ADR during a session, include this block
at the END of your normal response (after the task output):

---
📋 ADR created: ADR-{NNN} — {Title}
Reason: {one sentence — why this decision warrants an ADR}
File: docs/decisions/ADR-{NNN}-{kebab-case-title}.md
---

Do not interrupt the task flow to announce ADR creation.
Create the file, then append the block above at the very end.
If multiple ADRs are created in one session, list them all at the end.

---

## Verification at session end

Before ending any session where code was changed, run silently:

ls docs/decisions/ | wc -l

Compare to session start count.
If count is the same and any trigger condition was met → create the missing ADR.
If count increased → confirm README.md and CLAUDE.md are updated.

---

## Example — correct behavior

Task: "Fix the incident_surprise flag — it was never being set to 1"

After fixing:
Claude detects: "This bug fix changed a behavior. The old behavior was
unintentional (broken starttime field), the new behavior is intentional
(raw_incident lookup). A future session might revert this thinking the
new code is wrong."

Claude creates ADR-006 automatically, appends the 📋 block at end of response.

---

## Example — incorrect behavior

Task: "Add a loading spinner to the dashboard"

Claude does NOT create an ADR.
Reason: routine UI implementation, no decision with future re-interpretation risk.

## SoloCraft

### stack
- Backend: FastAPI 0.128 + SQLite + Python 3.11, déployé sur Render free tier
- Frontend: Next.js 16 App Router + React 19 + TypeScript + CSS Modules
- Dépendances clés: httpx, pydantic 2, slowapi, sentry-sdk | recharts, react-leaflet

### target
- Segment prioritaire: sécurité privée / événementielle Lyon
- Revenus: rapport one-shot 390€ HT → abonnement 490€/mois
- Segment secondaire (semaine 6+ seulement): logistique/livraison API 149€/mois
- Stade: MVP — premier client payant pas encore signé

### constraints
- SQLite jusqu'au premier client payant — pas de Postgres avant
- Pas de migration Tailwind sans instruction explicite
- Pas de nouvelle dépendance sans justification
- Validation manuelle uniquement — pas de suite de tests
- Tous les appels API frontend passent par frontend/lib/api.ts
- Pas de "use client" sans justification écrite

### high-risk-zones
- config.py WEIGHTS, LAMBDA, ALPHA, BETA, THETA
- scoring.py — sigmoid center, formule alert/spread
- ingestion.py — composition signal transport
- storage.py + main.py calibration_loop
- backend/scripts/seed_history.py

### domain-agents
When working on these domains within the `/sc` workflow, invoke the corresponding USE agent as domain expert:

| Domain | Files touched | Agent to invoke |
|--------|--------------|-----------------|
| Scoring / calibration / signaux | `config.py`, `scoring.py`, `smoothing.py`, `storage.py`, `ingestion.py` | `scoring-guardian` |
| Commercial / GTM / pricing | landing page, CLAUDE.md pricing, outreach copy | `use-gtm` |
| Déploiement / ops | `render.yaml`, `main.py` lifespan, env vars, Vercel | `use-ops` |

These agents are **advisory** — they provide validation and context, not blocking gates.
Invoke as subagents (subagent_type: scoring-guardian / use-gtm / use-ops) in Phase 1 or Phase 2 of the `/sc` workflow.

### decisions-dir
docs/decisions/

### adr-format
Voir section "ADR format" dans ce CLAUDE.md — 30 lignes max, sections : Decision, Values, Rationale, Consequences, DO NOT, Triggers.