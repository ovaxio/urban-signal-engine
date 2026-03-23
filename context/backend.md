# Backend API & Infrastructure — context/backend.md

Loaded for: endpoint, API, loop, deploy, env, SQLite, alert, storage, auth, zone list.
Invoke `use-ops` (subagent_type) for deploy/ops verification.

## API endpoints
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

## Background loops (main.py lifespan)
1. **refresh_loop** — fetch+score every 60s (CACHE_TTL_SECONDS)
2. **calibration_loop** — recalibrate baselines every 7 days at 3:00 AM
3. **backup_loop** — DB backup every 6h
4. **calendar_loop** — vacances scolaires refresh every 90 days

## Alert system (alerts.py)
Threshold crossing detection: TENDU (≥55), CRITIQUE (≥72), CALME return (<35).
30 min cooldown per zone. Persisted in alerts_log + webhook dispatch if configured.

## 12 Lyon zones (config.py ZONE_CENTROIDS)
part-dieu, presquile, vieux-lyon, perrache, gerland, guillotiere,
brotteaux, villette, montchat, fourviere, croix-rousse, confluence
Neighbor graph: scoring.py NEIGHBORS dict.

## External APIs
- **Grand Lyon Criter WFS** (open data, no quota): traffic state (pvotrafic) + incidents (pvoevenement)
- **TomTom Incident Details v5**: incidents with delay/magnitude (cached 30min, ≤2500 req/month)
- **Open-Meteo**: current weather + 48h hourly forecast (free, no key)
- **Grand Lyon data** (HTTP Basic Auth, GRANDLYON_LOGIN/PASSWORD): TCL passages, parcrelais, Velo'v
- **education.gouv.fr**: vacances scolaires (refreshed every 90 days)
- Static 2026 Lyon event calendar (OpenAgenda/Ticketmaster ruled out)

## Environment variables (render.yaml)
TOMTOM_API_KEY, GRANDLYON_LOGIN, GRANDLYON_PASSWORD, ENABLE_HISTORY,
ALERT_WEBHOOK_URL, ALLOWED_ORIGINS, ADMIN_SECRET, SENTRY_DSN, SENTRY_ENV

## SQLite persistence
DB at `backend/data/urban_signal.db`. Recreated + seed loaded at each Render deploy (ephemeral).
Tables: signals_history, alerts_log, forecast_history, calendar_vacances, api_keys.
