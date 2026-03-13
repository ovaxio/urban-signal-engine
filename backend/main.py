import asyncio
import logging
import os
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
from routers.zones import router as zones_router, _get_scores
from routers.contact import router as contact_router
from config import CACHE_TTL_SECONDS
from services.storage import init_db, get_calibration_baselines, get_calibration_baselines_per_zone
import services.scoring as scoring

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log = logging.getLogger("main")

# ── Rate limiter ──────────────────────────────────────────────────────────────
_rate_limit = os.getenv("RATE_LIMIT", "30/minute")
limiter = Limiter(key_func=get_remote_address, default_limits=[_rate_limit])


async def _refresh_loop():
    while True:
        try:
            await _get_scores(force_refresh=True)
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

        # Attendre 7 jours avant le prochain cycle
        await asyncio.sleep(INTERVAL_DAYS * 24 * 3600)


# Valeurs hardcodées à ne jamais écraser depuis SQLite :
# - event   : non-stationnaire (calendrier statique)
# - traffic : seed génère ~1.0 (flux libre) ≠ TomTom réel (~1.95)
#             → la calibration corromprait mu et ferait exploser les z-scores
_EVENT_BASELINE_DEFAULT   = {"mu": 0.2,  "sigma": 0.3}
_TRAFFIC_BASELINE_DEFAULT = {"mu": 1.95, "sigma": 0.4}


def _apply_calibration(min_count: int = 96) -> None:
    """
    Recalibre scoring.BASELINE depuis les raw_signals en base.
    event et traffic sont exclus (voir constantes ci-dessus).
    Appelé au démarrage et toutes les 7 jours à 3h00.
    """
    # Toujours réinitialiser les signaux protégés à leurs valeurs de référence
    scoring.BASELINE["event"]   = _EVENT_BASELINE_DEFAULT.copy()
    scoring.BASELINE["traffic"] = _TRAFFIC_BASELINE_DEFAULT.copy()

    baselines = get_calibration_baselines(min_count=min_count)
    if not baselines:
        log.info("Recalibration : données insuffisantes, baselines conservées.")
    else:
        for signal, values in baselines.items():
            if signal in scoring.BASELINE:
                old = scoring.BASELINE[signal]
                scoring.BASELINE[signal] = values
                log.info(
                    f"Recalibration globale [{signal}] : "
                    f"mu {old['mu']} → {values['mu']} | "
                    f"sigma {old['sigma']} → {values['sigma']}"
                )
        log.info("Recalibration globale terminée.")

    # Recalibration par zone (remplace ZONE_BASELINES)
    zone_baselines = get_calibration_baselines_per_zone(min_count=min_count // 2)
    scoring.ZONE_BASELINES.clear()
    scoring.ZONE_BASELINES.update(zone_baselines)
    log.info("Recalibration par zone : %d zones calibrées.", len(zone_baselines))


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


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("Urban Signal Engine — starting")
    init_db()
    _apply_calibration()
    task_refresh = asyncio.create_task(_refresh_loop())
    task_calib   = asyncio.create_task(_calibration_loop())
    task_backup  = asyncio.create_task(_backup_loop())
    yield
    task_refresh.cancel()
    task_calib.cancel()
    task_backup.cancel()


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
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
    allow_credentials=True,
)


# ── Security headers middleware ───────────────────────────────────────────────
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response: Response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if os.getenv("SENTRY_ENV") == "production":
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
    return response


app.include_router(zones_router)
app.include_router(contact_router)


@app.get("/health", tags=["system"])
async def health():
    from routers.zones import _cache
    from datetime import datetime, timezone
    age = int((datetime.now(timezone.utc) - _cache["fetched_at"]).total_seconds()) if _cache["fetched_at"] else None
    return {
        "status":   "ok",
        "zones":    12,
        "cache_age": age,
        "ttl":      CACHE_TTL_SECONDS,
        "baseline": scoring.BASELINE,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)