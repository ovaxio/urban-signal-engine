"""
Rapports d'impact — post-événement et pré-événement.

Endpoints :
    GET /reports/impact?start=...&end=...             — post-event (période libre)
    GET /reports/impact/event/{event_name}             — post-event (calendrier)
    GET /reports/pre-event/{event_name}?date=...       — pré-événement (simulation 24h)
    GET /reports/pre-event/{event_name}/pdf?date=...   — pré-événement PDF
    GET /reports/events                                — liste événements disponibles
"""

import logging
import re
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from services.events import STATIC_EVENTS, _days
from services.scoring import ZONE_NAMES, SIGNAL_LABELS, NEIGHBORS, score_level
from services.simulation import simulate_event_profile
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


# ─── Rapport pré-événement ────────────────────────────────────────────────────

_RECO_TEMPLATES = {
    0: [  # CALME (< 35)
        "Conditions nominales. Dispositif standard suffisant.",
        "Aucune alerte prévue sur les zones surveillées.",
    ],
    1: [  # MODÉRÉ (35-55)
        "Vigilance renforcée recommandée sur {zone}.",
        "Prévoir un effectif de réserve mobilisable sous 30 minutes.",
    ],
    2: [  # TENDU (55-71)
        "Renforcer le dispositif périmètre {zone} dès {hour}h.",
        "Prévoir rotation effectifs sur le créneau {from_h}h-{to_h}h.",
        "Coordonner avec TCL pour information flux transport.",
    ],
    3: [  # CRITIQUE (72-100)
        "Dispositif renforcé obligatoire. Activation protocole événement majeur.",
        "Présence terrain recommandée dès T-3h ({hour}h).",
        "Alerter le donneur d'ordres — conditions hors référentiel normal.",
    ],
}


def _recommendation_level(score: int) -> int:
    if score < 35:
        return 0
    if score < 55:
        return 1
    if score < 72:
        return 2
    return 3


def _build_recommendations(
    zones_analysis: Dict,
    primary_zones: List[str],
) -> List[Dict]:
    """Generate actionable recommendations from simulation data."""
    recommendations = []

    # Determine overall recommendation level from primary zones
    max_peak = 0
    for zid in primary_zones:
        zdata = zones_analysis.get(zid)
        if zdata:
            max_peak = max(max_peak, zdata["peak_score"])

    level = _recommendation_level(max_peak)
    templates = _RECO_TEMPLATES[level]

    # Find the main risk window across primary zones
    main_zone = None
    main_window = None
    for zid in primary_zones:
        zdata = zones_analysis.get(zid)
        if not zdata:
            continue
        for rw in zdata.get("risk_windows", []):
            if main_window is None or rw["peak_score"] > main_window["peak_score"]:
                main_window = rw
                main_zone = zid

    zone_name = ZONE_NAMES.get(main_zone, main_zone) if main_zone else ""
    hour = main_window["from"] if main_window else 8
    from_h = main_window["from"] if main_window else 8
    to_h = main_window["to"] if main_window else 20

    for tpl in templates:
        text = tpl.format(
            zone=zone_name,
            hour=max(hour - 3, 6) if "{hour}" in tpl and level == 3 else hour,
            from_h=from_h,
            to_h=to_h,
        )
        recommendations.append({
            "level": level,
            "text": text,
        })

    return recommendations


def _build_risk_windows_summary(
    zones_analysis: Dict,
    focus_zones: List[str],
) -> List[Dict]:
    """Build risk windows summary with recommendations per window."""
    windows = []
    for zid in focus_zones:
        zdata = zones_analysis.get(zid)
        if not zdata:
            continue
        for rw in zdata.get("risk_windows", []):
            level = _recommendation_level(rw["peak_score"])
            reco_tpls = _RECO_TEMPLATES.get(level, _RECO_TEMPLATES[0])
            zone_name = ZONE_NAMES.get(zid, zid)
            reco = reco_tpls[0].format(
                zone=zone_name, hour=rw["from"],
                from_h=rw["from"], to_h=rw["to"],
            )
            windows.append({
                "zone": zid,
                "zone_name": zone_name,
                "from": rw["from"],
                "to": rw["to"],
                "level": rw["level"],
                "peak_score": rw["peak_score"],
                "main_signal": rw["main_signal"],
                "recommendation": reco,
            })
    # Sort by peak_score descending
    windows.sort(key=lambda w: w["peak_score"], reverse=True)
    return windows


def _build_signals_breakdown(
    zones_analysis: Dict,
    focus_zones: List[str],
) -> Dict:
    """For each focus zone, compute avg z-scores across all hours."""
    breakdown = {}
    for zid in focus_zones:
        zdata = zones_analysis.get(zid)
        if not zdata or not zdata.get("hourly"):
            continue
        hourly = zdata["hourly"]
        sig_keys = ["traffic", "weather", "transport", "event", "incident"]
        avgs = {}
        for s in sig_keys:
            vals = [h["signals"].get(s, 0.0) for h in hourly]
            avgs[f"{s}_zscore"] = round(sum(vals) / len(vals), 2) if vals else 0.0
        # Dominant signal = highest avg z-score
        dominant = max(sig_keys, key=lambda s: avgs[f"{s}_zscore"])
        avgs["dominant_signal"] = dominant
        breakdown[zid] = avgs
    return breakdown


@router.get("/pre-event/{event_name}")
async def pre_event_report(
    event_name: str,
    date: Optional[str] = Query(None, description="Date cible YYYY-MM-DD (défaut: T+48h)"),
):
    """
    Rapport pré-événement : simulation 24h avec fenêtres de risque,
    zones à surveiller, et recommandations opérationnelles.
    """
    import re as _re

    # Resolve event
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

    # Resolve date
    if date:
        if not _re.match(r"^\d{4}-\d{2}-\d{2}$", date):
            raise HTTPException(status_code=400, detail="Format date invalide. Utilisez YYYY-MM-DD.")
        from datetime import date as date_type
        target_date = date_type.fromisoformat(date)
    else:
        # Default: first date of the matched event (not T+48h)
        target_date = sorted(ev["dates"])[0]

    # Run simulation
    sim = await simulate_event_profile(target_date, event_name)

    # Primary zones: event zone + neighbors
    primary_zone = ev["zone"]
    all_event_zones = set()
    for e in matches:
        all_event_zones.add(e["zone"])
    # Also include neighbors of primary zone for spillover
    neighbor_zones = set(NEIGHBORS.get(primary_zone, []))
    focus_zones = sorted(all_event_zones | neighbor_zones)

    # Filter zones_analysis to focus zones
    zones_analysis = {z: sim["zones"][z] for z in focus_zones if z in sim["zones"]}

    # Executive summary
    critical_zones = []
    peak_window_score = 0
    peak_window = {"from": 8, "to": 20}
    for zid in sorted(focus_zones):
        zdata = sim["zones"].get(zid)
        if not zdata:
            continue
        if zdata["peak_score"] >= 72:
            critical_zones.append(zid)
        for rw in zdata.get("risk_windows", []):
            if rw["peak_score"] > peak_window_score:
                peak_window_score = rw["peak_score"]
                peak_window = {"from": rw["from"], "to": rw["to"]}

    overall_max = max(
        (zones_analysis[z]["peak_score"] for z in focus_zones if z in zones_analysis),
        default=29,
    )
    overall_risk = score_level(overall_max)
    rec_level = _recommendation_level(overall_max)

    # Horizon confidence
    days_ahead = (target_date - datetime.now(timezone.utc).date()).days
    if days_ahead < 0:
        confidence = "retrospective"
    elif days_ahead <= 2:
        confidence = "high"
    elif days_ahead <= 7:
        confidence = "medium"
    else:
        confidence = "low"

    # Compute overall dominant signal from breakdown
    signals_breakdown = _build_signals_breakdown(zones_analysis, focus_zones)
    _all_dom = [v.get("dominant_signal", "traffic") for v in signals_breakdown.values()]
    _dominant_signal = max(set(_all_dom), key=_all_dom.count) if _all_dom else "traffic"
    _SIGNAL_LABELS = {"traffic": "trafic", "weather": "météo", "transport": "transport", "event": "événement", "incident": "incident"}
    _dominant_label = _SIGNAL_LABELS.get(_dominant_signal, _dominant_signal)

    # ── BLUF narrative ──────────────────────────────────────────────────
    critical_zone_names = [ZONE_NAMES.get(z, z) for z in critical_zones]
    if overall_max >= 72:
        bluf = (
            f"{ev['name']} du {target_date.strftime('%d/%m')} présente un risque {overall_risk} "
            f"(pic estimé {overall_max}) concentré sur "
            f"{', '.join(critical_zone_names[:3])} entre {peak_window['from']}h et {peak_window['to']}h. "
            f"Signal dominant : {_dominant_label}. Renforcement dispositif recommandé dès {max(peak_window['from'] - 3, 6)}h."
        )
    elif overall_max >= 55:
        bluf = (
            f"{ev['name']} du {target_date.strftime('%d/%m')} présente un risque {overall_risk} "
            f"(pic estimé {overall_max}) sur {', '.join(critical_zone_names[:3]) or 'les zones surveillées'} "
            f"entre {peak_window['from']}h et {peak_window['to']}h. "
            f"Vigilance renforcée recommandée."
        )
    else:
        bluf = (
            f"{ev['name']} du {target_date.strftime('%d/%m')} — conditions nominales prévues "
            f"(pic estimé {overall_max}, {overall_risk}). Dispositif standard suffisant."
        )

    # ── Escalation triggers ─────────────────────────────────────────────
    escalation_triggers = []
    if overall_max >= 55:
        escalation_triggers.append({
            "condition": f"Score dépasse 65 sur une zone primaire à T-2h",
            "action": "Activer protocole renforcé. Ajouter effectifs périmètre.",
        })
    if sim["weather_context"]["risk_modifier"] in ("medium", "high"):
        escalation_triggers.append({
            "condition": "Dégradation météo confirmée (pluie > 5mm/h ou vent > 50km/h)",
            "action": "Ajouter 2 agents périmètre. Sécuriser accès glissants.",
        })
    if len(critical_zones) >= 3:
        escalation_triggers.append({
            "condition": f"3+ zones simultanément en CRITIQUE",
            "action": "Coordination inter-zones. Alerter le donneur d'ordres.",
        })
    escalation_triggers.append({
        "condition": "Incident majeur non prévu (accident, manif, panne TCL)",
        "action": "Basculer en mode incident. Rapport actualisé disponible en temps réel sur le dashboard.",
    })

    # ── DPS mapping ─────────────────────────────────────────────────────
    _DPS_MAP = {
        0: {"categorie": "PAPS", "description": "Dispositif de base (2 secouristes)", "ratio": "1 agent / 300 personnes"},
        1: {"categorie": "DPS-PE", "description": "Petit événement", "ratio": "1 agent / 200 personnes"},
        2: {"categorie": "DPS-ME", "description": "Moyen événement — dispositif renforcé", "ratio": "1 agent / 100 personnes"},
        3: {"categorie": "DPS-GE", "description": "Grand événement — coordination préfectorale", "ratio": "1 agent / 50 personnes"},
    }
    dps = _DPS_MAP[rec_level]
    n_zones_tendu = sum(1 for z in focus_zones if zones_analysis.get(z, {}).get("peak_score", 0) >= 55)
    _weight_mult = 2.0 if ev["weight"] >= 1.5 else 1.5 if ev["weight"] >= 1.0 else 1.0
    _staff_low = max(int(n_zones_tendu * 4 * _weight_mult), 2)
    _staff_high = max(int(n_zones_tendu * 6 * _weight_mult), 4)
    staffing_estimate = f"{_staff_low}-{_staff_high} agents" if n_zones_tendu > 0 else "Effectif standard"

    # Build report
    return {
        "report_type": "pre_event",
        "event": {
            "name": ev["name"],
            "date": target_date.isoformat(),
            "primary_zones": sorted(all_event_zones),
            "zone_names": {z: ZONE_NAMES.get(z, z) for z in all_event_zones},
            "weight": ev["weight"],
        },
        "generated_at": sim["generated_at"],
        "simulation_horizon_h": days_ahead * 24,
        "bluf": bluf,
        "executive_summary": {
            "overall_risk": overall_risk,
            "overall_peak_score": overall_max,
            "critical_zones": critical_zones,
            "peak_window": peak_window,
            "recommendation_level": rec_level,
        },
        "zones_analysis": zones_analysis,
        "risk_windows_summary": _build_risk_windows_summary(zones_analysis, focus_zones),
        "recommendations": _build_recommendations(zones_analysis, sorted(all_event_zones)),
        "escalation_triggers": escalation_triggers,
        "dps": {
            **dps,
            "staffing_estimate": staffing_estimate,
            "zones_tendu": n_zones_tendu,
        },
        "weather_context": sim["weather_context"],
        "signals_breakdown": signals_breakdown,
        "data_confidence": confidence,
        "next_update": f"Rapport actualisé disponible à J-1 ({(target_date - timedelta(days=1)).isoformat()}).",
    }


@router.get("/pre-event/{event_name}/pdf")
async def pre_event_pdf(
    event_name: str,
    date: Optional[str] = Query(None, description="Date cible YYYY-MM-DD"),
):
    """
    Rapport pré-événement au format PDF.
    Même données que /pre-event/{event_name} mais rendu en document PDF.
    """
    # Reuse the JSON report logic
    report = await pre_event_report(event_name, date)

    from services.pdf_report import generate_pre_event_pdf
    pdf_bytes = generate_pre_event_pdf(report)

    # Build filename
    safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", event_name)[:40]
    target = report["event"]["date"]
    filename = f"USE_PreEvent_{safe_name}_{target}.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
