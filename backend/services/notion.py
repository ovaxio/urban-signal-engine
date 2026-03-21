"""Notion integration — forward contact leads to a Notion database.

Setup (one-time):
  1. Go to https://www.notion.so/my-integrations → New integration
     - Name: "Urban Signal Engine"
     - Capabilities: Insert content (read content not needed)
     - Copy the "Internal Integration Secret" → NOTION_TOKEN env var

  2. Create a Notion database with these properties:
     - Name        : Title     (auto-created)
     - Email       : Email
     - Organisation: Text
     - Message     : Text
     - Date        : Date
     - Statut      : Select    → options: Nouveau, Qualifié, Demo, Devis, Perdu
     - Source      : Select    → options: Formulaire, Outbound

  3. Open the database page → Share → Invite your integration (Urban Signal Engine)

  4. Copy the database ID from the URL:
     https://www.notion.so/{workspace}/{DATABASE_ID}?v=...
     → NOTION_LEADS_DB_ID env var

  5. Add both env vars to Render dashboard:
     NOTION_TOKEN=secret_...
     NOTION_LEADS_DB_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
"""

import logging
import os

import httpx

log = logging.getLogger("notion")

NOTION_API_URL = "https://api.notion.com/v1/pages"
NOTION_VERSION = "2022-06-28"

_title_prop_cache: dict[str, str] = {}


async def _get_title_prop(client: httpx.AsyncClient, token: str, db_id: str) -> str:
    """Trouve le nom de la propriété titre de la base Notion (mis en cache)."""
    if db_id in _title_prop_cache:
        return _title_prop_cache[db_id]
    try:
        r = await client.get(
            f"https://api.notion.com/v1/databases/{db_id}",
            headers={"Authorization": f"Bearer {token}", "Notion-Version": NOTION_VERSION},
        )
        if r.status_code == 200:
            for name, prop in r.json().get("properties", {}).items():
                if prop.get("type") == "title":
                    _title_prop_cache[db_id] = name
                    log.info("Notion title property detected: '%s'", name)
                    return name
    except Exception as e:
        log.warning("Could not detect Notion title property: %s", e)
    return "Nom"  # fallback


async def send_lead_to_notion(
    nom: str,
    email: str,
    organisation: str,
    message: str,
    submitted_at: str,
) -> None:
    """Crée une page dans la base Notion des leads. No-op si env vars absents."""
    token = os.getenv("NOTION_TOKEN", "").strip()
    db_id = os.getenv("NOTION_LEADS_DB_ID", "").strip()
    if not token or not db_id:
        log.warning("Notion not configured (NOTION_TOKEN=%s, NOTION_LEADS_DB_ID=%s)", bool(token), bool(db_id))
        return

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            title_prop = await _get_title_prop(client, token, db_id)
            payload = {
                "parent": {"database_id": db_id},
                "properties": {
                    title_prop: {
                        "title": [{"text": {"content": f"{nom} — {organisation}"}}]
                    },
                    "Email": {"email": email},
                    "Organisation": {"rich_text": [{"text": {"content": organisation}}]},
                    "Message": {"rich_text": [{"text": {"content": message[:2000]}}]},
                    "Date": {"date": {"start": submitted_at}},
                    "Statut": {"select": {"name": "Nouveau"}},
                    "Source": {"select": {"name": "Formulaire"}},
                },
            }
            r = await client.post(
                NOTION_API_URL,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Notion-Version": NOTION_VERSION,
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            if r.status_code not in (200, 201):
                log.warning("Notion API error %d: %s", r.status_code, r.text[:200])
            else:
                log.info("Lead forwarded to Notion: %s (%s)", email, organisation)
    except Exception as e:
        log.warning("Notion forwarding failed: %s", e)
