"""Contact form endpoint — stores submissions via storage service."""

import logging
import os
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr

from services.notion import send_lead_to_notion
from services.storage import save_contact

log = logging.getLogger("contact")

router = APIRouter(prefix="/contact", tags=["contact"])


class ContactRequest(BaseModel):
    nom: str
    email: EmailStr
    organisation: str
    message: str
    source: str = "Formulaire"


@router.post("", status_code=201)
async def submit_contact(payload: ContactRequest):
    submitted_at = datetime.now(timezone.utc).isoformat()

    try:
        save_contact(payload.nom, payload.email, payload.organisation, payload.message)
    except Exception as e:
        log.error("Contact submission error: %s", e)
        raise HTTPException(status_code=500, detail="Erreur lors de l'envoi du message.")

    webhook_url = os.getenv("CONTACT_WEBHOOK_URL", "").strip()
    if webhook_url:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                await client.post(webhook_url, json={
                    "text": f"📩 Nouveau lead\n*{payload.nom}* — {payload.organisation} ({payload.email})\n{payload.message}",
                    "nom": payload.nom,
                    "email": payload.email,
                    "organisation": payload.organisation,
                    "message": payload.message,
                })
        except Exception as e:
            log.warning("Contact webhook failed: %s", e)

    await send_lead_to_notion(
        payload.nom, payload.email, payload.organisation, payload.message, submitted_at, payload.source
    )

    return {"status": "ok", "message": "Message envoyé avec succès."}
