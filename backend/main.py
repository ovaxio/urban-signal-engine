import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv

# charger .env AVANT les autres imports
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

# ── Sentry (avant tout autre import applicatif) ──────────────────────────────
import sentry_sdk
_sentry_dsn = os.getenv("SENTRY_DSN")
if _sentry_dsn:
    sentry_sdk.init(
        dsn=_sentry_dsn,
        traces_sample_rate=0.3,
        environment=os.getenv("SENTRY_ENV", "production"),
    )

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from routers.zones import router as zones_router
from services.orchestrator import refresh_scores, get_cache_state
from routers.contact import router as contact_router
from routers.admin import router as admin_router
from routers.reports import router as reports_router
from config import CACHE_TTL_SECONDS
from services.storage import (
    init_db, get_calibration_baselines, get_calibration_baselines_per_zone,
    get_calibration_baselines_by_slot, get_calibration_baselines_per_zone_by_slot,
    save_calibration_log, CALIBRATION_CUTOFF_TS, save_request_log, purge_old_request_logs,
    load_calibration_snapshot,
)
from services.auth import init_auth_db
import services.scoring as scoring

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log = logging.getLogger("main")

_calibration_meta: dict = {
    "last_calibrated_at": None,
    "row_count": None,
    "zones_calibrated": 0,
}

# ── Rate limiter ──────────────────────────────────────────────────────────────
_rate_limit = os.getenv("RATE_LIMIT", "30/minute")
limiter = Limiter(key_func=get_remote_address, default_limits=[_rate_limit])


async def _refresh_loop():
    while True:
        try:
            await refresh_scores(force=True)
        except Exception as e:
            log.error(f"Refresh error: {e}")
        await asyncio.sleep(CACHE_TTL_SECONDS)


async def _calibration_loop():
    """
    Recalibre les baselines toutes les 7 jours à 3h00 heure Paris.
    Tourne en tâche de fond, silencieux si pas assez de données.
    """
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo
    PARIS_TZ = ZoneInfo("Europe/Paris")
    INTERVAL_DAYS = 7

    while True:
        now   = datetime.now(PARIS_TZ)
        # Prochain 3h00
        next_run = now.replace(hour=3, minute=0, second=0, microsecond=0)
        if next_run <= now:
            next_run = (now + timedelta(days=1)).replace(hour=3, minute=0, second=0, microsecond=0)
        wait_s = (next_run - now).total_seconds()
        log.info(f"Prochaine recalibration dans {wait_s/3600:.1f}h (à 3h00 Paris).")
        await asyncio.sleep(wait_s)

        log.info("Recalibration hebdomadaire — démarrage.")
        _apply_calibration(min_count=500)
        purge_old_request_logs(days=7)

        # Attendre 7 jours avant le prochain cycle
        await asyncio.sleep(INTERVAL_DAYS * 24 * 3600)


# event exclu de la calibration auto : non-stationnaire (calendrier statique,
# peut être tout-à-zéro pendant des jours). Baseline fixe.
_EVENT_BASELINE_DEFAULT = {"mu": 0.2, "sigma": 0.3}


def _apply_calibration(min_count: int = 96) -> None:
    """
    Recalibre scoring.BASELINE depuis les raw_signals en base.
    event est exclu (non-stationnaire). traffic, weather, transport,
    incident sont calibrés automatiquement depuis l'historique Criter.
    Filtre : source='live', ts >= CALIBRATION_CUTOFF_TS.
    Appelé au démarrage et toutes les 7 jours à 3h00.

    Fallback chain (ADR-015):
      1. Live data calibration (>= min_count rows) — PRIMARY
      2. calibration_snapshot.json (if exists and valid) — FALLBACK
      3. Hardcoded BASELINE in scoring.py — LAST RESORT
    """
    from datetime import datetime, timezone as _tz

    cal_entries: list = []
    global_bl = {"event": _EVENT_BASELINE_DEFAULT.copy()}

    baselines, n_rows = get_calibration_baselines(min_count=min_count)
    if not baselines:
        log.info("Recalibration : données insuffisantes (%d relevés qualifiés), tentative snapshot fallback.", n_rows)

        # ── Snapshot fallback (ADR-015) ──────────────────────────────────
        snapshot = load_calibration_snapshot()
        if snapshot:
            log.info("Applying calibration from snapshot (generated_at=%s).", snapshot["generated_at"])
            for signal, values in snapshot["baseline"].items():
                global_bl[signal] = values
            zone_baselines = snapshot.get("zone_baselines", {})
            scoring.set_baselines(global_bl, zone_baselines)
            log.info("Snapshot applied: %d global signals, %d zones.", len(snapshot["baseline"]), len(zone_baselines))

            slot_bl = snapshot.get("baseline_by_slot", {})
            zone_slot_bl = snapshot.get("zone_baselines_by_slot", {})
            scoring.set_slot_baselines(slot_bl, zone_slot_bl)
            log.info("Snapshot slots: %d slots globaux, %d zones avec slots.",
                     len(slot_bl), len(zone_slot_bl))

            _calibration_meta["last_calibrated_at"] = snapshot["generated_at"]
            _calibration_meta["row_count"] = n_rows
            _calibration_meta["zones_calibrated"] = len(zone_baselines)
            _calibration_meta["source"] = "snapshot"
            return
        else:
            log.warning("No snapshot available — falling back to hardcoded BASELINE.")
            _calibration_meta["source"] = "hardcoded"
            return
    else:
        for signal, values in baselines.items():
            old = scoring.BASELINE.get(signal, {})
            global_bl[signal] = values
            delta_pct = (
                abs(values["mu"] - old.get("mu", 0)) / max(old.get("mu", 1), 0.01) * 100
                if old.get("mu") is not None else 0
            )
            if delta_pct > 15:
                log.warning(
                    "Calibration shift >15%% [%s] : mu %.4f → %.4f (%.1f%%)",
                    signal, old.get("mu", 0), values["mu"], delta_pct,
                )
            log.info(
                f"Recalibration globale [{signal}] : "
                f"mu {old.get('mu')} → {values['mu']} | "
                f"sigma {old.get('sigma')} → {values['sigma']}"
            )
            cal_entries.append({
                "zone_id": None, "signal": signal,
                "old_mu": old.get("mu"), "new_mu": values["mu"],
                "old_sigma": old.get("sigma"), "new_sigma": values["sigma"],
                "row_count": n_rows, "cutoff_ts": CALIBRATION_CUTOFF_TS,
                "skipped": 0,
            })
        log.info("Recalibration globale terminée (%d relevés).", n_rows)

    zone_baselines = get_calibration_baselines_per_zone(min_count=min_count // 2)

    scoring.set_baselines(global_bl, zone_baselines)
    log.info("Recalibration par zone : %d zones calibrées.", len(zone_baselines))

    # Baselines segmentées par créneau horaire (nuit/matin/aprem/soir)
    slot_bl = get_calibration_baselines_by_slot(min_count=min_count // 4)
    zone_slot_bl = get_calibration_baselines_per_zone_by_slot(min_count=min_count // 8)
    scoring.set_slot_baselines(slot_bl, zone_slot_bl)
    log.info("Recalibration par slot : %d slots globaux, %d zones avec slots.",
             len(slot_bl), len(zone_slot_bl))

    # Persist calibration log
    save_calibration_log(cal_entries)

    # Update in-memory metadata for /health
    _calibration_meta["last_calibrated_at"] = datetime.now(_tz.utc).isoformat(timespec="seconds")
    _calibration_meta["row_count"] = n_rows
    _calibration_meta["zones_calibrated"] = len(zone_baselines)
    _calibration_meta["source"] = "live"


async def _backup_loop():
    """Sauvegarde automatique de la DB toutes les 6h."""
    from scripts.backup_db import backup_db
    INTERVAL = 6 * 3600
    backup_db()  # backup immédiat au démarrage
    while True:
        await asyncio.sleep(INTERVAL)
        try:
            backup_db()
        except Exception as e:
            log.error(f"Backup error: {e}")


async def _calendar_loop():
    """Refresh vacances scolaires tous les 90 jours."""
    from services.calendar import refresh_vacances
    INTERVAL = 90 * 24 * 3600  # 90 jours
    try:
        count = await refresh_vacances()
        log.info(f"Calendrier scolaire initialisé : {count} périodes")
    except Exception as e:
        log.warning(f"Calendrier scolaire init fallback : {e}")
    while True:
        await asyncio.sleep(INTERVAL)
        try:
            count = await refresh_vacances()
            log.info(f"Calendrier scolaire refreshed : {count} périodes")
        except Exception as e:
            log.error(f"Calendar refresh error: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("Urban Signal Engine — starting")
    init_db()
    init_auth_db()
    _apply_calibration()
    # Charger le calendrier scolaire depuis la DB (fallback hardcodé si vide)
    scoring.load_vacances_from_db()
    task_refresh  = asyncio.create_task(_refresh_loop())
    task_calib    = asyncio.create_task(_calibration_loop())
    task_backup   = asyncio.create_task(_backup_loop())
    task_calendar = asyncio.create_task(_calendar_loop())
    yield
    task_refresh.cancel()
    task_calib.cancel()
    task_backup.cancel()
    task_calendar.cancel()


app = FastAPI(
    title="Urban Signal Engine",
    description="Moteur temps réel de détection de tensions urbaines à Lyon.",
    version="1.0.0-mvp",
    lifespan=lifespan,
)

# ── Rate limiter ──────────────────────────────────────────────────────────────
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── CORS — configurable via ALLOWED_ORIGINS env var ───────────────────────────
_default_origins = ["http://localhost:3000", "http://127.0.0.1:3000"]
_env_origins = os.getenv("ALLOWED_ORIGINS", "")
_origins = [o.strip() for o in _env_origins.split(",") if o.strip()] if _env_origins else _default_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type", "Authorization", "X-API-Key"],
    allow_credentials=True,
)


# ── Security headers + request logging middleware ─────────────────────────────
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    t0 = time.perf_counter()
    response: Response = await call_next(request)
    duration_ms = (time.perf_counter() - t0) * 1000

    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if os.getenv("SENTRY_ENV") == "production":
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"

    if request.url.path != "/health":
        client_ip = request.client.host if request.client else None
        log.info(
            "%s %s %d %.0fms %s",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            client_ip or "-",
        )
        try:
            save_request_log(
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_ms=duration_ms,
                client_ip=client_ip,
            )
        except Exception as e:
            log.warning("request_log write failed: %s", e)

    return response


app.include_router(zones_router)
app.include_router(contact_router)
app.include_router(admin_router)
app.include_router(reports_router)


@app.get("/health", tags=["system"])
async def health():
    from datetime import datetime, timezone as _tz
    state = get_cache_state()

    # Compute stale_warning: true if last calibration > 25h ago
    stale = False
    last_cal = _calibration_meta.get("last_calibrated_at")
    if last_cal:
        try:
            age_s = (datetime.now(_tz.utc) - datetime.fromisoformat(last_cal)).total_seconds()
            stale = age_s > 25 * 3600
        except (ValueError, TypeError):
            stale = True

    # Per-signal summary from current baselines
    signals_summary = {}
    for sig, bl in scoring.BASELINE.items():
        signals_summary[sig] = {
            "global_mu": bl["mu"],
            "global_sigma": bl["sigma"],
        }

    return {
        "status":    "ok",
        "zones":     12,
        "cache_age": state["cache_age_s"],
        "ttl":       CACHE_TTL_SECONDS,
        "baseline":  scoring.BASELINE,
        "calibration": {
            "last_calibrated_at": _calibration_meta.get("last_calibrated_at"),
            "source": _calibration_meta.get("source", "unknown"),
            "cutoff_ts": CALIBRATION_CUTOFF_TS,
            "row_count": _calibration_meta.get("row_count"),
            "zones_with_custom_baseline": _calibration_meta.get("zones_calibrated", 0),
            "signals_summary": signals_summary,
            "stale_warning": stale,
        },
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)