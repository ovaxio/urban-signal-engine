"""
Urban Signal Engine — Event Simulation Service
================================================
Profil horaire simulé 24h pour analyse pré-événement.

Fonction centrale : simulate_event_profile(target_date, event_name)
Utilisée par /zones/simulate (24h) et /reports/pre-event/{event_name}.
"""

import httpx
import logging
from datetime import date, datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from config import ZONE_CENTROIDS
from services.scoring import (
    BASELINE, _effective_baseline, score_all_zones, score_level,
    normalize, ZONE_NAMES,
)
from services.events import compute_event_signals, STATIC_EVENTS

log = logging.getLogger("simulation")

SIM_HOURS = list(range(6, 24))  # 6h-23h = 18 points


# ─── Weather forecast for target date ─────────────────────────────────────────

_OPEN_METEO_FORECAST = (
    "https://api.open-meteo.com/v1/forecast"
    "?latitude=45.748&longitude=4.847"
    "&hourly=precipitation,wind_speed_10m,weather_code,temperature_2m"
    "&timezone=Europe/Paris"
)

_OPEN_METEO_ARCHIVE = (
    "https://archive-api.open-meteo.com/v1/archive"
    "?latitude=45.748&longitude=4.847"
    "&daily=precipitation_sum,wind_speed_10m_max,temperature_2m_max,temperature_2m_min,weather_code"
    "&timezone=Europe/Paris"
)

# Cache climatologie par (mois, jour) — ne change pas dans la journée
_historical_cache: Dict[tuple, Dict[int, Dict]] = {}


async def _fetch_weather_forecast(target_date: date) -> Dict[int, Dict]:
    """Try Open-Meteo forecast API (works for dates within ~16 days)."""
    from services.ingestion import _weather_score_from_values

    url = f"{_OPEN_METEO_FORECAST}&start_date={target_date}&end_date={target_date}"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(url)
            r.raise_for_status()
            data = r.json()
    except Exception as e:
        log.warning("[sim-weather] Forecast fetch failed: %s", e)
        return {}

    hourly = data.get("hourly", {})
    times = hourly.get("time", [])
    if not times:
        return {}
    precip = hourly.get("precipitation", [])
    wind = hourly.get("wind_speed_10m", [])
    wmo = hourly.get("weather_code", [])
    temp = hourly.get("temperature_2m", [])

    result: Dict[int, Dict] = {}
    for i, t in enumerate(times):
        try:
            h = int(t.split("T")[1].split(":")[0])
        except (IndexError, ValueError):
            continue
        p = float(precip[i]) if i < len(precip) and precip[i] is not None else 0.0
        w = float(wind[i]) if i < len(wind) and wind[i] is not None else 0.0
        c = int(wmo[i]) if i < len(wmo) and wmo[i] is not None else 0
        tp = float(temp[i]) if i < len(temp) and temp[i] is not None else 15.0
        result[h] = {
            "temp": round(tp, 1),
            "precip_mm": round(p, 1),
            "wind_kmh": round(w, 1),
            "wmo_code": c,
            "weather_score": round(_weather_score_from_values(p, w, c), 3),
            "source": "forecast",
        }
    log.info("[sim-weather] forecast: %d heures pour %s", len(result), target_date)
    return result


async def _fetch_historical_climatology(target_date: date) -> Dict[int, Dict]:
    """
    Build weather estimate from historical averages (Open-Meteo Archive API).
    Fetches same date ±7 days over the last 5 years, computes medians/means.
    """
    from services.ingestion import _weather_score_from_values

    cache_key = (target_date.month, target_date.day)
    if cache_key in _historical_cache:
        log.info("[sim-weather] climatologie cache hit pour %02d/%02d", *cache_key)
        return _historical_cache[cache_key]

    YEARS_BACK = 5
    WINDOW_DAYS = 7

    all_precip: List[float] = []
    all_wind: List[float] = []
    all_wmo: List[int] = []
    all_temp_max: List[float] = []
    all_temp_min: List[float] = []

    async with httpx.AsyncClient(timeout=15) as client:
        for years_ago in range(1, YEARS_BACK + 1):
            year = target_date.year - years_ago
            try:
                center = target_date.replace(year=year)
            except ValueError:
                continue  # Feb 29 on non-leap year
            start = center - timedelta(days=WINDOW_DAYS)
            end = center + timedelta(days=WINDOW_DAYS)

            url = f"{_OPEN_METEO_ARCHIVE}&start_date={start}&end_date={end}"
            try:
                r = await client.get(url)
                r.raise_for_status()
                data = r.json()
            except Exception as e:
                log.warning("[sim-weather] archive %d failed: %s", year, e)
                continue

            daily = data.get("daily", {})
            for v in daily.get("precipitation_sum", []):
                if v is not None:
                    all_precip.append(float(v))
            for v in daily.get("wind_speed_10m_max", []):
                if v is not None:
                    all_wind.append(float(v))
            for v in daily.get("weather_code", []):
                if v is not None:
                    all_wmo.append(int(v))
            for v in daily.get("temperature_2m_max", []):
                if v is not None:
                    all_temp_max.append(float(v))
            for v in daily.get("temperature_2m_min", []):
                if v is not None:
                    all_temp_min.append(float(v))

    if not all_precip:
        log.warning("[sim-weather] climatologie: aucune donnée → vide")
        return {}

    # Agrégation
    median_precip = sorted(all_precip)[len(all_precip) // 2]
    mean_wind = sum(all_wind) / len(all_wind) if all_wind else 10.0
    mode_wmo = max(set(all_wmo), key=all_wmo.count) if all_wmo else 0
    mean_temp = (
        (sum(all_temp_max) / len(all_temp_max) + sum(all_temp_min) / len(all_temp_min)) / 2
        if all_temp_max and all_temp_min else 15.0
    )

    score = _weather_score_from_values(median_precip, mean_wind, mode_wmo)

    log.info(
        "[sim-weather] climatologie %02d/%02d: precip=%.1fmm wind=%.0fkm/h temp=%.1f°C wmo=%d score=%.2f (%d points)",
        target_date.month, target_date.day,
        median_precip, mean_wind, mean_temp, mode_wmo, score, len(all_precip),
    )

    # Appliquer uniformément sur toutes les heures (données daily, pas horaires)
    result: Dict[int, Dict] = {}
    for h in range(24):
        result[h] = {
            "temp": round(mean_temp, 1),
            "precip_mm": round(median_precip, 1),
            "wind_kmh": round(mean_wind, 1),
            "wmo_code": mode_wmo,
            "weather_score": round(score, 3),
            "source": "historical_avg",
        }

    _historical_cache[cache_key] = result
    return result


async def _fetch_weather_for_date(target_date: date) -> Dict[int, Dict]:
    """
    Weather data for simulation: forecast if available (<16 days),
    otherwise historical climatology (archive API, 5 years average).
    """
    # Try forecast first
    result = await _fetch_weather_forecast(target_date)
    if result:
        return result

    # Fallback: historical climatology
    return await _fetch_historical_climatology(target_date)


# ─── Risk windows detection ──────────────────────────────────────────────────

def _detect_risk_windows(
    hourly: List[Dict], threshold: int = 55,
) -> List[Dict]:
    """
    Group consecutive hours where score >= threshold into risk windows.
    Each window has from/to hours, max level, and dominant signal.
    """
    windows: List[Dict] = []
    current_window = None

    for entry in hourly:
        if entry["score"] >= threshold:
            if current_window is None:
                current_window = {
                    "from": entry["hour"],
                    "to": entry["hour"],
                    "peak_score": entry["score"],
                    "peak_level": entry["level"],
                    "signals_acc": {s: [] for s in ("traffic", "weather", "transport", "event", "incident")},
                }
            current_window["to"] = entry["hour"]
            if entry["score"] > current_window["peak_score"]:
                current_window["peak_score"] = entry["score"]
                current_window["peak_level"] = entry["level"]
            for s in current_window["signals_acc"]:
                current_window["signals_acc"][s].append(entry["signals"].get(s, 0.0))
        else:
            if current_window is not None:
                windows.append(_finalize_window(current_window))
                current_window = None

    if current_window is not None:
        windows.append(_finalize_window(current_window))

    return windows


def _finalize_window(w: Dict) -> Dict:
    """Compute main_signal from accumulated signal z-scores."""
    avg_signals = {
        s: sum(vals) / len(vals) if vals else 0.0
        for s, vals in w["signals_acc"].items()
    }
    main_signal = max(avg_signals, key=avg_signals.get) if avg_signals else "traffic"
    return {
        "from": w["from"],
        "to": w["to"] + 1,  # exclusive end (17-20 means 17h to 21h)
        "level": w["peak_level"],
        "peak_score": w["peak_score"],
        "main_signal": main_signal,
    }


# ─── Weather context summary ─────────────────────────────────────────────────

def _weather_context(weather_data: Dict[int, Dict], hours: List[int]) -> Dict:
    """Build weather context summary from forecast data."""
    if not weather_data:
        return {
            "summary": "Données météo indisponibles.",
            "risk_modifier": "unknown",
        }

    # Detect source
    first = next(iter(weather_data.values()), {})
    is_historical = first.get("source") == "historical_avg"

    relevant = {h: weather_data[h] for h in hours if h in weather_data}
    if not relevant:
        return {
            "summary": "Pas de données météo sur le créneau horaire.",
            "risk_modifier": "none",
        }

    max_precip = max(d["precip_mm"] for d in relevant.values())
    max_wind = max(d["wind_kmh"] for d in relevant.values())
    min_temp = min(d["temp"] for d in relevant.values())

    # Rain hours
    rain_hours = [h for h, d in sorted(relevant.items()) if d["precip_mm"] > 0.5]
    rain_total = sum(d["precip_mm"] for d in relevant.values())

    parts = []
    risk = "none"

    if max_precip > 2.0:
        if rain_hours:
            rain_range = f"{rain_hours[0]}h-{rain_hours[-1] + 1}h"
            parts.append(f"Pluie prévue {rain_range} ({rain_total:.1f}mm cumulés)")
        risk = "medium" if max_precip > 5.0 else "low"
    elif max_precip > 0.5:
        parts.append(f"Pluie légère possible ({max_precip:.1f}mm max)")
        risk = "low"

    if max_wind > 40:
        parts.append(f"Vent fort ({max_wind:.0f} km/h)")
        risk = "medium" if risk != "medium" else "high"

    if min_temp < 5:
        parts.append(f"Températures basses ({min_temp:.0f}°C)")
        if risk == "none":
            risk = "low"

    if not parts:
        avg_temp = sum(d["temp"] for d in relevant.values()) / len(relevant)
        parts.append(f"Conditions clémentes ({avg_temp:.0f}°C, pas de pluie)")

    summary = ". ".join(parts) + "."
    impact_label = {"none": "Aucun impact", "low": "Impact modéré", "medium": "Impact significatif", "high": "Impact fort"}
    summary += f" {impact_label.get(risk, '')}."

    if is_historical:
        summary += " (Estimation climatologique — moyennes 2021-2025, ±7 jours.)"

    return {"summary": summary, "risk_modifier": risk}


# ─── Main simulation function ────────────────────────────────────────────────

async def simulate_event_profile(
    target_date: date,
    event_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Compute 24h hourly simulation for all 12 zones on target_date.
    Shared by /zones/simulate and /reports/pre-event.

    Returns structured dict with per-zone hourly scores, risk windows,
    weather forecast, and event metadata.
    """

    # 1. Weather forecast (single fetch for the full day)
    weather_data = await _fetch_weather_for_date(target_date)

    # 2. Resolve event metadata and active events for this date
    event_meta = None
    if event_name:
        for ev in STATIC_EVENTS:
            if event_name.lower() in ev["name"].lower():
                hours_info = ev.get("hours")
                event_meta = {
                    "name": ev["name"],
                    "zone": ev["zone"],
                    "zone_name": ZONE_NAMES.get(ev["zone"], ev["zone"]),
                    "weight": ev["weight"],
                    "dates": [d.isoformat() for d in sorted(ev["dates"])],
                    "hours": list(hours_info) if hours_info else None,
                    "ramp": ev.get("ramp", 1),
                }
                break

    # 3. Precompute per-hour event signals (using hours + ramp from events.py)
    #    For each hour, compute the event intensity multiplier [0.0 – 1.0]:
    #    - Outside event hours: 0.0 (no event impact)
    #    - During ramp-up (before start): linear 0.0 → 1.0 (people arriving)
    #    - During event hours: 1.0 (full impact)
    #    - During ramp-down (after end): linear 1.0 → 0.0 (people leaving)
    active_on_date = [ev for ev in STATIC_EVENTS if target_date in ev["dates"]]

    def _event_intensity(hour: int, ev: dict) -> float:
        """Returns 0.0-1.0 intensity for an event at a given hour."""
        hours = ev.get("hours")
        if not hours:
            return 1.0  # no hours defined → all day
        start_h, end_h = hours
        ramp = ev.get("ramp", 1)
        if start_h - ramp <= hour < start_h:
            # ramp-up: arriving
            return (hour - (start_h - ramp)) / ramp
        elif start_h <= hour < end_h:
            # active hours
            return 1.0
        elif end_h <= hour < end_h + ramp:
            # ramp-down: leaving
            return 1.0 - (hour - end_h) / ramp
        else:
            return 0.0

    def _hourly_event_signals(hour: int) -> Dict[str, float]:
        """Compute event signals for all zones at a specific hour, respecting event hours."""
        from services.events import _haversine_km, EVENT_RADIUS_KM
        scores: Dict[str, float] = {z: 0.0 for z in ZONE_CENTROIDS}
        for ev in active_on_date:
            intensity = _event_intensity(hour, ev)
            if intensity <= 0:
                continue
            for zone_id, (zlat, zlng) in ZONE_CENTROIDS.items():
                dist = _haversine_km(ev["lat"], ev["lng"], zlat, zlng)
                if dist <= EVENT_RADIUS_KM:
                    proximity = 1.0 - (dist / EVENT_RADIUS_KM)
                    scores[zone_id] += ev["weight"] * proximity * intensity
        return {z: round(min(v, 3.0), 4) for z, v in scores.items()}

    # 4. Compute scores for each hour
    zones_result: Dict[str, Dict] = {z: {"hourly": []} for z in ZONE_CENTROIDS}

    for hour in SIM_HOURS:
        # Build signals for all zones at this hour
        dt = datetime.fromisoformat(f"{target_date}T{hour:02d}:00:00+00:00")

        # Per-hour event signals (respects event hours + ramp)
        event_signals = _hourly_event_signals(hour)

        weather_score = BASELINE["weather"]["mu"]  # default
        if hour in weather_data:
            weather_score = weather_data[hour]["weather_score"]

        all_signals: Dict[str, Dict[str, float]] = {}
        for zone_id, ev_sig in event_signals.items():
            bl = _effective_baseline(zone_id, dt)
            traffic_base = bl["traffic"]["mu"] * (1 + ev_sig * 0.8)
            transport_base = bl["transport"]["mu"] * (1 + ev_sig * 0.5)
            incident_base = bl["incident"]["mu"] * (1 + ev_sig * 0.2)
            all_signals[zone_id] = {
                "traffic": min(traffic_base, 3.0),
                "weather": weather_score,
                "event": ev_sig,
                "transport": min(transport_base, 1.0),
                "incident": incident_base,
            }

        # Score all zones at this hour (uses φ(dt) internally)
        scores = score_all_zones(all_signals, dt=dt)
        score_map = {z["zone_id"]: z for z in scores}

        for zone_id in ZONE_CENTROIDS:
            z = score_map[zone_id]
            bl = _effective_baseline(zone_id, dt)
            sigs = all_signals[zone_id]
            zones_result[zone_id]["hourly"].append({
                "hour": hour,
                "score": z["urban_score"],
                "level": z["level"],
                "signals": {
                    "traffic": round(normalize(sigs["traffic"], "traffic", bl), 2),
                    "weather": round(normalize(sigs["weather"], "weather", bl), 2),
                    "transport": round(normalize(sigs["transport"], "transport", bl), 2),
                    "event": round(normalize(sigs["event"], "event", bl), 2),
                    "incident": round(normalize(sigs["incident"], "incident", bl), 2),
                },
            })

    # 5. Per-zone aggregates: peak, risk windows
    for zone_id, zdata in zones_result.items():
        hourly = zdata["hourly"]
        scores_list = [h["score"] for h in hourly]
        peak_idx = scores_list.index(max(scores_list))
        zdata["peak_hour"] = hourly[peak_idx]["hour"]
        zdata["peak_score"] = hourly[peak_idx]["score"]
        zdata["peak_level"] = hourly[peak_idx]["level"]
        zdata["risk_windows"] = _detect_risk_windows(hourly)

    # 6. Active events on this date
    active_events = [ev["name"] for ev in STATIC_EVENTS if target_date in ev["dates"]]

    # 7. Weather forecast output (hours 6-23 only)
    weather_output: Dict[str, Dict] = {}
    for h in SIM_HOURS:
        if h in weather_data:
            wd = weather_data[h]
            weather_output[str(h)] = {
                "temp": wd["temp"],
                "precip_mm": wd["precip_mm"],
                "wind_kmh": wd["wind_kmh"],
            }

    now = datetime.now(timezone.utc)
    return {
        "date": target_date.isoformat(),
        "event_name": event_name,
        "event_meta": event_meta,
        "active_events": active_events,
        "zones": zones_result,
        "weather_forecast": {
            "source": next(iter(weather_data.values()), {}).get("source", "open-meteo")
                      if weather_data else "none",
            "fetched_at": now.isoformat(timespec="seconds"),
            "hourly": weather_output,
        },
        "weather_context": _weather_context(weather_data, SIM_HOURS),
        "generated_at": now.isoformat(timespec="seconds"),
    }
