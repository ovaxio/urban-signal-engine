"""
Urban Signal Engine — API Key Authentication
Simple API key system stored in SQLite. Keys are generated via admin endpoint
and validated via FastAPI dependency injection.
"""

import hashlib
import logging
import secrets
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import Depends, HTTPException, Security
from fastapi.security import APIKeyHeader

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent / "data" / "urban_signal.db"

# ── Schema ───────────────────────────────────────────────────────────────────

CREATE_API_KEYS = """
CREATE TABLE IF NOT EXISTS api_keys (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    key_hash     TEXT    NOT NULL UNIQUE,
    key_prefix   TEXT    NOT NULL,
    organisation TEXT    NOT NULL,
    contact_email TEXT   NOT NULL,
    created_at   TEXT    NOT NULL,
    last_used_at TEXT,
    is_active    INTEGER NOT NULL DEFAULT 1
);
"""


def init_auth_db() -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(CREATE_API_KEYS)


# ── Key generation ───────────────────────────────────────────────────────────

def _hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def generate_api_key(organisation: str, contact_email: str) -> str:
    """Generate a new API key, store its hash, return the raw key (shown once)."""
    raw_key = f"use_{secrets.token_hex(24)}"
    key_hash = _hash_key(raw_key)
    key_prefix = raw_key[:8]
    now = datetime.now(timezone.utc).isoformat()

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO api_keys (key_hash, key_prefix, organisation, contact_email, created_at) VALUES (?, ?, ?, ?, ?)",
            (key_hash, key_prefix, organisation, contact_email, now),
        )
    logger.info(f"API key generated for {organisation} (prefix: {key_prefix})")
    return raw_key


def revoke_api_key(key_prefix: str) -> bool:
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute(
            "UPDATE api_keys SET is_active = 0 WHERE key_prefix = ? AND is_active = 1",
            (key_prefix,),
        )
        return cursor.rowcount > 0


def list_api_keys() -> list[dict]:
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT key_prefix, organisation, contact_email, created_at, last_used_at, is_active FROM api_keys ORDER BY created_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]


# ── Validation ───────────────────────────────────────────────────────────────

def validate_api_key(key: str) -> Optional[dict]:
    """Validate an API key. Returns key info if valid, None otherwise."""
    key_hash = _hash_key(key)
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT id, key_prefix, organisation, contact_email FROM api_keys WHERE key_hash = ? AND is_active = 1",
            (key_hash,),
        ).fetchone()
        if row:
            now = datetime.now(timezone.utc).isoformat()
            conn.execute("UPDATE api_keys SET last_used_at = ? WHERE id = ?", (now, row["id"]))
            return dict(row)
    return None


# ── FastAPI dependency ───────────────────────────────────────────────────────

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def require_api_key(api_key: Optional[str] = Security(_api_key_header)) -> dict:
    """FastAPI dependency: require a valid API key in X-API-Key header."""
    if not api_key:
        raise HTTPException(status_code=401, detail="API key manquante. Ajoutez le header X-API-Key.")
    key_info = validate_api_key(api_key)
    if not key_info:
        raise HTTPException(status_code=403, detail="API key invalide ou révoquée.")
    return key_info


async def optional_api_key(api_key: Optional[str] = Security(_api_key_header)) -> Optional[dict]:
    """FastAPI dependency: validate API key if present, but don't require it."""
    if not api_key:
        return None
    return validate_api_key(api_key)
