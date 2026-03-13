"""
Urban Signal Engine — Alert Service
Détection des franchissements de seuil et dispatch (DB + webhook).

Logique :
  - Après chaque refresh, compare prev_scores vs new_scores
  - Si une zone franchit TENDU (55) ou CRITIQUE (72) → alerte RISING
  - Si une zone repasse sous CALME (35) → alerte CALME (retour au calme)
  - Cooldown 30 min par zone pour éviter le spam
  - Persiste chaque alerte en base + dispatch webhook si ALERT_WEBHOOK_URL configuré
"""

import asyncio
import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Dict, List

import httpx

log = logging.getLogger("alerts")

COOLDOWN_MINUTES = 30
TENDU_THRESHOLD  = 55
CRIT_THRESHOLD   = 72
CALM_THRESHOLD   = 35

# Cooldown in-memory : zone_id → dernière alerte envoyée
_cooldown: Dict[str, datetime] = {}


def check_alerts(prev_scores: Dict[str, int], new_scores: List[dict]) -> List[dict]:
    """
    Détecte les franchissements de seuil entre prev et new scores.
    Retourne la liste des alertes à persister/dispatcher.
    """
    now = datetime.now(timezone.utc)
    alerts = []

    for zone in new_scores:
        zid   = zone["zone_id"]
        new_s = zone["urban_score"]
        prev_s = prev_scores.get(zid)

        if prev_s is None:
            continue

        # Cooldown — pas de double alerte dans les 30 min
        last = _cooldown.get(zid)
        if last and (now - last).total_seconds() < COOLDOWN_MINUTES * 60:
            continue

        alert_type = None
        if new_s >= CRIT_THRESHOLD and prev_s < CRIT_THRESHOLD:
            alert_type = "CRITIQUE"
        elif new_s >= TENDU_THRESHOLD and prev_s < TENDU_THRESHOLD:
            alert_type = "TENDU"
        elif new_s < CALM_THRESHOLD and prev_s >= CALM_THRESHOLD:
            alert_type = "CALME"

        if alert_type:
            alerts.append({
                "ts":          now.isoformat(timespec="seconds"),
                "zone_id":     zid,
                "zone_name":   zone.get("zone_name", zid),
                "alert_type":  alert_type,
                "urban_score": new_s,
                "prev_score":  prev_s,
                "level":       zone.get("level", ""),
            })
            _cooldown[zid] = now
            log.info(
                "ALERTE [%s] %s : %d → %d (%s)",
                alert_type, zid, prev_s, new_s, zone.get("level", "")
            )

    return alerts


async def dispatch_alerts(alerts: List[dict]) -> None:
    """Persiste en base et envoie le webhook si configuré."""
    if not alerts:
        return

    from services.storage import save_alerts  # import local pour éviter cycle
    save_alerts(alerts)

    webhook_url = os.getenv("ALERT_WEBHOOK_URL", "").strip()
    if not webhook_url:
        return

    async with httpx.AsyncClient(timeout=5.0) as client:
        for alert in alerts:
            emoji = {"CRITIQUE": "🔴", "TENDU": "🟠", "CALME": "🟢"}.get(alert["alert_type"], "⚪")
            payload = {
                **alert,
                "message": (
                    f"{emoji} {alert['zone_name']} → {alert['alert_type']} "
                    f"({alert['urban_score']}/100, était {alert['prev_score']})"
                ),
            }
            try:
                r = await client.post(webhook_url, json=payload)
                log.info("Webhook dispatched → %s (%d)", alert["zone_id"], r.status_code)
            except Exception as e:
                log.warning("Webhook dispatch failed for %s : %s", alert["zone_id"], e)
