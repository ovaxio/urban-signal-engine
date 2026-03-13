import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv

# charger .env AVANT les autres imports
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers.zones import router as zones_router, _get_scores
from config import CACHE_TTL_SECONDS
from services.storage import init_db, get_calibration_baselines, get_calibration_baselines_per_zone
import services.scoring as scoring                                 # ← AJOUT

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log = logging.getLogger("main")


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


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("Urban Signal Engine — starting")
    init_db()
    _apply_calibration()          # recalibration immédiate au démarrage
    task_refresh = asyncio.create_task(_refresh_loop())
    task_calib   = asyncio.create_task(_calibration_loop())  # ← NOUVEAU
    yield
    task_refresh.cancel()
    task_calib.cancel()


app = FastAPI(
    title="Urban Signal Engine",
    description="Moteur temps réel de détection de tensions urbaines à Lyon.",
    version="1.0.0-mvp",
    lifespan=lifespan,
)

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET","POST"], allow_headers=["*"])
app.include_router(zones_router)


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
        "baseline": scoring.BASELINE,   # ← visible dans /health pour debug
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)