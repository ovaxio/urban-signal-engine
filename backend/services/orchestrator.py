"""
Urban Signal Engine — Orchestrator
====================================
Cycle de rafraîchissement : fetch → score → persist → forecast → alertes → cache.
Point d'entrée unique pour main.py (background loops) et routers (endpoints).
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from config import CACHE_TTL_SECONDS, ENABLE_HISTORY
from services.ingestion import fetch_all_signals
from services.scoring import (
    score_all_zones, compute_forecast, _effective_baseline,
)
from services.storage import save_scores_history
from services.forecast_storage import (
    save_forecast_history, evaluate_forecasts, flag_incident_surprises,
    should_save_forecasts,
)
from services.alerts import check_alerts, dispatch_alerts
from services.rss_incidents import fetch_rss_incidents

log = logging.getLogger("orchestrator")


# ── Cache global ──────────────────────────────────────────────────────────────

_cache: dict = {
    "scores":            None,
    "signals":           None,
    "incident_schedule": {},
    "incident_events":   {},
    "weather_forecast":  {},
    "transport_detail":  {},
    "rss_incidents":     [],
    "fetched_at":        None,
    "lock":              asyncio.Lock(),
    "prev_scores":       {},
}


# ── Public API ────────────────────────────────────────────────────────────────

async def refresh_scores(force: bool = False) -> List[dict]:
    """
    Rafraîchit les scores si nécessaire (ou si force=True).
    Retourne la liste des scores par zone.
    """
    async with _cache["lock"]:
        now = datetime.now(timezone.utc)
        age = (now - _cache["fetched_at"]).total_seconds() if _cache["fetched_at"] else None

        if force or _cache["scores"] is None or (age and age > CACHE_TTL_SECONDS):
            log.info("Refreshing signals...")

            # Snapshot scores précédents avant refresh
            if _cache["scores"]:
                _cache["prev_scores"] = {
                    z["zone_id"]: z["urban_score"] for z in _cache["scores"]
                }

            signals, incident_schedule, incident_events, weather_fc, transport_detail, incident_labels = await fetch_all_signals()
            scores = score_all_zones(signals)

            # Attach top incident label to each score for persistence
            for z in scores:
                lbl = incident_labels.get(z["zone_id"], {})
                z["incident_label"] = lbl.get("label")
                z["incident_type"]  = lbl.get("type")

            if ENABLE_HISTORY:
                save_scores_history(scores)

            # Évaluer les forecasts passés par rapport aux scores actuels
            evaluate_forecasts(scores)
            flag_incident_surprises(incident_events)

            # Sauvegarder les forecasts pour TOUTES les zones (accuracy tracking)
            if ENABLE_HISTORY and should_save_forecasts():
                for z in scores:
                    zid = z["zone_id"]
                    trend = compute_trend(zid, z["urban_score"])
                    fc = compute_forecast(
                        z["urban_score"],
                        z["alert"],
                        z["components"]["spread"],
                        dt=now,
                        trend=trend,
                        signals=z.get("raw_signals"),
                        incident_schedule=incident_schedule.get(zid),
                        bl=_effective_baseline(zid, now),
                        zone_id=zid,
                        weather_forecast=weather_fc,
                    )
                    save_forecast_history(zid, fc, z["urban_score"])

            # Détection d'alertes sur franchissement de seuil
            new_alerts = check_alerts(_cache["prev_scores"], scores)
            if new_alerts:
                asyncio.create_task(dispatch_alerts(new_alerts))

            # RSS enrichment (cached 10min, never blocks)
            try:
                rss_incidents = await fetch_rss_incidents()
            except Exception as e:
                log.warning("RSS fetch error (non-blocking): %s", e)
                rss_incidents = []

            _cache["scores"]            = scores
            _cache["signals"]           = signals
            _cache["incident_schedule"] = incident_schedule
            _cache["incident_events"]   = incident_events
            _cache["weather_forecast"]  = weather_fc
            _cache["transport_detail"]  = transport_detail
            _cache["rss_incidents"]     = rss_incidents
            _cache["fetched_at"]        = now

    return _cache["scores"]


def get_cached_scores() -> Optional[List[dict]]:
    """Lecture du cache sans refresh."""
    return _cache["scores"]


def get_cache_data(key: str) -> Any:
    """Accès à une clé spécifique du cache (incident_events, transport_detail, etc.)."""
    return _cache.get(key)


def get_cache_state() -> dict:
    """État du cache pour le health endpoint."""
    fetched = _cache["fetched_at"]
    age = int((datetime.now(timezone.utc) - fetched).total_seconds()) if fetched else None
    return {
        "fetched_at": fetched.isoformat() if fetched else None,
        "cache_age_s": age,
    }


def compute_trend(zone_id: str, current_score: int) -> float:
    """
    Tendance = delta score entre cycle actuel et précédent.
    Normalisée par CACHE_TTL pour avoir une unité /min.
    """
    prev = _cache["prev_scores"].get(zone_id)
    if prev is None:
        return 0.0
    delta = current_score - prev
    ttl_min = CACHE_TTL_SECONDS / 60.0
    return round(delta / ttl_min, 4)
