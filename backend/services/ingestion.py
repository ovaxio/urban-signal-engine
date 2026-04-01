import math
import os
import re
import asyncio
import base64
import datetime
import logging
from typing import Dict, Optional

import httpx
from config import (
    APIS, ENABLE_HISTORY, CRITER_ETAT_TO_RATIO, ZONE_CENTROIDS,
    WEATHER_PRECIP_DIVISOR, WEATHER_WIND_THRESHOLD,
    WEATHER_WMO_SCORE, WEATHER_SCORE_MAX,
    MULTIZONE_ENABLED, MULTIZONE_SIGMA_KM, MULTIZONE_MIN_WEIGHT,
)
from services.events import fetch_event_signals
from services.smoothing import smooth_signals
from services.scoring import _effective_baseline


log = logging.getLogger("ingestion")

# ---------------------------------------------------------------------------
# Helper HTTP
# ---------------------------------------------------------------------------

_HEADERS = {"User-Agent": "UrbanSignalEngine/1.0 (https://urban-signal-engine.onrender.com)"}

async def safe_get(client: httpx.AsyncClient, url: str, params: dict = None) -> Optional[dict]:
    for attempt in range(2):
        try:
            r = await client.get(url, params=params, timeout=12.0, headers=_HEADERS)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            log.warning(f"API call failed [{url}] (attempt {attempt + 1}/2): {type(e).__name__}: {e}")
    return None

# Correction cosinus à la latitude de Lyon (~45.76°) pour que
# 1° de longitude pèse autant que 1° de latitude en distance réelle.
_COS_LAT_LYON = math.cos(math.radians(45.76))

# Rayon max d'assignation : 2 km ≈ 0.018° lat → d² = 0.000324
# Au-delà, le point est hors périmètre urbain (filtre Bron, A43, etc.)
_MAX_ZONE_D2 = (2.0 / 111.1) ** 2


def _nearest_zone(lat: float, lon: float) -> Optional[str]:
    best, best_d = None, float("inf")
    for zone, (zlat, zlon) in ZONE_CENTROIDS.items():
        d = (lat - zlat) ** 2 + ((lon - zlon) * _COS_LAT_LYON) ** 2
        if d < best_d:
            best_d, best = d, zone
    if best_d > _MAX_ZONE_D2:
        return None
    return best


def _zone_weights_raw(lat: float, lon: float) -> Dict[str, float]:
    """Poids gaussien brut (non normalisé) par zone dans le rayon _MAX_ZONE_D2."""
    _2sigma2 = 2.0 * MULTIZONE_SIGMA_KM ** 2
    raw: Dict[str, float] = {}
    for zone, (zlat, zlon) in ZONE_CENTROIDS.items():
        d2 = (lat - zlat) ** 2 + ((lon - zlon) * _COS_LAT_LYON) ** 2
        if d2 > _MAX_ZONE_D2:
            continue
        d_km = math.sqrt(d2) * 111.1
        w = math.exp(-(d_km ** 2) / _2sigma2)
        if w >= MULTIZONE_MIN_WEIGHT:
            raw[zone] = w
    return raw


def _zone_weights(lat: float, lon: float) -> Dict[str, float]:
    """Poids gaussien normalisé sum=1 (ADR-019). Pour trafic/vélo'v :
    un segment se DISTRIBUE entre zones."""
    raw = _zone_weights_raw(lat, lon)
    if not raw:
        return {}
    total = sum(raw.values())
    return {z: round(w / total, 4) for z, w in raw.items()}


def _zone_weights_radiate(lat: float, lon: float) -> Dict[str, float]:
    """Poids gaussien normalisé max=1 (ADR-019). Pour incidents :
    un événement RAYONNE vers les zones voisines sans perdre d'intensité."""
    raw = _zone_weights_raw(lat, lon)
    if not raw:
        return {}
    max_w = max(raw.values())
    return {z: round(w / max_w, 4) for z, w in raw.items()}


# ---------------------------------------------------------------------------
# Météo — Open-Meteo
# ---------------------------------------------------------------------------

def _wmo_contribution(wmo: int) -> float:
    """Lookup granulaire WMO → contribution score (ADR-017).
    Utilise une correspondance exacte ; retourne 0.0 pour les codes non listés."""
    return WEATHER_WMO_SCORE.get(wmo, 0.0)


def _weather_score_from_values(precip: float, wind: float, wmo: int) -> float:
    """Score météo synthétique [0, WEATHER_SCORE_MAX] depuis les valeurs Open-Meteo.

    Composition :
    - précipitations : min(precip / WEATHER_PRECIP_DIVISOR, 1.5)
    - vent fort      : +0.5 si wind > WEATHER_WIND_THRESHOLD
    - code WMO       : lookup granulaire via WEATHER_WMO_SCORE (ADR-017)
    """
    score = 0.0
    score += min(precip / WEATHER_PRECIP_DIVISOR, 1.5)
    score += 0.5 if wind > WEATHER_WIND_THRESHOLD else 0.0
    score += _wmo_contribution(wmo)
    return min(score, WEATHER_SCORE_MAX)


_weather_last_known: dict = {"score": None, "ts": None}
_WEATHER_STALE_MAX = 7200  # 2h — au-delà, on préfère 0.0 à une valeur trop vieille

async def fetch_weather() -> Dict[str, float]:
    async with httpx.AsyncClient() as client:
        data = await safe_get(client, APIS.WEATHER_URL)
    if not data:
        cached = _weather_last_known["score"]
        if cached is not None:
            age = (datetime.datetime.now(datetime.timezone.utc) - _weather_last_known["ts"]).total_seconds()
            if age < _WEATHER_STALE_MAX:
                log.warning("[weather] Open-Meteo inaccessible — last known score=%.3f (age=%.0fs)", cached, age)
                return {z: cached for z in ZONE_CENTROIDS}
        log.error("[weather] Open-Meteo inaccessible — fallback neutre 0.0")
        return {z: 0.0 for z in ZONE_CENTROIDS}
    cur    = data.get("current", {})
    precip = float(cur.get("precipitation", 0))
    wind   = float(cur.get("wind_speed_10m", 0))
    wmo    = int(cur.get("weather_code", 0))
    score  = _weather_score_from_values(precip, wind, wmo)
    _weather_last_known["score"] = round(score, 3)
    _weather_last_known["ts"]    = datetime.datetime.now(datetime.timezone.utc)
    return {z: round(score, 3) for z in ZONE_CENTROIDS}

# ---------------------------------------------------------------------------
# Météo forecast horaire — Open-Meteo (prévision 48h, gratuit)
# ---------------------------------------------------------------------------

_weather_forecast_cache: dict = {"data": None, "ts": None}
_WEATHER_FORECAST_TTL = 1800  # 30 min — les prévisions horaires ne changent pas vite


async def fetch_weather_forecast() -> Dict[str, float]:
    """
    Récupère le forecast météo horaire Open-Meteo (48h).
    Retourne un dict {iso_hour_str: weather_score} indexé par heure ISO arrondie.
    Ex: {"2026-03-17T18:00": 0.8, "2026-03-17T19:00": 0.0, ...}
    Cache 30 min — les prévisions horaires changent peu.
    """
    now = datetime.datetime.now(datetime.timezone.utc)

    # Check cache
    if (
        _weather_forecast_cache["data"] is not None
        and _weather_forecast_cache["ts"] is not None
        and (now - _weather_forecast_cache["ts"]).total_seconds() < _WEATHER_FORECAST_TTL
    ):
        return _weather_forecast_cache["data"]

    async with httpx.AsyncClient() as client:
        data = await safe_get(client, APIS.WEATHER_FORECAST_URL)

    if not data or "hourly" not in data:
        log.warning("[weather-forecast] Pas de données → vide")
        return {}

    hourly = data["hourly"]
    times  = hourly.get("time", [])
    precip = hourly.get("precipitation", [])
    wind   = hourly.get("wind_speed_10m", [])
    wmo    = hourly.get("weather_code", [])

    result: Dict[str, float] = {}
    for i, t in enumerate(times):
        p = float(precip[i]) if i < len(precip) and precip[i] is not None else 0.0
        w = float(wind[i])   if i < len(wind) and wind[i] is not None else 0.0
        c = int(wmo[i])      if i < len(wmo) and wmo[i] is not None else 0
        result[t] = round(_weather_score_from_values(p, w, c), 3)

    _weather_forecast_cache["data"] = result
    _weather_forecast_cache["ts"] = now
    log.info("[weather-forecast] %d heures de prévision chargées", len(result))
    return result


# ---------------------------------------------------------------------------
# Trafic — Grand Lyon Criter (données officielles, sans quota)
# ---------------------------------------------------------------------------

_TRAFFIC_NEUTRAL = 1.0    # Criter V=fluide → z≈0 quand données indisponibles
_PASSAGES_NEUTRAL = 0.5   # Neutre quand données TCL indisponibles (0=plein service, 1=aucun bus)
_CONGESTION_BOOST = 1.5   # Multiplicateur fraction segments congestionnés (O+R+N)

async def fetch_traffic() -> Dict[str, float]:
    """
    Récupère l'état du trafic en temps réel depuis le système Criter
    de la Métropole de Lyon (WFS Grand Lyon, sans clé API, sans quota).
    Retourne un ratio de congestion par zone [0.5–3.0].
    V=1.0 (fluide), O=2.0 (dense), R=2.8 (chargé), N=3.0 (coupée).
    """
    neutral = {z: _TRAFFIC_NEUTRAL for z in ZONE_CENTROIDS}

    async with httpx.AsyncClient() as client:
        try:
            r = await client.get(
                APIS.CRITER_WFS_URL,
                headers=_gl_headers(),
                timeout=15.0,
            )
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            log.warning(f"[criter-traffic] Échec appel WFS: {e} → neutre")
            return neutral

    features = data.get("features", [])
    if not features:
        log.warning("[criter-traffic] Aucun tronçon reçu → neutre")
        return neutral

    # Accumuler les ratios par zone (ignorer G=gris et *=inconnu)
    zone_ratios: Dict[str, list] = {z: [] for z in ZONE_CENTROIDS}

    for feat in features:
        props = feat.get("properties", {})
        etat  = props.get("etat", "")
        ratio = CRITER_ETAT_TO_RATIO.get(etat)
        if ratio is None:
            continue  # G / * → pas de mesure, ignorer

        geom   = feat.get("geometry", {})
        coords = geom.get("coordinates", [])
        if not coords:
            continue

        # Midpoint du tronçon (LineString [lon, lat])
        mid      = coords[len(coords) // 2]
        lat, lon = float(mid[1]), float(mid[0])
        if MULTIZONE_ENABLED:
            weights = _zone_weights(lat, lon)
            for z, w in weights.items():
                zone_ratios[z].append((ratio, w))
        else:
            zone = _nearest_zone(lat, lon)
            if zone:
                zone_ratios[zone].append((ratio, 1.0))

    result: Dict[str, float] = {}
    for zone, ratios in zone_ratios.items():
        if ratios:
            total_w = sum(w for _, w in ratios)
            avg = sum(r * w for r, w in ratios) / total_w
            n_congested = sum(w for r, w in ratios if r >= 2.0)  # O + R + N
            frac = n_congested / total_w
            boosted = avg + frac * _CONGESTION_BOOST
            result[zone] = round(max(0.5, min(3.0, boosted)), 3)
            log.info(
                f"[criter-traffic] zone={zone} segments={len(ratios)}"
                f" ratio_moy={avg:.3f} congestion={frac:.0%} final={result[zone]}"
            )
        else:
            result[zone] = _TRAFFIC_NEUTRAL
            log.debug(f"[criter-traffic] zone={zone} → aucun segment actif, neutre")

    return result

# ---------------------------------------------------------------------------
# Incidents — Grand Lyon Criter (pvoevenement, sans quota)
# ---------------------------------------------------------------------------

# Poids par type d'événement Criter
_CRITER_EVENT_WEIGHT = {
    # NetworkManagement
    "roadClosed":       2.0,  # route fermée — impact fort
    # Activities (disturbanceactivitytype)
    "march":            1.2,  # manifestation
    "demonstration":    1.2,
    "publicEvent":      0.8,  # événement public
    "sportEvent":       0.8,
    "other":            0.5,
}
_CRITER_EVENT_WEIGHT_DEFAULT_NETWORK   = 1.0   # NetworkManagement sans sous-type connu
_CRITER_EVENT_WEIGHT_DEFAULT_ACTIVITY  = 0.3   # Activities sans sous-type


def _structural_decay(hour: float) -> float:
    """Atténue les événements structurels (travaux, chantiers) en heures creuses.
    Reflète le volume de trafic réellement impacté par les travaux."""
    if 7.0 <= hour <= 9.5:
        return 1.0       # rush matin
    if 16.0 <= hour <= 19.0:
        return 1.0       # rush soir
    if 9.5 <= hour < 16.0:
        return 0.7       # journée — flux continu mais dilué
    if 19.0 < hour <= 21.0:
        return 0.5       # soirée
    if 21.0 < hour <= 23.0:
        return 0.3       # soirée tardive
    if 5.0 <= hour < 7.0:
        return 0.5       # réveil progressif
    return 0.10           # nuit (23h-5h)


def _is_structural_event(props: dict) -> bool:
    """True si l'événement est planifié/structurel (travaux, chantiers, fermetures)."""
    return props.get("type", "") == "NetworkManagement"


def _criter_event_weight(props: dict, decay: float = 1.0) -> float:
    evt_type = props.get("type", "")
    if evt_type == "NetworkManagement":
        sub = props.get("networkmanagementtype") or ""
        base = _CRITER_EVENT_WEIGHT.get(sub, _CRITER_EVENT_WEIGHT_DEFAULT_NETWORK)
        return base * decay
    if evt_type == "Activities":
        sub = props.get("disturbanceactivitytype") or ""
        return _CRITER_EVENT_WEIGHT.get(sub, _CRITER_EVENT_WEIGHT_DEFAULT_ACTIVITY)
    return 0.3


def _multipoint_centroid(coords: list) -> Optional[tuple]:
    """Retourne (lat, lon) depuis coordonnées MultiPoint ou Point."""
    if not coords:
        return None
    # MultiPoint : liste de [lon, lat]
    if isinstance(coords[0], list):
        lons = [c[0] for c in coords]
        lats = [c[1] for c in coords]
        return sum(lats) / len(lats), sum(lons) / len(lons)
    # Point simple : [lon, lat]
    return float(coords[1]), float(coords[0])


_INCIDENT_HORIZONS = [0, 30, 60, 120, 360, 720, 1440]   # minutes (0 = maintenant, +6h, +12h, +24h)


def _is_event_active_at(props: dict, target: datetime.datetime) -> bool:
    """Retourne True si l'événement est actif à l'instant `target`."""
    from zoneinfo import ZoneInfo
    _PARIS = ZoneInfo("Europe/Paris")
    start_s = props.get("starttime")
    end_s   = props.get("endtime")
    if not start_s or not end_s:
        return True  # pas d'horaire → considéré actif
    try:
        start = datetime.datetime.fromisoformat(start_s)
        end   = datetime.datetime.fromisoformat(end_s)
        # Criter WFS renvoie des dates naive en heure locale Paris
        if start.tzinfo is None:
            start = start.replace(tzinfo=_PARIS)
        if end.tzinfo is None:
            end = end.replace(tzinfo=_PARIS)
        return start <= target <= end
    except (ValueError, TypeError):
        return True  # échec parsing → inclure par défaut


def _zone_score_from_weights(weights: list, fallback_mu: float = 0.0) -> float:
    if not weights:
        # Aucun incident remonté → baseline zone-specific (pas 1.70 global)
        return fallback_mu
    avg     = sum(weights) / len(weights)
    # Densité logarithmique : amortit la fragmentation TomTom
    # 1 incident → ×1.0, 3 → ×1.33, 5 → ×1.48, 10 → ×1.69, 20 → ×1.90
    density = 1 + 0.3 * math.log(1 + len(weights))
    return round(min(avg * density, 3.0), 3)


def _build_event_display(props: dict, now, paris_tz) -> dict:
    """Construit l'objet d'affichage frontend pour un événement Criter."""
    evt_type = (
        props.get("networkmanagementtype")
        or props.get("disturbanceactivitytype")
        or props.get("type", "")
    )
    comment = props.get("publiccomment") or ""
    parts   = [p.strip() for p in comment.split("|")]
    label   = parts[0][:70] if parts else ""
    detail  = parts[1][:80] if len(parts) > 1 else ""

    direction_lbl = {
        "bothWays": "", "inbound": "→ centre", "outbound": "→ périphérie",
    }.get(props.get("direction", ""), "")

    end_s     = props.get("endtime", "")
    ends_soon = False
    end_fmt   = ""
    try:
        end_dt = datetime.datetime.fromisoformat(end_s)
        if end_dt.tzinfo is None:
            end_dt = end_dt.replace(tzinfo=paris_tz)
        end_fmt   = end_dt.astimezone(paris_tz).strftime("%-d %b %H:%M")
        ends_soon = now <= end_dt <= now + datetime.timedelta(hours=2)
    except (ValueError, TypeError):
        pass

    now_local_hour = now.astimezone(paris_tz).hour + now.astimezone(paris_tz).minute / 60.0
    return {
        "type":      evt_type,
        "label":     label,
        "detail":    detail,
        "direction": direction_lbl,
        "end":       end_fmt,
        "ends_soon": ends_soon,
        "weight":    _criter_event_weight(
            props,
            decay=_structural_decay(now_local_hour) if _is_structural_event(props) else 1.0,
        ),
    }


async def fetch_incidents() -> tuple:
    """
    Récupère les événements perturbateurs actifs depuis Criter/Grand Lyon WFS.
    Single pass : accumule scores par horizon ET détails d'affichage simultanément.
    Retourne :
        current  : Dict[str, float]               — score incident par zone maintenant
        schedule : Dict[str, Dict[int, float]]    — score par zone à t+30/60/120/360/720/1440 min
        events   : Dict[str, List[dict]]           — détails événements actifs par zone
        labels   : Dict[str, Dict[str, str]]       — top incident label par zone
    """
    neutral_c  = {z: _effective_baseline(z)["incident"]["mu"] for z in ZONE_CENTROIDS}
    neutral_s  = {z: {h: _effective_baseline(z)["incident"]["mu"] for h in _INCIDENT_HORIZONS if h > 0} for z in ZONE_CENTROIDS}
    neutral_ev = {z: [] for z in ZONE_CENTROIDS}
    neutral_lb = {}

    async with httpx.AsyncClient() as client:
        try:
            r = await client.get(
                APIS.CRITER_EVENTS_URL,
                headers=_gl_headers(),
                timeout=15.0,
            )
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            log.warning(f"[criter-incidents] Échec appel WFS: {e} → neutre")
            return neutral_c, neutral_s, neutral_ev, neutral_lb

    features = data.get("features", [])
    if not features:
        log.info("[criter-incidents] Aucun événement actif")
        return neutral_c, neutral_s, neutral_ev, neutral_lb

    now = datetime.datetime.now(datetime.timezone.utc)

    from zoneinfo import ZoneInfo
    _PARIS = ZoneInfo("Europe/Paris")

    # Accumuler scores ET display en un seul pass
    h_zone_weights: Dict[int, Dict[str, list]] = {
        h: {z: [] for z in ZONE_CENTROIDS} for h in _INCIDENT_HORIZONS
    }
    h_zone_seen: Dict[int, Dict[str, set]] = {
        h: {z: set() for z in ZONE_CENTROIDS} for h in _INCIDENT_HORIZONS
    }
    events_by_zone: Dict[str, list] = {z: [] for z in ZONE_CENTROIDS}

    for feat in features:
        props  = feat.get("properties", {})
        geom   = feat.get("geometry", {})
        coords = geom.get("coordinates", [])
        point  = _multipoint_centroid(coords)
        if not point:
            continue
        lat, lon = point
        if MULTIZONE_ENABLED:
            zones_map = _zone_weights_radiate(lat, lon)
            if not zones_map:
                continue
        else:
            z_single = _nearest_zone(lat, lon)
            if not z_single:
                continue
            zones_map = {z_single: 1.0}
        structural = _is_structural_event(props)
        criter_id  = props.get("id")

        # Scores par horizon — distribuer sur toutes les zones contribuantes
        for h in _INCIDENT_HORIZONS:
            target = now + datetime.timedelta(minutes=h)
            if _is_event_active_at(props, target):
                local_hour = target.astimezone(_PARIS).hour + target.astimezone(_PARIS).minute / 60.0
                decay = _structural_decay(local_hour) if structural else 1.0
                weight = _criter_event_weight(props, decay=decay)
                for zone, zw in zones_map.items():
                    if criter_id and criter_id in h_zone_seen[h][zone]:
                        continue
                    h_zone_weights[h][zone].append(weight * zw)
                    if criter_id:
                        h_zone_seen[h][zone].add(criter_id)

        # Display (h=0 uniquement) — zone principale seulement (éviter doublons UI)
        if _is_event_active_at(props, now):
            primary_zone = max(zones_map, key=zones_map.get)
            events_by_zone[primary_zone].append(_build_event_display(props, now, _PARIS))

    # Merge TomTom incidents
    _TT_DECAY: Dict[int, Dict[int, float]] = {
        1:  {0: 1.0, 30: 0.50, 60: 0.20, 120: 0.0},   # Accident
        6:  {0: 1.0, 30: 0.70, 60: 0.40, 120: 0.0},   # Bouchon
        7:  {0: 1.0, 30: 0.90, 60: 0.80, 120: 0.5},   # Voie fermée
        8:  {0: 1.0, 30: 0.90, 60: 0.80, 120: 0.5},   # Route fermée
        9:  {0: 1.0, 30: 1.00, 60: 1.00, 120: 1.0},   # Travaux
        14: {0: 1.0, 30: 0.50, 60: 0.10, 120: 0.0},   # Véhicule en panne
    }
    _TT_DECAY_DEFAULT = {0: 1.0, 30: 0.60, 60: 0.30, 120: 0.0}
    _TT_STRUCTURAL_CATS = {7, 8, 9}

    for tt in await _fetch_tomtom_incidents_cached():
        z        = tt["zone"]
        w        = tt["weight"]
        icon_cat = tt.get("icon_cat", 0)
        is_struct = icon_cat in _TT_STRUCTURAL_CATS
        decay_h  = _TT_DECAY.get(icon_cat, _TT_DECAY_DEFAULT)
        for h in _INCIDENT_HORIZONS:
            factor = decay_h.get(h, 0.0)
            if factor > 0:
                target_h = now + datetime.timedelta(minutes=h)
                local_hour = target_h.astimezone(_PARIS).hour + target_h.astimezone(_PARIS).minute / 60.0
                sd = _structural_decay(local_hour) if is_struct else 1.0
                h_zone_weights[h][z].append(round(w * factor * sd, 3))

        # TomTom display
        events_by_zone[z].append({
            "type":      tt["evt_type"],
            "label":     tt["label"],
            "detail":    tt.get("detail", ""),
            "direction": tt.get("direction", ""),
            "delay_min": tt.get("delay_min", 0),
            "end":       "",
            "ends_soon": False,
            "weight":    tt["weight"],
            "source":    "tomtom",
        })

    # Scores
    current: Dict[str, float] = {}
    for z in ZONE_CENTROIDS:
        mu_inc = _effective_baseline(z)["incident"]["mu"]
        current[z] = _zone_score_from_weights(h_zone_weights[0][z], fallback_mu=mu_inc)
        log.info(f"[criter-incidents] zone={z} count={len(h_zone_weights[0][z])} score={current[z]}")

    schedule: Dict[str, Dict[int, float]] = {
        z: {h: _zone_score_from_weights(h_zone_weights[h][z], fallback_mu=_effective_baseline(z)["incident"]["mu"]) for h in _INCIDENT_HORIZONS if h > 0}
        for z in ZONE_CENTROIDS
    }

    # Dédupliquer par (type, label) pour éviter les doublons de segments
    for z in ZONE_CENTROIDS:
        seen_labels: set = set()
        deduped = []
        for ev in sorted(events_by_zone[z], key=lambda e: -e["weight"]):
            key = (ev["type"], ev["label"][:40])
            if key not in seen_labels:
                seen_labels.add(key)
                deduped.append(ev)
        events_by_zone[z] = deduped

    # Extract top incident label per zone (highest weight, for persistence)
    top_labels: Dict[str, Dict[str, str]] = {}
    for z in ZONE_CENTROIDS:
        evts = events_by_zone[z]
        if evts:
            top = evts[0]  # already sorted by weight desc after dedup
            evt_type = top.get("type", "")
            source = top.get("source", "criter")
            label = top.get("label", "")[:100]
            top_labels[z] = {"label": label, "type": f"{source}/{evt_type}" if source == "tomtom" else evt_type}

    return current, schedule, events_by_zone, top_labels

# ---------------------------------------------------------------------------
# Incidents TomTom — cache 30 min (budget : ≤2 500 req/mois)
# ---------------------------------------------------------------------------

_TOMTOM_API_KEY = os.getenv("TOMTOM_API_KEY", "")
_TOMTOM_TTL     = 1800   # 30 min → ≈ 1 440 appels/mois
_TOMTOM_BBOX    = "4.77,45.70,4.93,45.82"   # Lyon intra-muros

_tomtom_cache: dict = {"data": None, "fetched_at": None}

# Poids par iconCategory TomTom
_TOMTOM_BASE_WEIGHT: Dict[int, float] = {
    1:  1.5,   # Accident
    6:  0.8,   # Bouchon
    7:  1.2,   # Voie fermée
    8:  2.0,   # Route fermée
    9:  0.7,   # Travaux
    14: 1.0,   # Véhicule en panne
}
_TOMTOM_CATEGORY_TYPE: Dict[int, str] = {
    1:  "roadClosed",
    6:  "other",
    7:  "roadClosed",
    8:  "roadClosed",
    9:  "NetworkManagement",
    14: "other",
}
_TOMTOM_CATEGORY_LABEL: Dict[int, str] = {
    1:  "Accident",
    6:  "Bouchon",
    7:  "Voie fermée",
    8:  "Route fermée",
    9:  "Travaux",
    14: "Véhicule en panne",
}


def _tomtom_weight(icon_cat: int, magnitude: int, delay_s: int = 0) -> float:
    base = _TOMTOM_BASE_WEIGHT.get(icon_cat, 0.5)
    # magnitude : 1=mineur 2=modéré 3=majeur → +0 / +15% / +30%
    mult = {1: 1.0, 2: 1.15, 3: 1.30}.get(magnitude, 1.0)
    # Pondération par le retard réel — incidents à 0 delay pèsent 55 % max
    # (route fermée sans delay = impact réel mais non mesuré par TomTom)
    delay_min = int(delay_s) / 60 if delay_s else 0
    delay_factor = max(0.55, min(delay_min / 5.0, 1.0))
    return round(base * mult * delay_factor, 2)


_CLUSTER_RADIUS_DEG = 200.0 / 111_100  # 200 m en degrés latitude


def _cluster_tomtom_incidents(incidents: list) -> list:
    """Regroupe les incidents TomTom à <200 m dans la même zone/catégorie.

    Pour chaque cluster, on garde l'incident de poids max (représentant)
    et on cumule le delay.  Ça élimine la fragmentation multi-segments
    des chantiers et fermetures TomTom.
    """
    if not incidents:
        return incidents

    from collections import defaultdict
    by_zone_cat: Dict[tuple, list] = defaultdict(list)
    for inc in incidents:
        key = (inc["zone"], inc["evt_type"])
        by_zone_cat[key].append(inc)

    result = []
    r2 = _CLUSTER_RADIUS_DEG ** 2
    cos2 = _COS_LAT_LYON ** 2

    for _key, group in by_zone_cat.items():
        clusters: list[list] = []
        for inc in sorted(group, key=lambda x: -x["weight"]):
            merged = False
            for cluster in clusters:
                ref = cluster[0]
                d2 = (inc["lat"] - ref["lat"]) ** 2 + ((inc["lon"] - ref["lon"]) ** 2) * cos2
                if d2 <= r2:
                    cluster.append(inc)
                    merged = True
                    break
            if not merged:
                clusters.append([inc])

        for cluster in clusters:
            rep = cluster[0]  # poids max (déjà trié desc)
            # Cumuler le delay pour refléter l'impact total du cluster
            total_delay = sum(c.get("delay_min", 0) for c in cluster)
            rep["delay_min"] = total_delay
            result.append(rep)

    log.info(f"[tomtom-cluster] {len(incidents)} bruts → {len(result)} après clustering 200m")
    return result


async def _fetch_tomtom_incidents_cached() -> list:
    """
    Retourne une liste de dicts {zone, weight, label, evt_type}.
    Rafraîchit depuis l'API TomTom au plus toutes les 30 min.
    """
    if not _TOMTOM_API_KEY:
        return []

    now = datetime.datetime.now(datetime.timezone.utc)
    fetched = _tomtom_cache["fetched_at"]
    if fetched and (now - fetched).total_seconds() < _TOMTOM_TTL:
        return _tomtom_cache["data"] or []

    url = "https://api.tomtom.com/traffic/services/5/incidentDetails"
    params = {
        "key":              _TOMTOM_API_KEY,
        "bbox":             _TOMTOM_BBOX,
        "fields":           "{incidents{geometry{coordinates},properties{iconCategory,magnitudeOfDelay,events{description},from,to,delay,length}}}",
        "language":         "fr-FR",
        "categoryFilter":   "1,6,7,8,9,14",
        "timeValidityFilter": "present",
    }
    try:
        async with httpx.AsyncClient(timeout=12) as client:
            r = await client.get(url, params=params)
            r.raise_for_status()
            raw = r.json()
    except Exception as e:
        log.warning(f"[tomtom-incidents] Échec: {e} → cache inchangé")
        return _tomtom_cache["data"] or []

    incidents = raw.get("incidents", [])
    result = []
    for inc in incidents:
        props  = inc.get("properties", {})
        coords = inc.get("geometry", {}).get("coordinates")
        if not coords:
            continue
        # Coordonnées : [lon, lat] ou [[lon, lat], ...]
        if isinstance(coords[0], list):
            lon, lat = coords[0][0], coords[0][1]
        else:
            lon, lat = coords[0], coords[1]
        icon_cat  = int(props.get("iconCategory", 0))
        magnitude = int(props.get("magnitudeOfDelay", 1))
        delay_s   = props.get("delay") or 0
        weight    = _tomtom_weight(icon_cat, magnitude, delay_s=delay_s)
        if weight <= 0:
            continue

        desc_list = props.get("events", [])
        desc      = desc_list[0].get("description", "") if desc_list else ""
        from_s    = props.get("from", "")
        to_s      = props.get("to", "")
        from_to   = f"{from_s} → {to_s}".strip(" →") if (from_s or to_s) else ""
        label     = (desc or _TOMTOM_CATEGORY_LABEL.get(icon_cat, "Incident"))[:70]
        detail    = from_to[:80]

        delay_min = round(int(delay_s) / 60) if delay_s else 0

        if MULTIZONE_ENABLED:
            zones_map = _zone_weights_radiate(float(lat), float(lon))
            if not zones_map:
                continue
            for z, zw in zones_map.items():
                result.append({
                    "zone":      z,
                    "weight":    weight * zw,
                    "label":     label,
                    "detail":    detail,
                    "direction": "",
                    "delay_min": delay_min,
                    "evt_type":  _TOMTOM_CATEGORY_TYPE.get(icon_cat, "other"),
                    "icon_cat":  icon_cat,
                    "lat":       float(lat),
                    "lon":       float(lon),
                })
        else:
            zone = _nearest_zone(float(lat), float(lon))
            if not zone:
                continue
            result.append({
                "zone":      zone,
                "weight":    weight,
                "label":     label,
                "detail":    detail,
                "direction": "",
                "delay_min": delay_min,
                "evt_type":  _TOMTOM_CATEGORY_TYPE.get(icon_cat, "other"),
                "icon_cat":  icon_cat,
                "lat":       float(lat),
                "lon":       float(lon),
            })

    # ── Clustering géographique : regrouper incidents TomTom <200m ──
    result = _cluster_tomtom_incidents(result)

    log.info(f"[tomtom-incidents] {len(result)} incidents après clustering (1 appel API)")
    _tomtom_cache["data"]       = result
    _tomtom_cache["fetched_at"] = now
    return result

# ---------------------------------------------------------------------------
# Transport — Grand Lyon Basic Auth
# ---------------------------------------------------------------------------

GL_LOGIN    = os.getenv("GRANDLYON_LOGIN")
GL_PASSWORD = os.getenv("GRANDLYON_PASSWORD")

def _gl_headers() -> dict:
    token = base64.b64encode(f"{GL_LOGIN}:{GL_PASSWORD}".encode()).decode()
    return {"Authorization": f"Basic {token}"}

PARC_ZONE: Dict[str, str] = {
    "MERP": "montchat",  "BON":  "villette",  "SOI":  "villette",
    "VAI1": "villette",  "VAI2": "villette",  "GOR":  "villette",
    "CUI":  "croix-rousse", "PAR": "gerland", "BELA": "gerland",
    "HFVE": "gerland",   "ALP":  "gerland",   "MEYZ": "villette",
    "MEYG": "villette",  "MEYP": "villette",  "DECG": "villette",
    "DECC": "villette",
}

# Mapping arrêt TCL → zone, généré depuis les APIs tclarret + tclpassagearret
# en croisant les arrêts actifs avec les centroïdes de zone (rayon ≤ 2km).
ARRET_ZONE: Dict[int, str] = {
    # brotteaux (3 arrêts, ex: Collège B. Tavernier, Cité Inter)
    547: "brotteaux", 817: "brotteaux", 35775: "brotteaux",
    # confluence (2 arrêts, ex: Hôtel Région Montrochet)
    34874: "confluence", 46179: "confluence",
    # croix-rousse (10 arrêts, ex: Hénon, Croix-Rousse, Hôtel de Ville)
    1153: "croix-rousse", 2369: "croix-rousse", 3503: "croix-rousse",
    11058: "croix-rousse", 11544: "croix-rousse", 30156: "croix-rousse",
    30159: "croix-rousse", 33645: "croix-rousse", 42214: "croix-rousse",
    47904: "croix-rousse",
    # fourviere (15 arrêts, ex: Gorge de Loup, Vaise, Saint-Just)
    1061: "fourviere", 2537: "fourviere", 2828: "fourviere",
    3434: "fourviere", 12045: "fourviere", 12273: "fourviere",
    21420: "fourviere", 26070: "fourviere", 30210: "fourviere",
    30214: "fourviere", 30506: "fourviere", 30575: "fourviere",
    32682: "fourviere", 46264: "fourviere", 46710: "fourviere",
    # gerland (4 arrêts, ex: Debourg)
    46160: "gerland", 46190: "gerland", 46310: "gerland", 47287: "gerland",
    # guillotiere (4 arrêts, ex: Jean Macé, Saxe-Gambetta)
    1248: "guillotiere", 1252: "guillotiere", 32482: "guillotiere",
    50403: "guillotiere",
    # montchat (2 arrêts, ex: Villeurbanne Centre, Manufacture Montluc)
    43062: "montchat", 47084: "montchat",
    # part-dieu (11 arrêts, ex: Part-Dieu, Charpennes)
    2213: "part-dieu", 11810: "part-dieu", 30472: "part-dieu",
    34350: "part-dieu", 35834: "part-dieu", 41194: "part-dieu",
    44038: "part-dieu", 45848: "part-dieu", 46642: "part-dieu",
    46644: "part-dieu", 50140: "part-dieu",
    # perrache (7 arrêts, ex: Perrache, Claudius Collonge)
    542: "perrache", 23467: "perrache", 30459: "perrache",
    33779: "perrache", 33782: "perrache", 50420: "perrache",
    50421: "perrache",
    # presquile (9 arrêts, ex: Cordeliers, Pont Guillotière)
    599: "presquile", 17393: "presquile", 30041: "presquile",
    43226: "presquile", 48351: "presquile", 48375: "presquile",
    48376: "presquile", 50208: "presquile", 50210: "presquile",
    # vieux-lyon (4 arrêts, ex: Gare Saint-Paul, Vieux Lyon)
    30000: "vieux-lyon", 30211: "vieux-lyon", 30215: "vieux-lyon",
    50423: "vieux-lyon",
    # villette (10 arrêts, ex: Grange Blanche, Mermoz-Pinel)
    1087: "villette", 1089: "villette", 1095: "villette",
    10185: "villette", 32962: "villette", 45271: "villette",
    46422: "villette", 48370: "villette", 50260: "villette",
    50383: "villette",
}

PARCRELAIS_URL = (
    "https://data.grandlyon.com/fr/datapusher/ws/rdata"
    "/tcl_sytral.tclparcrelaistr/all.json?maxfeatures=-1&start=1"
)
PASSAGES_URL = (
    "https://data.grandlyon.com/fr/datapusher/ws/rdata"
    "/tcl_sytral.tclpassagearret/all.json?maxfeatures=-1&start=1"
)
VELOV_URL = (
    "https://data.grandlyon.com/fr/datapusher/ws/rdata"
    "/jcd_jcdecaux.jcdvelov/all.json?maxfeatures=-1&start=1"
)
SEUIL_PASSAGES_PAR_STOP = 40   # ~40 passages par arrêt en 15 min = service normal en pointe

# Pré-calculer le nombre d'arrêts par zone (pour normalisation passages)
_STOPS_PER_ZONE: Dict[str, int] = {}
for _sid, _zid in ARRET_ZONE.items():
    _STOPS_PER_ZONE[_zid] = _STOPS_PER_ZONE.get(_zid, 0) + 1


def _parse_delai(raw: str) -> Optional[float]:
    raw = raw.strip()
    if raw.lower() in ("proche", "imminent"):
        return 0.5  # bus imminent → compte comme < 1 min
    m = re.match(r"^(\d+)\s*min$", raw)
    if m:
        return float(m.group(1))
    m = re.match(r"^(\d{1,2})h(\d{2})$", raw)
    if m:
        now    = datetime.datetime.now()
        target = now.replace(hour=int(m.group(1)), minute=int(m.group(2)), second=0)
        if target < now:
            target += datetime.timedelta(days=1)
        return (target - now).total_seconds() / 60.0
    return None

async def _fetch_parcrelais() -> Dict[str, float]:
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(PARCRELAIS_URL, headers=_gl_headers())
        r.raise_for_status()
        data = r.json()
    zone_tauxs: Dict[str, list] = {}
    for item in data.get("values", []):
        pid      = item.get("id", "")
        capacite = int(item.get("capacite") or 0)
        dispo    = int(item.get("nb_tot_place_dispo") or 0)
        zone     = PARC_ZONE.get(pid)
        if not zone or capacite <= 0:
            continue
        zone_tauxs.setdefault(zone, []).append(1.0 - (dispo / capacite))
    return {z: sum(v) / len(v) for z, v in zone_tauxs.items()}

async def _fetch_passages() -> Dict[str, float]:
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.get(PASSAGES_URL, headers=_gl_headers())
        r.raise_for_status()
        data = r.json()
    zone_count: Dict[str, int] = {}
    for item in data.get("values", []):
        delai_raw = item.get("delaipassage", "")
        dest_id   = item.get("idtarretdestination")
        zone      = ARRET_ZONE.get(dest_id)
        if not zone or not delai_raw:
            continue
        delai_min = _parse_delai(str(delai_raw))
        if delai_min is not None and delai_min <= 15:
            zone_count[zone] = zone_count.get(zone, 0) + 1
    # Normaliser par nombre d'arrêts mappés dans la zone
    # avg_per_stop / seuil → 0.0 = plein de bus (normal), 1.0 = aucun bus (tension max)
    result: Dict[str, float] = {}
    for z, cnt in zone_count.items():
        n_stops = _STOPS_PER_ZONE.get(z, 1)
        avg_per_stop = cnt / n_stops
        result[z] = 1.0 - min(avg_per_stop / SEUIL_PASSAGES_PAR_STOP, 1.0)
    return result

async def _fetch_velov() -> Dict[str, float]:
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(VELOV_URL, headers=_gl_headers())
        r.raise_for_status()
        data = r.json()
    zone_tauxs: Dict[str, list] = {}
    for item in data.get("values", []):
        if item.get("status") != "OPEN":
            continue
        capacity = int(item.get("bike_stands") or 0)
        if capacity <= 0:
            continue
        bikes = int(item.get("available_bikes") or 0)
        taux  = 1.0 - (bikes / capacity)   # 0=vide (tout loué), 1=plein (rien loué)
        lat   = item.get("lat")
        lng   = item.get("lng")
        if lat is None or lng is None:
            continue
        if MULTIZONE_ENABLED:
            weights = _zone_weights(float(lat), float(lng))
            for z, w in weights.items():
                zone_tauxs.setdefault(z, []).append((taux, w))
        else:
            zone = _nearest_zone(float(lat), float(lng))
            if zone:
                zone_tauxs.setdefault(zone, []).append((taux, 1.0))
    return {
        z: round(sum(t * w for t, w in v) / sum(w for _, w in v), 4)
        for z, v in zone_tauxs.items()
    }

_PEAK_ZONES = {"part-dieu", "presquile", "perrache", "guillotiere"}

def _deterministic_fallback(zone_id: str) -> float:
    h = datetime.datetime.now().hour
    base = 0.35
    if h in range(7, 10) or h in range(17, 20):
        base = 0.75 if zone_id in _PEAK_ZONES else 0.55
    elif h in range(12, 14):
        base = 0.50
    elif h in range(0, 5):
        base = 0.10
    return base

# ---------------------------------------------------------------------------
# Agrégation
# ---------------------------------------------------------------------------

async def fetch_all_signals() -> tuple:
    """
    Retourne :
        signals            : Dict[str, Dict[str, float]]   — signaux par zone
        incident_schedule  : Dict[str, Dict[int, float]]   — incidents planifiés t+30/60/120
        incident_events    : Dict[str, List[dict]]          — détails événements actifs
        weather_forecast   : Dict[str, float]               — météo horaire prévue (48h)
    """
    weather_t, event_t, traffic_t, incident_result, weather_fc = await asyncio.gather(
        fetch_weather(),
        fetch_event_signals(),
        fetch_traffic(),
        fetch_incidents(),
        fetch_weather_forecast(),
    )
    incident_t, incident_schedule, incident_events, incident_labels = incident_result

    transport_detail: Dict[str, Dict[str, Any]] = {}
    try:
        parcrelais, passages, velov = await asyncio.gather(
            _fetch_parcrelais(), _fetch_passages(), _fetch_velov()
        )
        if not passages:
            log.warning("[transport] passages_tcl vide → probable échec API TCL, fallback neutre")
        def _transport_score(zone: str) -> float:
            return round(
                parcrelais.get(zone, 0.35) * 0.3
                + passages.get(zone, _PASSAGES_NEUTRAL)  * 0.5
                + velov.get(zone, 0.5)     * 0.2,
                4,
            )
        for z in ZONE_CENTROIDS:
            pr = round(parcrelais.get(z, 0.35), 3)
            pa = round(passages.get(z, _PASSAGES_NEUTRAL), 3)
            vl = round(velov.get(z, 0.5), 3)
            transport_detail[z] = {
                "parcrelais": pr,
                "passages_tcl": pa,
                "velov": vl,
                "score": _transport_score(z),
                "fallback": False,
            }
    except Exception as e:
        log.warning(f"[fetch_all_signals] transport fallback: {e}")
        def _transport_score(zone: str) -> float:
            return _deterministic_fallback(zone)
        for z in ZONE_CENTROIDS:
            transport_detail[z] = {
                "parcrelais": None,
                "passages_tcl": None,
                "velov": None,
                "score": _transport_score(z),
                "fallback": True,
            }

    result = {}
    for zone in ZONE_CENTROIDS:
        traffic_final = round(max(0.5, min(3.0, traffic_t.get(zone, _TRAFFIC_NEUTRAL))), 3)
        incident_val  = incident_t.get(zone, 0.0)
        event_val     = event_t.get(zone, 0.0)
        log.info(
            f"[signals] zone={zone} traffic={traffic_final} incident={incident_val} "
            f"transport={_transport_score(zone)} event={event_val}"
        )
        result[zone] = {
            "traffic":   traffic_final,
            "weather":   weather_t.get(zone, 0.5),
            "event":     event_val,
            "transport": _transport_score(zone),
            "incident":  incident_val,
        }

    if ENABLE_HISTORY:
        # Lissage EWM sur raw_signals si historique disponible
        result = {
            zone: smooth_signals(zone, signals)
            for zone, signals in result.items()
        }
        log.info("[smoothing] EWM appliqué sur %d zones.", len(result))

    return result, incident_schedule, incident_events, weather_fc, transport_detail, incident_labels