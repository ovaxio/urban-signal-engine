"""Contact form endpoint — stores submissions via storage service."""

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr

from services.storage import save_contact

log = logging.getLogger("contact")

router = APIRouter(prefix="/contact", tags=["contact"])


class ContactRequest(BaseModel):
    nom: str
    email: EmailStr
    organisation: str
    message: str


@router.post("", status_code=201)
async def submit_contact(payload: ContactRequest):
    try:
        save_contact(payload.nom, payload.email, payload.organisation, payload.message)
    except Exception as e:
        log.error(f"Contact submission error: {e}")
        raise HTTPException(status_code=500, detail="Erreur lors de l'envoi du message.")
    return {"status": "ok", "message": "Message envoyé avec succès."}
