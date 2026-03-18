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
- **RISK** = φ(t) × Σ(wₛ × zₛ) — weighted risk modulated by temporal profile
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

## Target market (context for naming/comments)
Primary: événementiel / logistique urbaine Lyon (POC payant par événement)
Secondary: sécurité privée (pilote 30j gratuit → 299-499€/mois)
