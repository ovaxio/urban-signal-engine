# ADR-007 — Request Logging Strategy (SQLite, MVP)

**Date**: 2026-03-21
**Status**: Accepted
**Source**: Claude Code session — historisation des logs serveur

## Decision
Persist HTTP request logs in a SQLite `request_logs` table (7-day rolling window).
Reject external log services (Logtail, Papertrail, Datadog) until first paying customer.

## Values
```
Retention: 7 days (purged weekly in calibration_loop)
Write: asyncio.create_task (fire-and-forget, non-blocking)
Fields: ts, method, path, status_code, duration_ms, client_ip
Excluded: /health (too noisy — pinged every 5 min by Render)
Query: GET /admin/request-logs?limit=&status=&path=
```

## Rationale
- SQLite already present — zero new dependencies
- External services ($3–10/month) unjustified before first paying customer
- File-based logs are unstructured and unqueryable (grep only)
- 7-day window covers incident debugging window for solo founder

## Consequences
- Request logs queryable by status_code, path, time range
- Lost on Render restart (ephemeral) — diagnostic only, not audit trail
- Disk impact: ~33MB/day peak → purge keeps it bounded

## DO NOT
- Add external log service without explicit customer SLA requirement
- Persist /health endpoint logs (noise without signal)
- Use request_logs as compliance audit trail (ephemeral, not guaranteed)

## Triggers
Re-read when: `main.py middleware`, `storage.py request_logs`, external logging SaaS evaluation
