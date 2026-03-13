"""Admin endpoints — protected by ADMIN_SECRET env var."""

import logging
import os
from typing import Optional

from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel, EmailStr

from services.auth import generate_api_key, revoke_api_key, list_api_keys

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
