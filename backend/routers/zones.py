import logging
import re
from datetime import datetime, timezone
from datetime import date as date_type
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, BackgroundTasks

from services.orchestrator import refresh_scores, get_cache_data, get_cache_state, compute_trend
from services.scoring import compute_forecast, NEIGHBORS, ZONE_NAMES, BASELINE, _effective_baseline, score_all_zones
from services.storage import get_zone_history, get_recent_alerts, get_typical_score
from services.calendar_utils import day_type as get_day_type
from services.forecast_storage import save_forecast_history, get_forecast_accuracy
from services.events import compute_event_signals, STATIC_EVENTS
from services.simulation import simulate_event_profile
from config import ENABLE_HISTORY, WEIGHTS

log = logging.getLogger("router.zones")
router = APIRouter(prefix="/zones", tags=["zones"])


@router.get("/scores")
async def get_all_scores(
    min_score: Optional[int] = Query(None, ge=0, le=100),
    level:     Optional[str] = Query(None),
    sort:      str           = Query("score_desc"),
):
    scores = await refresh_scores()
    result = scores
    if min_score is not None:
        result = [z for z in result if z["urban_score"] >= min_score]
    if level:
        result = [z for z in result if z["level"] == level.upper()]
    if sort == "score_desc":   result = sorted(result, key=lambda z: z["urban_score"], reverse=True)
    elif sort == "score_asc":  result = sorted(result, key=lambda z: z["urban_score"])
    elif sort == "zone_asc":   result = sorted(result, key=lambda z: z["zone_name"])
    clean = [{k: v for k, v in z.items() if k != "alert"} for z in result]
    state = get_cache_state()
    return {"count": len(clean), "refreshed_at": state["fetched_at"], "cache_age_s": state["cache_age_s"], "zones": clean}


@router.get("/{zone_id}/detail")
async def get_zone_detail(zone_id: str, force_refresh: bool = Query(False)):
    scores   = await refresh_scores(force=force_refresh)
    zone_map = {z["zone_id"]: z for z in scores}
    if zone_id not in zone_map:
        raise HTTPException(status_code=404, detail=f"Zone '{zone_id}' introuvable.")
    z        = zone_map[zone_id]
    neighbors = [
        {"zone_id": n, "zone_name": zone_map[n]["zone_name"], "urban_score": zone_map[n]["urban_score"],
         "level": zone_map[n]["level"], "top_causes": zone_map[n]["top_causes"]}
        for n in NEIGHBORS.get(zone_id, []) if n in zone_map
    ]
    incident_events = get_cache_data("incident_events") or {}
    transport_detail = get_cache_data("transport_detail") or {}
    rss_incidents = get_cache_data("rss_incidents") or []
    rss_context = [
        {
            "headline":      r.headline,
            "incident_type": r.incident_type,
            "severity_hint": r.severity_hint,
            "published_at":  r.published_at,
            "source":        r.source,
            "url":           r.url,
        }
        for r in rss_incidents if r.zone_id == zone_id
    ]
    # ── Contexte décisionnel (delta vs typical + recommandation) ────────────
    from zoneinfo import ZoneInfo
    now_paris = datetime.now(ZoneInfo("Europe/Paris"))
    dt = get_day_type(now_paris)
    hour = now_paris.hour
    typical = get_typical_score(zone_id, dt, hour)
    delta = round(z["urban_score"] - typical, 1) if typical is not None else None

    RECOMMENDATIONS = {
        "CALME":    {"level": 0, "action": "Effectif standard. Aucune action requise."},
        "MODÉRÉ":   {"level": 1, "action": "Attention recommandée. Surveiller l'évolution des signaux."},
        "TENDU":    {"level": 2, "action": "Renforcement du dispositif recommandé. Surveillance active des zones voisines."},
        "CRITIQUE": {"level": 3, "action": "Plan d'urgence. Déploiement immédiat de renforts sur la zone."},
    }
    recommendation = RECOMMENDATIONS.get(z["level"], RECOMMENDATIONS["CALME"])

    # Enrichir le delta dans la recommandation si disponible
    delta_text = ""
    if delta is not None:
        sign = "+" if delta > 0 else ""
        day_labels = {"semaine": "un jour de semaine", "mercredi": "un mercredi", "vacances": "les vacances", "weekend": "un weekend"}
        delta_text = f"{sign}{delta:.0f} pts vs moyenne {day_labels.get(dt, dt)} à {hour}h"

    return {
        **{k: v for k, v in z.items() if k != "alert"},
        "neighbors":        neighbors,
        "incident_events":  incident_events.get(zone_id, []),
        "transport_detail": transport_detail.get(zone_id),
        "weights":          {k: round(v * 100) for k, v in WEIGHTS.items()},
        "rss_context":      rss_context,
        "typical_score":    typical,
        "delta_vs_typical": delta,
        "delta_label":      delta_text if delta_text else None,
        "recommendation":   recommendation,
    }


@router.get("/{zone_id}/forecast")
async def get_zone_forecast(zone_id: str, force_refresh: bool = Query(False)):
    scores   = await refresh_scores(force=force_refresh)
    zone_map = {z["zone_id"]: z for z in scores}
    if zone_id not in zone_map:
        raise HTTPException(status_code=404, detail=f"Zone '{zone_id}' introuvable.")
    z     = zone_map[zone_id]
    trend = compute_trend(zone_id, z["urban_score"])

    incident_schedule = get_cache_data("incident_schedule") or {}
    weather_forecast = get_cache_data("weather_forecast") or {}

    forecast = compute_forecast(
        z["urban_score"],
        z["alert"],
        z["components"]["spread"],
        dt=datetime.now(timezone.utc),
        trend=trend,
        signals=z.get("raw_signals"),
        incident_schedule=incident_schedule.get(zone_id),
        bl=_effective_baseline(zone_id, datetime.now(timezone.utc)),
        zone_id=zone_id,
        weather_forecast=weather_forecast,
    )

    if ENABLE_HISTORY:
        save_forecast_history(zone_id, forecast, z["urban_score"])

    return {
        "zone_id":       zone_id,
        "zone_name":     z["zone_name"],
        "current_score": z["urban_score"],
        "current_level": z["level"],
        "trend_per_min": trend,
        "forecast":      forecast,
        "disclaimer":    "Prévision probabiliste. Confiance décroissante au-delà de 2h.",
    }


@router.get("/{zone_id}/history")
async def get_zone_history_endpoint(
    zone_id: str,
    limit: int = Query(48, ge=1, le=500),
):
    scores   = await refresh_scores()
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
    background_tasks.add_task(refresh_scores, force=True)
    return {"status": "refresh_scheduled"}


@router.get("/forecast/accuracy")
async def forecast_accuracy(
    zone_id: Optional[str] = Query(None),
    horizon: Optional[str] = Query(None),
    since: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    """
    Stats de précision des forecasts : MAE global et par horizon,
    taux d'incidents surprises, dernières évaluations.
    since: filtre evaluated_at >= date (ISO format).
    """
    return get_forecast_accuracy(zone_id=zone_id, horizon=horizon, since=since, limit=limit)


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
async def simulate_date(
    date: str = Query(..., description="YYYY-MM-DD"),
    event_name: Optional[str] = Query(None, description="Nom événement (recherche partielle)"),
):
    """Simule le profil horaire 24h (6h-23h) pour toutes les zones à une date donnée."""
    d = _parse_sim_date(date)
    return await simulate_event_profile(d, event_name)


@router.get("/{zone_id}/simulate-detail")
async def simulate_zone_detail(zone_id: str, date: str = Query(..., description="YYYY-MM-DD")):
    """
    Retourne le détail simulé d'une zone pour une date donnée.
    Même structure que /zones/{id}/detail avec champs sim_date et sim_events en plus.
    Utilise _build_sim_scores (score unique 11h) pour compatibilité existante.
    """
    d = _parse_sim_date(date)
    scores, active_events = _build_sim_scores(d, date)
    zone_map = {z["zone_id"]: z for z in scores}

    if zone_id not in zone_map:
        raise HTTPException(status_code=404, detail=f"Zone '{zone_id}' introuvable.")

    z = zone_map[zone_id]
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
        "neighbors":    neighbors,
        "sim_date":     date,
        "sim_events":   active_events,
    }
