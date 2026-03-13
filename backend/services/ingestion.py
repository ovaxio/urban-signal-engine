import os
import re
import asyncio
import base64
import datetime
import logging
from typing import Dict, Optional

import httpx
from config import APIS, ENABLE_HISTORY, CRITER_ETAT_TO_RATIO
from services.events import fetch_event_signals
from services.smoothing import smooth_signals


log = logging.getLogger("ingestion")

# ---------------------------------------------------------------------------
# Centroïdes des 12 zones
# ---------------------------------------------------------------------------

ZONE_CENTROIDS = {
    "part-dieu":    (45.7602, 4.8598),
    "presquile":    (45.7558, 4.8320),
    "vieux-lyon":   (45.7622, 4.8271),
    "perrache":     (45.7488, 4.8286),
    "gerland":      (45.7283, 4.8336),
    "guillotiere":  (45.7490, 4.8460),
    "brotteaux":    (45.7660, 4.8540),
    "villette":     (45.7720, 4.8620),
    "montchat":     (45.7560, 4.8760),
    "fourviere":    (45.7622, 4.8200),
    "croix-rousse": (45.7760, 4.8320),
    "confluence":   (45.7380, 4.8170),
}

# ---------------------------------------------------------------------------
# Helper HTTP
# ---------------------------------------------------------------------------

async def safe_get(client: httpx.AsyncClient, url: str, params: dict = None) -> Optional[dict]:
    try:
        r = await client.get(url, params=params, timeout=8.0)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        log.warning(f"API call failed [{url}]: {e}")
        return None

def _nearest_zone(lat: float, lon: float) -> Optional[str]:
    best, best_d = None, float("inf")
    for zone, (zlat, zlon) in ZONE_CENTROIDS.items():
        d = (lat - zlat) ** 2 + (lon - zlon) ** 2
        if d < best_d:
            best_d, best = d, zone
    return best

# ---------------------------------------------------------------------------
# Météo — Open-Meteo
# ---------------------------------------------------------------------------

async def fetch_weather() -> Dict[str, float]:
    async with httpx.AsyncClient() as client:
        data = await safe_get(client, APIS.WEATHER_URL)
    if not data:
        return {z: 0.5 for z in ZONE_CENTROIDS}
    cur    = data.get("current", {})
    precip = float(cur.get("precipitation", 0))
    wind   = float(cur.get("wind_speed_10m", 0))
    wmo    = int(cur.get("weather_code", 0))
    score  = 0.0
    score += min(precip / 5.0, 1.5)
    score += 0.5 if wind > 50 else 0.0
    score += 1.5 if wmo >= 95 else (0.8 if wmo >= 61 else 0.0)
    return {z: round(score, 3) for z in ZONE_CENTROIDS}

# ---------------------------------------------------------------------------
# Trafic — Grand Lyon Criter (données officielles, sans quota)
# ---------------------------------------------------------------------------

_TRAFFIC_NEUTRAL = 1.30   # baseline mu Criter — z≈0 quand données indisponibles

async def fetch_traffic() -> Dict[str, float]:
    """
    Récupère l'état du trafic en temps réel depuis le système Criter
    de la Métropole de Lyon (WFS Grand Lyon, sans clé API, sans quota).
    Retourne un ratio freeFlow/current par zone, sur la même échelle
    que l'ancien signal TomTom [0.5–3.0].
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
        zone     = _nearest_zone(lat, lon)
        if zone:
            zone_ratios[zone].append(ratio)

    result: Dict[str, float] = {}
    for zone, ratios in zone_ratios.items():
        if ratios:
            avg = sum(ratios) / len(ratios)
            result[zone] = round(max(0.5, min(3.0, avg)), 3)
            log.info(f"[criter-traffic] zone={zone} segments={len(ratios)} ratio_moy={result[zone]}")
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


def _criter_event_weight(props: dict) -> float:
    evt_type = props.get("type", "")
    if evt_type == "NetworkManagement":
        sub = props.get("networkmanagementtype") or ""
        return _CRITER_EVENT_WEIGHT.get(sub, _CRITER_EVENT_WEIGHT_DEFAULT_NETWORK)
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


_INCIDENT_HORIZONS = [0, 30, 60, 120]   # minutes (0 = maintenant)


def _is_event_active_at(props: dict, target: datetime.datetime) -> bool:
    """Retourne True si l'événement est actif à l'instant `target`."""
    start_s = props.get("starttime")
    end_s   = props.get("endtime")
    if not start_s or not end_s:
        return True  # pas d'horaire → considéré actif
    try:
        start = datetime.datetime.fromisoformat(start_s)
        end   = datetime.datetime.fromisoformat(end_s)
        if start.tzinfo is None:
            start = start.replace(tzinfo=datetime.timezone.utc)
        if end.tzinfo is None:
            end = end.replace(tzinfo=datetime.timezone.utc)
        return start <= target <= end
    except (ValueError, TypeError):
        return True  # échec parsing → inclure par défaut


def _zone_score_from_weights(weights: list) -> float:
    if not weights:
        return 0.0
    avg     = sum(weights) / len(weights)
    density = 1 + 0.05 * min(len(weights), 20)
    return round(min(avg * density, 3.0), 3)


async def fetch_incidents() -> tuple:
    """
    Récupère les événements perturbateurs actifs depuis Criter/Grand Lyon WFS.
    Retourne :
        current  : Dict[str, float]               — score incident par zone maintenant
        schedule : Dict[str, Dict[int, float]]    — score par zone à t+30/60/120 min
    """
    neutral_c  = {z: 0.0 for z in ZONE_CENTROIDS}
    neutral_s  = {z: {h: 0.0 for h in [30, 60, 120]} for z in ZONE_CENTROIDS}
    neutral_ev = {z: [] for z in ZONE_CENTROIDS}

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
            return neutral_c, neutral_s, neutral_ev

    features = data.get("features", [])
    if not features:
        log.info("[criter-incidents] Aucun événement actif")
        return neutral_c, neutral_s, neutral_ev

    now = datetime.datetime.now(datetime.timezone.utc)

    # Accumuler les poids par horizon × zone
    # Déduplication par ID Criter : un même événement peut être encodé comme
    # plusieurs features (segments de route) — on ne le compte qu'une fois par zone.
    h_zone_weights: Dict[int, Dict[str, list]] = {
        h: {z: [] for z in ZONE_CENTROIDS} for h in _INCIDENT_HORIZONS
    }
    # (horizon, zone) → set d'IDs Criter déjà comptés
    h_zone_seen: Dict[int, Dict[str, set]] = {
        h: {z: set() for z in ZONE_CENTROIDS} for h in _INCIDENT_HORIZONS
    }

    for feat in features:
        props  = feat.get("properties", {})
        geom   = feat.get("geometry", {})
        coords = geom.get("coordinates", [])
        point  = _multipoint_centroid(coords)
        if not point:
            continue
        lat, lon = point
        zone = _nearest_zone(lat, lon)
        if not zone:
            continue
        weight    = _criter_event_weight(props)
        criter_id = props.get("id")   # None si absent → chaque feature compte (rétrocompat)

        for h in _INCIDENT_HORIZONS:
            target = now + datetime.timedelta(minutes=h)
            if _is_event_active_at(props, target):
                if criter_id and criter_id in h_zone_seen[h][zone]:
                    continue   # même événement, segment déjà comptabilisé
                h_zone_weights[h][zone].append(weight)
                if criter_id:
                    h_zone_seen[h][zone].add(criter_id)

    # Merge TomTom incidents avec decay progressif par type
    # iconCategory → {horizon_min: decay_factor}
    _TT_DECAY: Dict[int, Dict[int, float]] = {
        1:  {0: 1.0, 30: 0.50, 60: 0.20, 120: 0.0},   # Accident
        6:  {0: 1.0, 30: 0.70, 60: 0.40, 120: 0.0},   # Bouchon
        7:  {0: 1.0, 30: 0.90, 60: 0.80, 120: 0.5},   # Voie fermée
        8:  {0: 1.0, 30: 0.90, 60: 0.80, 120: 0.5},   # Route fermée
        9:  {0: 1.0, 30: 1.00, 60: 1.00, 120: 1.0},   # Travaux
        14: {0: 1.0, 30: 0.50, 60: 0.10, 120: 0.0},   # Véhicule en panne
    }
    _TT_DECAY_DEFAULT = {0: 1.0, 30: 0.60, 60: 0.30, 120: 0.0}

    for tt in await _fetch_tomtom_incidents_cached():
        z       = tt["zone"]
        w       = tt["weight"]
        decay_h = _TT_DECAY.get(tt.get("icon_cat", 0), _TT_DECAY_DEFAULT)
        for h in _INCIDENT_HORIZONS:
            factor = decay_h.get(h, 0.0)
            if factor > 0:
                h_zone_weights[h][z].append(round(w * factor, 3))

    # Score courant (h=0)
    current: Dict[str, float] = {}
    for z in ZONE_CENTROIDS:
        current[z] = _zone_score_from_weights(h_zone_weights[0][z])
        log.info(
            f"[criter-incidents] zone={z} "
            f"count={len(h_zone_weights[0][z])} score={current[z]}"
        )

    # Schedule (h=30/60/120)
    schedule: Dict[str, Dict[int, float]] = {
        z: {h: _zone_score_from_weights(h_zone_weights[h][z]) for h in [30, 60, 120]}
        for z in ZONE_CENTROIDS
    }

    # Détails lisibles des événements actifs par zone
    PARIS_OFFSET = datetime.timezone(datetime.timedelta(hours=2))
    events_by_zone: Dict[str, list] = {z: [] for z in ZONE_CENTROIDS}

    for feat in features:
        props  = feat.get("properties", {})
        geom   = feat.get("geometry", {})
        coords = geom.get("coordinates", [])
        point  = _multipoint_centroid(coords)
        if not point:
            continue
        lat, lon = point
        zone = _nearest_zone(lat, lon)
        if not zone or not _is_event_active_at(props, now):
            continue

        evt_type = (
            props.get("networkmanagementtype")
            or props.get("disturbanceactivitytype")
            or props.get("type", "")
        )
        comment  = props.get("publiccomment") or ""
        parts    = [p.strip() for p in comment.split("|")]
        label    = parts[0][:70] if parts else ""
        detail   = parts[1][:80] if len(parts) > 1 else ""

        # Direction de circulation
        direction_raw = props.get("direction", "")
        direction_lbl = {
            "bothWays": "",
            "inbound":  "→ centre",
            "outbound": "→ périphérie",
        }.get(direction_raw, "")

        end_s    = props.get("endtime", "")
        ends_soon = False
        end_fmt  = ""
        try:
            end_dt = datetime.datetime.fromisoformat(end_s)
            if end_dt.tzinfo is None:
                end_dt = end_dt.replace(tzinfo=datetime.timezone.utc)
            end_fmt   = end_dt.astimezone(PARIS_OFFSET).strftime("%-d %b %H:%M")
            ends_soon = now <= end_dt <= now + datetime.timedelta(hours=2)
        except (ValueError, TypeError):
            pass

        events_by_zone[zone].append({
            "type":      evt_type,
            "label":     label,
            "detail":    detail,
            "direction": direction_lbl,
            "end":       end_fmt,
            "ends_soon": ends_soon,
            "weight":    _criter_event_weight(props),
        })

    # Ajouter les incidents TomTom dans events_by_zone (affichage frontend)
    for tt in _tomtom_cache.get("data") or []:
        events_by_zone[tt["zone"]].append({
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

    return current, schedule, events_by_zone

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


def _tomtom_weight(icon_cat: int, magnitude: int) -> float:
    base = _TOMTOM_BASE_WEIGHT.get(icon_cat, 0.5)
    # magnitude : 1=mineur 2=modéré 3=majeur → +0 / +15% / +30%
    mult = {1: 1.0, 2: 1.15, 3: 1.30}.get(magnitude, 1.0)
    return round(base * mult, 2)


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
        zone = _nearest_zone(float(lat), float(lon))
        if not zone:
            continue

        icon_cat  = int(props.get("iconCategory", 0))
        magnitude = int(props.get("magnitudeOfDelay", 1))
        weight    = _tomtom_weight(icon_cat, magnitude)
        if weight <= 0:
            continue

        desc_list = props.get("events", [])
        desc      = desc_list[0].get("description", "") if desc_list else ""
        from_s    = props.get("from", "")
        to_s      = props.get("to", "")
        from_to   = f"{from_s} → {to_s}".strip(" →") if (from_s or to_s) else ""
        label     = (desc or _TOMTOM_CATEGORY_LABEL.get(icon_cat, "Incident"))[:70]
        detail    = from_to[:80]

        delay_s   = props.get("delay") or 0
        delay_min = round(int(delay_s) / 60) if delay_s else 0

        result.append({
            "zone":      zone,
            "weight":    weight,
            "label":     label,
            "detail":    detail,
            "direction": "",
            "delay_min": delay_min,
            "evt_type":  _TOMTOM_CATEGORY_TYPE.get(icon_cat, "other"),
            "icon_cat":  icon_cat,
        })

    log.info(f"[tomtom-incidents] {len(result)} incidents actifs (1 appel API)")
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

ARRET_ZONE: Dict[int, str] = {
    35834: "part-dieu",
    50041: "brotteaux",   50042: "brotteaux",   50043: "brotteaux",
    50001: "presquile",   50002: "presquile",
    50021: "presquile",   50022: "presquile",   50023: "presquile",
    50024: "presquile",   50025: "presquile",
    50211: "presquile",   50212: "presquile",
    50461: "presquile",   50462: "presquile",   50463: "presquile",
    50851: "perrache",    50852: "perrache",
    50441: "guillotiere", 50921: "guillotiere", 50922: "guillotiere",
    52001: "gerland",     52002: "gerland",     52201: "gerland",
    50951: "vieux-lyon",  50952: "vieux-lyon",  50953: "vieux-lyon",
    52241: "fourviere",   50931: "fourviere",
    51601: "confluence",  51602: "confluence",
    52233: "croix-rousse", 52234: "croix-rousse", 52221: "croix-rousse",
    51031: "villette",    51032: "villette",
    1511:  "villette",    51011: "villette",    51012: "villette",
    3434:  "villette",    50401: "villette",
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
SEUIL_PASSAGES = 10

def _parse_delai(raw: str) -> Optional[float]:
    raw = raw.strip()
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
    return {z: min(cnt / SEUIL_PASSAGES, 1.0) for z, cnt in zone_count.items()}

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
        zone = _nearest_zone(float(lat), float(lng))
        if zone:
            zone_tauxs.setdefault(zone, []).append(taux)
    return {z: round(sum(v) / len(v), 4) for z, v in zone_tauxs.items()}

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
        signals           : Dict[str, Dict[str, float]]   — signaux par zone
        incident_schedule : Dict[str, Dict[int, float]]   — incidents planifiés t+30/60/120
    """
    weather_t, event_t, traffic_t, incident_result = await asyncio.gather(
        fetch_weather(),
        fetch_event_signals(),
        fetch_traffic(),
        fetch_incidents(),
    )
    incident_t, incident_schedule, incident_events = incident_result

    try:
        parcrelais, passages, velov = await asyncio.gather(
            _fetch_parcrelais(), _fetch_passages(), _fetch_velov()
        )
        def _transport_score(zone: str) -> float:
            return round(
                parcrelais.get(zone, 0.35) * 0.3
                + passages.get(zone, 0.0)  * 0.5
                + velov.get(zone, 0.5)     * 0.2,
                4,
            )
    except Exception as e:
        log.warning(f"[fetch_all_signals] transport fallback: {e}")
        def _transport_score(zone: str) -> float:
            return _deterministic_fallback(zone)

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

    return result, incident_schedule, incident_events