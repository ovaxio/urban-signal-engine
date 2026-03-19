"""
Urban Signal Engine --- RSS Incidents Enrichment
=================================================
Fetch RSS from Lyon Capitale, detect Lyon-specific incident keywords,
map to USE zones. Display enrichment ONLY --- zero impact on scoring.
"""

import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Dict, List, Optional

import httpx

log = logging.getLogger("rss_incidents")

RSS_URL = "https://www.lyoncapitale.fr/feed/"
FETCH_INTERVAL_SECONDS = 600  # 10 minutes

# ---- Zone keyword mapping (USE zone_id -> location keywords) ----

ZONE_KEYWORDS: Dict[str, List[str]] = {
    "fourviere":    ["fourviere", "fourvière"],
    "presquile":    ["presqu'île", "presquile", "terreaux", "bellecour",
                     "cordeliers", "hôtel de ville", "hotel de ville",
                     "republique", "rue de la republique", "rue de la république"],
    "part-dieu":    ["part-dieu", "part dieu", "garibaldi"],
    "brotteaux":    ["brotteaux", "tête d'or", "tete d'or"],
    "villette":     ["villette", "grange blanche", "mermoz"],
    "montchat":     ["montchat", "monplaisir", "sans souci", "bachut"],
    "confluence":   ["confluence"],
    "perrache":     ["perrache"],
    "croix-rousse": ["croix-rousse", "croix rousse", "saint-exupéry",
                     "saint exupery", "pentes", "grande rue de la croix"],
    "gerland":      ["gerland", "groupama", "jean macé", "jean mace"],
    "vieux-lyon":   ["vieux lyon", "vieux-lyon", "saint-georges", "saint-paul",
                     "saint-jean"],
    "guillotiere":  ["guillotière", "guillotiere", "jean-jaurès", "jean jaures",
                     "saxe"],
}

INCIDENT_KEYWORDS: Dict[str, List[str]] = {
    "blocage":       ["blocage", "bloqué", "bloque", "bloquée", "bloquee"],
    "manifestation": ["manifestation", "manif", "cortège", "cortege",
                      "marche", "rassemblement", "protestation"],
    "greve":         ["grève", "greve", "mouvement social", "préavis", "preavis"],
    "accident":      ["accident", "collision", "carambolage"],
    "fermeture":     ["fermeture", "fermé", "ferme", "coupé", "coupe",
                      "interdit", "déviation", "deviation"],
    "incident":      ["incident", "perturbation", "trouble"],
}

SEVERITY_MAP: Dict[str, str] = {
    "blocage": "TENDU",
    "manifestation": "TENDU",
    "greve": "MODERE",
    "accident": "TENDU",
    "fermeture": "TENDU",
    "incident": "MODERE",
}


@dataclass
class RSSIncident:
    zone_id: str
    headline: str
    incident_type: str
    severity_hint: str
    published_at: str  # ISO string
    source: str = "lyon_capitale"
    url: str = ""


# ---- Cache ----

_rss_cache: List[RSSIncident] = []
_rss_last_fetch: Optional[datetime] = None


def _match_incident_type(text: str) -> Optional[str]:
    """Return first matching incident keyword category, or None."""
    for category, keywords in INCIDENT_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                return category
    return None


def _match_zones(text: str) -> List[str]:
    """Return all matching USE zone_ids from text."""
    matched = []
    for zone_id, keywords in ZONE_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                matched.append(zone_id)
                break
    return matched


def _parse_pubdate(raw: str) -> Optional[datetime]:
    """Parse RSS pubDate (RFC 2822) to UTC datetime."""
    try:
        dt = parsedate_to_datetime(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


async def fetch_rss_incidents() -> List[RSSIncident]:
    """
    Fetch Lyon Capitale RSS, extract incident-relevant items,
    map to USE zones. Returns list of RSSIncident (may be empty).
    Never raises --- enrichment must not break the main loop.
    """
    global _rss_cache, _rss_last_fetch

    now = datetime.now(timezone.utc)

    # Check cache
    if _rss_last_fetch and (now - _rss_last_fetch).total_seconds() < FETCH_INTERVAL_SECONDS:
        return _rss_cache

    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            r = await client.get(RSS_URL, headers={"User-Agent": "UrbanSignalEngine/1.0"})
            r.raise_for_status()
            xml_data = r.text
    except Exception as e:
        log.warning("[rss] Fetch failed: %s", e)
        return _rss_cache  # return stale cache on error

    try:
        root = ET.fromstring(xml_data)
    except ET.ParseError as e:
        log.warning("[rss] XML parse error: %s", e)
        return _rss_cache

    cutoff = now - timedelta(hours=2)
    results: List[RSSIncident] = []

    for item in root.findall(".//item"):
        title_el = item.find("title")
        desc_el = item.find("description")
        pubdate_el = item.find("pubDate")
        link_el = item.find("link")

        title = (title_el.text or "") if title_el is not None else ""
        desc = (desc_el.text or "") if desc_el is not None else ""
        pubdate_raw = (pubdate_el.text or "") if pubdate_el is not None else ""
        link = (link_el.text or "") if link_el is not None else ""

        # Parse and filter by freshness
        pub_dt = _parse_pubdate(pubdate_raw)
        if not pub_dt or pub_dt < cutoff:
            continue

        # Combine title + desc for keyword matching
        text = f"{title} {desc}".lower()

        # Match incident type
        inc_type = _match_incident_type(text)
        if not inc_type:
            continue

        # Match zones
        zones = _match_zones(text)
        if not zones:
            continue

        for zone_id in zones:
            results.append(RSSIncident(
                zone_id=zone_id,
                headline=title[:200],
                incident_type=inc_type,
                severity_hint=SEVERITY_MAP.get(inc_type, "MODERE"),
                published_at=pub_dt.isoformat(timespec="seconds"),
                url=link,
            ))

    _rss_cache = results
    _rss_last_fetch = now
    log.info("[rss] Fetched %d items, %d incidents matched", len(root.findall(".//item")), len(results))
    return results
