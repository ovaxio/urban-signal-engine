"""Contact form endpoint — stores submissions in SQLite."""

import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr

log = logging.getLogger("contact")

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "urban_signal.db"

router = APIRouter(prefix="/contact", tags=["contact"])


class ContactRequest(BaseModel):
    nom: str
    email: EmailStr
    organisation: str
    message: str


def _init_contact_table() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS contact_submissions (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                nom         TEXT NOT NULL,
                email       TEXT NOT NULL,
                organisation TEXT NOT NULL,
                message     TEXT NOT NULL,
                created_at  TEXT NOT NULL
            )
        """)


# Init table on module load
_init_contact_table()


@router.post("", status_code=201)
async def submit_contact(payload: ContactRequest):
    now = datetime.now(timezone.utc).isoformat()
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                "INSERT INTO contact_submissions (nom, email, organisation, message, created_at) VALUES (?, ?, ?, ?, ?)",
                (payload.nom, payload.email, payload.organisation, payload.message, now),
            )
        log.info(f"Contact form submission from {payload.email} ({payload.organisation})")
    except Exception as e:
        log.error(f"Contact submission error: {e}")
        raise HTTPException(status_code=500, detail="Erreur lors de l'envoi du message.")
    return {"status": "ok", "message": "Message envoyé avec succès."}
