"""Admin endpoints — protected by ADMIN_SECRET env var."""

import logging
import os
from typing import Optional

from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel, EmailStr

import services.scoring as _scoring
from services.auth import generate_api_key, revoke_api_key, list_api_keys
from services.storage import (
    get_calibration_log, get_request_logs,
    get_calibration_baselines, get_calibration_baselines_per_zone,
    get_calibration_baselines_by_slot, get_calibration_baselines_per_zone_by_slot,
    save_calibration_log, CALIBRATION_CUTOFF_TS,
    patch_incident_history,
)

log = logging.getLogger("admin")

router = APIRouter(prefix="/admin", tags=["admin"])

ADMIN_SECRET = os.getenv("ADMIN_SECRET", "")


def _check_admin(authorization: Optional[str]) -> None:
    if not ADMIN_SECRET:
        raise HTTPException(status_code=503, detail="ADMIN_SECRET non configuré.")
    if authorization != f"Bearer {ADMIN_SECRET}":
        raise HTTPException(status_code=401, detail="Accès admin non autorisé.")


class CreateKeyRequest(BaseModel):
    organisation: str
    contact_email: EmailStr


@router.post("/api-keys", status_code=201)
async def create_api_key(payload: CreateKeyRequest, authorization: Optional[str] = Header(default=None)):
    _check_admin(authorization)
    raw_key = generate_api_key(payload.organisation, payload.contact_email)
    log.info(f"Admin: API key created for {payload.organisation}")
    return {
        "api_key": raw_key,
        "organisation": payload.organisation,
        "message": "Conservez cette clé — elle ne sera plus affichée.",
    }


@router.get("/api-keys")
async def get_api_keys(authorization: Optional[str] = Header(default=None)):
    _check_admin(authorization)
    return {"keys": list_api_keys()}


@router.delete("/api-keys/{key_prefix}")
async def delete_api_key(key_prefix: str, authorization: Optional[str] = Header(default=None)):
    _check_admin(authorization)
    if revoke_api_key(key_prefix):
        log.info(f"Admin: API key revoked (prefix: {key_prefix})")
        return {"status": "revoked", "key_prefix": key_prefix}
    raise HTTPException(status_code=404, detail="Clé non trouvée ou déjà révoquée.")


@router.get("/request-logs")
async def get_request_logs_endpoint(
    authorization: Optional[str] = Header(default=None),
    limit: int = 100,
    status_code: Optional[int] = None,
    path: Optional[str] = None,
):
    """Historique des requêtes HTTP — filtre par status_code et/ou path."""
    _check_admin(authorization)
    logs = get_request_logs(limit=limit, status_code=status_code, path_filter=path)
    return {"count": len(logs), "logs": logs}


@router.post("/recalibrate")
async def force_recalibrate(authorization: Optional[str] = Header(default=None)):
    """Patch les raw_incident=0.0 corrompus puis force une recalibration immédiate."""
    _check_admin(authorization)

    patched = patch_incident_history()
    log.info("Recalibration forcée : %d lignes raw_incident=0.0 patchées → 1.70", patched)

    global_bl = {"event": {"mu": 0.2, "sigma": 0.3}}
    baselines, n_rows = get_calibration_baselines(min_count=96)
    if baselines:
        global_bl.update(baselines)

    zone_bls = get_calibration_baselines_per_zone(min_count=48)
    _scoring.set_baselines(global_bl, zone_bls)

    slot_bl = get_calibration_baselines_by_slot(min_count=24)
    zone_slot_bl = get_calibration_baselines_per_zone_by_slot(min_count=12)
    _scoring.set_slot_baselines(slot_bl, zone_slot_bl)
    log.info("Recalibration forcée terminée : %d zones, %d relevés globaux, %d slots",
             len(zone_bls), n_rows, len(slot_bl))

    return {
        "status": "ok",
        "patched_incident_rows": patched,
        "zones_recalibrated": len(zone_bls),
        "global_rows": n_rows,
        "slots_calibrated": len(slot_bl),
    }


@router.get("/forecast-learning")
async def forecast_learning_preview(authorization: Optional[str] = Header(default=None)):
    """
    Aperçu de l'auto-apprentissage forecast : paramètres courants, ajustements proposés,
    stats d'accuracy par horizon (ADR-018).
    """
    _check_admin(authorization)
    from services.forecast_learning import preview_learning, get_forecast_params
    from services.forecast_storage import get_forecast_accuracy
    accuracy = get_forecast_accuracy()
    preview = preview_learning(accuracy)
    return preview


@router.get("/calibration")
async def get_calibration(authorization: Optional[str] = Header(default=None)):
    """
    Audit des calibrations : dernières entrées du calibration_log.
    Signale les shifts > 15% pour revue manuelle.
    """
    _check_admin(authorization)
    entries = get_calibration_log(limit=50)

    large_shifts = []
    for e in entries:
        if e["old_mu"] is not None and e["new_mu"] is not None and not e["skipped"]:
            denom = max(abs(e["old_mu"]), 0.01)
            delta_pct = round(abs(e["new_mu"] - e["old_mu"]) / denom * 100, 1)
            e["delta_mu_pct"] = delta_pct
            if delta_pct > 15:
                large_shifts.append(e)
        else:
            e["delta_mu_pct"] = None

    return {
        "entries": entries,
        "large_shifts": large_shifts,
    }
