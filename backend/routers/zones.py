import asyncio
import logging
from datetime import datetime, timezone
from typing import List, Optional

import re
from datetime import date as date_type

from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from services.ingestion import fetch_all_signals
from services.scoring import score_all_zones, compute_forecast, NEIGHBORS, ZONE_NAMES, BASELINE, _effective_baseline
from services.storage import save_scores_history, get_zone_history, get_recent_alerts
from services.alerts import check_alerts, dispatch_alerts
from services.events import compute_event_signals, STATIC_EVENTS
from config import CACHE_TTL_SECONDS, ENABLE_HISTORY

log = logging.getLogger("router.zones")
router = APIRouter(prefix="/zones", tags=["zones"])

_cache: dict = {
    "scores":            None,
    "signals":           None,
    "incident_schedule": {},   # Dict[zone_id, Dict[int, float]] — incidents planifiés
    "incident_events":   {},   # Dict[zone_id, List[dict]]        — détails événements actifs
    "fetched_at":        None,
    "lock":              asyncio.Lock(),
    "prev_scores":       {},   # snapshot des scores du cycle précédent pour calcul tendance
}


async def _get_scores(force_refresh: bool = False) -> List[dict]:
    async with _cache["lock"]:
        now = datetime.now(timezone.utc)
        age = (now - _cache["fetched_at"]).total_seconds() if _cache["fetched_at"] else None
        if force_refresh or _cache["scores"] is None or (age and age > CACHE_TTL_SECONDS):
            log.info("Refreshing signals...")

            # Snapshot scores précédents avant refresh
            if _cache["scores"]:
                _cache["prev_scores"] = {
                    z["zone_id"]: z["urban_score"] for z in _cache["scores"]
                }

            signals, incident_schedule, incident_events = await fetch_all_signals()
            scores  = score_all_zones(signals)

            if ENABLE_HISTORY:
                save_scores_history(scores)

            # Détection d'alertes sur franchissement de seuil
            new_alerts = check_alerts(_cache["prev_scores"], scores)
            if new_alerts:
                asyncio.create_task(dispatch_alerts(new_alerts))

            _cache["scores"]            = scores
            _cache["signals"]           = signals
            _cache["incident_schedule"] = incident_schedule
            _cache["incident_events"]   = incident_events
            _cache["fetched_at"]        = now

    return _cache["scores"]


def _compute_trend(zone_id: str, current_score: int) -> float:
    """
    Tendance = delta score entre cycle actuel et précédent.
    Normalisée par CACHE_TTL pour avoir une unité /min.
    Retourne 0.0 si pas d'historique.
    """
    prev = _cache["prev_scores"].get(zone_id)
    if prev is None:
        return 0.0
    delta = current_score - prev
    ttl_min = CACHE_TTL_SECONDS / 60.0
    return round(delta / ttl_min, 4)   # points/min


@router.get("/scores")
async def get_all_scores(
    min_score: Optional[int] = Query(None, ge=0, le=100),
    level:     Optional[str] = Query(None),
    sort:      str           = Query("score_desc"),
):
    scores = await _get_scores()
    result = scores
    if min_score is not None:
        result = [z for z in result if z["urban_score"] >= min_score]
    if level:
        result = [z for z in result if z["level"] == level.upper()]
    if sort == "score_desc":   result = sorted(result, key=lambda z: z["urban_score"], reverse=True)
    elif sort == "score_asc":  result = sorted(result, key=lambda z: z["urban_score"])
    elif sort == "zone_asc":   result = sorted(result, key=lambda z: z["zone_name"])
    clean = [{k: v for k, v in z.items() if k != "alert"} for z in result]
    age = int((datetime.now(timezone.utc) - _cache["fetched_at"]).total_seconds()) if _cache["fetched_at"] else None
    return {"count": len(clean), "refreshed_at": _cache["fetched_at"].isoformat() if _cache["fetched_at"] else None, "cache_age_s": age, "zones": clean}


@router.get("/{zone_id}/detail")
async def get_zone_detail(zone_id: str, force_refresh: bool = Query(False)):
    scores   = await _get_scores(force_refresh=force_refresh)
    zone_map = {z["zone_id"]: z for z in scores}
    if zone_id not in zone_map:
        raise HTTPException(status_code=404, detail=f"Zone '{zone_id}' introuvable.")
    z        = zone_map[zone_id]
    conv_val = z["components"]["conv"]
    conv_txt = f"{conv_val:.2f} (signaux multiples)" if conv_val > 0.3 else f"{conv_val:.2f} (faible)"
    explanation = f"Zone {z['level'].lower()} (score {z['urban_score']}/100). Signaux forts : {', '.join(z['top_causes'])}. Convergence : {conv_txt}. Diffusion voisinage : {z['components']['spread']:.2f}."
    neighbors = [
        {"zone_id": n, "zone_name": zone_map[n]["zone_name"], "urban_score": zone_map[n]["urban_score"],
         "level": zone_map[n]["level"], "top_causes": zone_map[n]["top_causes"]}
        for n in NEIGHBORS.get(zone_id, []) if n in zone_map
    ]
    return {
        **{k: v for k, v in z.items() if k != "alert"},
        "explanation":     explanation,
        "neighbors":       neighbors,
        "incident_events": _cache["incident_events"].get(zone_id, []),
    }


@router.get("/{zone_id}/forecast")
async def get_zone_forecast(zone_id: str, force_refresh: bool = Query(False)):
    scores   = await _get_scores(force_refresh=force_refresh)
    zone_map = {z["zone_id"]: z for z in scores}
    if zone_id not in zone_map:
        raise HTTPException(status_code=404, detail=f"Zone '{zone_id}' introuvable.")
    z     = zone_map[zone_id]
    trend = _compute_trend(zone_id, z["urban_score"])  # ← points/min

    forecast = compute_forecast(
        z["urban_score"],
        z["alert"],
        z["components"]["spread"],
        dt=datetime.now(timezone.utc),
        trend=trend,
        signals=z.get("raw_signals"),
        incident_schedule=_cache["incident_schedule"].get(zone_id),
        bl=_effective_baseline(zone_id),
    )
    return {
        "zone_id":       zone_id,
        "zone_name":     z["zone_name"],
        "current_score": z["urban_score"],
        "current_level": z["level"],
        "trend_per_min": trend,   # visible pour debug
        "forecast":      forecast,
        "disclaimer":    "Prévision probabiliste. Non déterministe.",
    }


@router.get("/{zone_id}/history")
async def get_zone_history_endpoint(
    zone_id: str,
    limit: int = Query(48, ge=1, le=500),
):
    scores   = await _get_scores()
    zone_ids = {z["zone_id"] for z in scores}
    if zone_id not in zone_ids:
        raise HTTPException(status_code=404, detail=f"Zone '{zone_id}' introuvable.")
    rows = get_zone_history(zone_id, limit=limit)
    return {
        "zone_id": zone_id,
        "count":   len(rows),
        "history": [
            {
                "ts":          r["ts"],
                "urban_score": r["urban_score"],
                "traffic":     r["traffic"],
                "weather":     r["weather"],
                "transport":   r["transport"],
                "event":       r["event"],
            }
            for r in rows
        ],
    }


@router.get("/alerts")
async def get_alerts(limit: int = Query(50, ge=1, le=200)):
    """Retourne les dernières alertes de franchissement de seuil."""
    alerts = get_recent_alerts(limit=limit)
    return {"count": len(alerts), "alerts": alerts}


@router.post("/refresh")
async def force_refresh(background_tasks: BackgroundTasks):
    background_tasks.add_task(_get_scores, force_refresh=True)
    return {"status": "refresh_scheduled"}


def _parse_sim_date(date: str) -> date_type:
    """Valide et parse une date YYYY-MM-DD. Lève HTTPException si invalide."""
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", date):
        raise HTTPException(status_code=400, detail="Format invalide. Utilisez YYYY-MM-DD.")
    try:
        return date_type.fromisoformat(date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Date invalide.")


def _build_sim_scores(d: date_type, date: str) -> tuple[list[dict], list[str]]:
    """
    Calcule les scores simulés pour toutes les zones à une date donnée.
    Retourne (scores_list, active_events_names).
    """
    event_signals = compute_event_signals(d)
    signals: dict = {}
    for zone_id, ev in event_signals.items():
        signals[zone_id] = {
            "traffic":   min(BASELINE["traffic"]["mu"]   * (1 + ev * 0.8), 3.0),
            "weather":   BASELINE["weather"]["mu"],
            "event":     ev,
            "transport": min(BASELINE["transport"]["mu"] * (1 + ev * 0.5), 1.0),
            "incident":  BASELINE["incident"]["mu"]      * (1 + ev * 0.2),
        }
    dt = datetime.fromisoformat(f"{date}T11:00:00+00:00")
    scores = score_all_zones(signals, dt=dt)
    active_events = [ev["name"] for ev in STATIC_EVENTS if d in ev["dates"]]
    return scores, active_events


@router.get("/simulate")
async def simulate_date(date: str = Query(..., description="YYYY-MM-DD")):
    """Simule les scores de toutes les zones pour une date donnée."""
    d = _parse_sim_date(date)
    scores, active_events = _build_sim_scores(d, date)
    clean = sorted(
        [{k: v for k, v in z.items() if k != "alert"} for z in scores],
        key=lambda z: z["urban_score"],
        reverse=True,
    )
    return {
        "mode":          "simulation",
        "date":          date,
        "active_events": active_events,
        "count":         len(clean),
        "zones":         clean,
    }


@router.get("/{zone_id}/simulate-detail")
async def simulate_zone_detail(zone_id: str, date: str = Query(..., description="YYYY-MM-DD")):
    """
    Retourne le détail simulé d'une zone pour une date donnée.
    Même structure que /zones/{id}/detail avec champs sim_date et sim_events en plus.
    Pas de forecast (sans sens pour une simulation).
    """
    d = _parse_sim_date(date)
    scores, active_events = _build_sim_scores(d, date)
    zone_map = {z["zone_id"]: z for z in scores}

    if zone_id not in zone_map:
        raise HTTPException(status_code=404, detail=f"Zone '{zone_id}' introuvable.")

    z = zone_map[zone_id]
    conv_val = z["components"]["conv"]
    conv_txt = f"{conv_val:.2f} (signaux multiples)" if conv_val > 0.3 else f"{conv_val:.2f} (faible)"
    explanation = (
        f"Zone {z['level'].lower()} (score {z['urban_score']}/100) — simulation {date}. "
        f"Signaux forts : {', '.join(z['top_causes'])}. "
        f"Convergence : {conv_txt}. "
        f"Diffusion voisinage : {z['components']['spread']:.2f}."
    )
    neighbors = [
        {
            "zone_id":     n,
            "zone_name":   zone_map[n]["zone_name"],
            "urban_score": zone_map[n]["urban_score"],
            "level":       zone_map[n]["level"],
            "top_causes":  zone_map[n]["top_causes"],
        }
        for n in NEIGHBORS.get(zone_id, []) if n in zone_map
    ]
    return {
        **{k: v for k, v in z.items() if k != "alert"},
        "explanation":  explanation,
        "neighbors":    neighbors,
        "sim_date":     date,
        "sim_events":   active_events,
    }