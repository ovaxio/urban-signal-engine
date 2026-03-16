"""
Rapport d'impact post-événement.

Permet d'analyser l'impact réel d'un événement sur les zones de Lyon
en comparant les scores pendant l'événement à une période de référence.

Endpoints :
    GET /reports/impact?start=...&end=...&baseline_start=...&baseline_end=...
    GET /reports/impact/event/{event_name}
"""

import logging
import re
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query

from services.events import STATIC_EVENTS, _days
from services.scoring import ZONE_NAMES, SIGNAL_LABELS, score_level
from services.storage import get_history_range, get_alerts_range

log = logging.getLogger("router.reports")
router = APIRouter(prefix="/reports", tags=["reports"])


def _compute_zone_impact(rows: List[dict], baseline_rows: List[dict]) -> dict:
    """
    Calcule les métriques d'impact pour une zone à partir de ses relevés
    pendant l'événement et pendant la période de référence.
    """
    if not rows:
        return None

    scores = [r["urban_score"] for r in rows]
    peak_score = max(scores)
    avg_score = round(sum(scores) / len(scores), 1)
    peak_row = next(r for r in rows if r["urban_score"] == peak_score)

    # Durée au-dessus des seuils
    n = len(scores)
    minutes_tendu = sum(1 for s in scores if s >= 55) * (n and 1)
    minutes_critique = sum(1 for s in scores if s >= 72) * (n and 1)

    # Niveaux observés
    level_counts = defaultdict(int)
    for r in rows:
        level_counts[r["level"]] += 1

    # Signaux dominants (moyennes normalisées pendant la période)
    signal_avgs = {}
    for sig in ("traffic", "weather", "event", "transport"):
        vals = [r[sig] for r in rows if r.get(sig) is not None]
        if vals:
            signal_avgs[SIGNAL_LABELS.get(sig, sig)] = round(sum(vals) / len(vals), 3)

    # Raw signal averages
    raw_avgs = {}
    for sig in ("raw_traffic", "raw_weather", "raw_event", "raw_transport", "raw_incident"):
        vals = [r[sig] for r in rows if r.get(sig) is not None]
        if vals:
            label = sig.replace("raw_", "")
            raw_avgs[label] = round(sum(vals) / len(vals), 3)

    # Baseline comparison
    baseline_avg = None
    delta_vs_baseline = None
    if baseline_rows:
        bl_scores = [r["urban_score"] for r in baseline_rows]
        if bl_scores:
            baseline_avg = round(sum(bl_scores) / len(bl_scores), 1)
            delta_vs_baseline = round(avg_score - baseline_avg, 1)

    return {
        "data_points": n,
        "peak_score": peak_score,
        "peak_level": score_level(peak_score),
        "peak_at": peak_row["ts"],
        "avg_score": avg_score,
        "level_distribution": dict(level_counts),
        "readings_tendu": minutes_tendu,
        "readings_critique": minutes_critique,
        "signal_averages_normalized": signal_avgs,
        "raw_signal_averages": raw_avgs,
        "baseline_avg_score": baseline_avg,
        "delta_vs_baseline": delta_vs_baseline,
    }


def _build_impact_report(
    start: str,
    end: str,
    baseline_start: Optional[str],
    baseline_end: Optional[str],
    event_name: Optional[str] = None,
) -> dict:
    """Construit le rapport d'impact complet."""
    rows = get_history_range(start, end)
    if not rows:
        raise HTTPException(
            status_code=404,
            detail=f"Aucune donnée historique entre {start} et {end}.",
        )

    # Baseline rows
    baseline_rows_all = []
    if baseline_start and baseline_end:
        baseline_rows_all = get_history_range(baseline_start, baseline_end)

    # Alertes pendant la période
    alerts = get_alerts_range(start, end)

    # Grouper par zone
    zone_rows: Dict[str, list] = defaultdict(list)
    for r in rows:
        zone_rows[r["zone_id"]].append(r)

    zone_baseline: Dict[str, list] = defaultdict(list)
    for r in baseline_rows_all:
        zone_baseline[r["zone_id"]].append(r)

    # Calcul par zone
    zones_impact = {}
    for zone_id in sorted(zone_rows.keys()):
        impact = _compute_zone_impact(
            zone_rows[zone_id],
            zone_baseline.get(zone_id, []),
        )
        if impact:
            zones_impact[zone_id] = {
                "zone_name": ZONE_NAMES.get(zone_id, zone_id),
                **impact,
            }

    # Scores globaux (toutes zones confondues)
    all_scores = [r["urban_score"] for r in rows]
    global_avg = round(sum(all_scores) / len(all_scores), 1)
    global_peak = max(all_scores)
    peak_row = next(r for r in rows if r["urban_score"] == global_peak)

    # Top 3 zones les plus impactées (par score moyen)
    ranked = sorted(
        zones_impact.items(),
        key=lambda x: x[1]["avg_score"],
        reverse=True,
    )
    top_zones = [
        {"zone_id": zid, "zone_name": data["zone_name"], "avg_score": data["avg_score"],
         "peak_score": data["peak_score"], "peak_level": data["peak_level"]}
        for zid, data in ranked[:3]
    ]

    # Delta global vs baseline
    global_baseline_avg = None
    global_delta = None
    if baseline_rows_all:
        bl_scores = [r["urban_score"] for r in baseline_rows_all]
        if bl_scores:
            global_baseline_avg = round(sum(bl_scores) / len(bl_scores), 1)
            global_delta = round(global_avg - global_baseline_avg, 1)

    return {
        "report_type": "post_event_impact",
        "event_name": event_name,
        "period": {"start": start, "end": end},
        "baseline_period": (
            {"start": baseline_start, "end": baseline_end}
            if baseline_start else None
        ),
        "summary": {
            "total_data_points": len(rows),
            "zones_analyzed": len(zones_impact),
            "global_avg_score": global_avg,
            "global_peak_score": global_peak,
            "global_peak_zone": peak_row["zone_id"],
            "global_peak_at": peak_row["ts"],
            "global_peak_level": score_level(global_peak),
            "baseline_avg_score": global_baseline_avg,
            "delta_vs_baseline": global_delta,
            "total_alerts": len(alerts),
            "alerts_critique": sum(1 for a in alerts if a["alert_type"] == "CRITIQUE"),
            "alerts_tendu": sum(1 for a in alerts if a["alert_type"] == "TENDU"),
        },
        "top_impacted_zones": top_zones,
        "zones": zones_impact,
        "alerts": alerts,
    }


@router.get("/impact")
async def impact_report(
    start: str = Query(..., description="Début période (ISO, ex: 2026-03-20T08:00:00)"),
    end: str = Query(..., description="Fin période (ISO, ex: 2026-03-20T22:00:00)"),
    baseline_start: Optional[str] = Query(None, description="Début période de référence"),
    baseline_end: Optional[str] = Query(None, description="Fin période de référence"),
):
    """
    Rapport d'impact sur une période arbitraire.
    Compare les scores observés à une période de référence (optionnelle).
    """
    return _build_impact_report(start, end, baseline_start, baseline_end)


@router.get("/impact/event/{event_name}")
async def event_impact_report(event_name: str):
    """
    Rapport d'impact pour un événement du calendrier statique.
    La période de référence est automatiquement calculée (semaine précédente, mêmes heures).
    """
    # Chercher l'événement dans le calendrier
    matches = [
        ev for ev in STATIC_EVENTS
        if event_name.lower() in ev["name"].lower()
    ]
    if not matches:
        available = sorted(set(ev["name"] for ev in STATIC_EVENTS))
        raise HTTPException(
            status_code=404,
            detail=f"Événement '{event_name}' non trouvé. Disponibles : {available}",
        )

    ev = matches[0]
    dates = sorted(ev["dates"])
    start_date = dates[0]
    end_date = dates[-1]

    start = f"{start_date.isoformat()}T00:00:00+00:00"
    end = f"{end_date.isoformat()}T23:59:59+00:00"

    # Baseline = même période la semaine précédente
    bl_start = f"{(start_date - timedelta(days=7)).isoformat()}T00:00:00+00:00"
    bl_end = f"{(end_date - timedelta(days=7)).isoformat()}T23:59:59+00:00"

    return _build_impact_report(start, end, bl_start, bl_end, event_name=ev["name"])


@router.get("/events")
async def list_events():
    """Liste les événements du calendrier statique disponibles pour analyse."""
    seen = set()
    events = []
    for ev in STATIC_EVENTS:
        if ev["name"] in seen:
            continue
        seen.add(ev["name"])
        dates = sorted(ev["dates"])
        events.append({
            "name": ev["name"],
            "start": dates[0].isoformat(),
            "end": dates[-1].isoformat(),
            "zone": ev["zone"],
            "zone_name": ZONE_NAMES.get(ev["zone"], ev["zone"]),
            "weight": ev["weight"],
        })
    return {"count": len(events), "events": events}
