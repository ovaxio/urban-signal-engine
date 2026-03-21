# ADR-006 — Zone Centroids: Source of Truth

**Date**: 2026-03-21
**Status**: Accepted
**Source**: Claude Code session — fix ZONE_CENTROIDS divergence frontend/backend

## Decision
`backend/config.py` is the single source of truth for zone centroids.
Frontend must copy values verbatim; never maintain its own.

## Values
```python
# backend/config.py (authoritative)
ZONE_CENTROIDS = {
    "part-dieu":    (45.7580, 4.8490),
    "presquile":    (45.7558, 4.8320),
    "vieux-lyon":   (45.7622, 4.8271),
    "perrache":     (45.7488, 4.8286),
    "gerland":      (45.7283, 4.8336),
    "guillotiere":  (45.7460, 4.8430),
    "brotteaux":    (45.7690, 4.8560),
    "villette":     (45.7720, 4.8620),
    "montchat":     (45.7560, 4.8760),
    "fourviere":    (45.7622, 4.8150),
    "croix-rousse": (45.7760, 4.8320),
    "confluence":   (45.7400, 4.8200),
}
```

## Rationale
- Backend uses centroids for `nearest_zone()` (signal assignment) and haversine (event impact)
- Frontend had hand-copied values never synced → divergences up to 1.7km (villette)
- Map markers and algorithm zones must be spatially consistent

## Consequences
- Map markers now align with the zones used for scoring
- Frontend comment points to backend file as source
- Any centroid update requires changing `config.py` only, then copying to `constants.ts`

## DO NOT
- Maintain separate coordinates in frontend — always copy from `config.py`
- Update `frontend/domain/constants.ts` without updating `config.py` first

## Triggers
Re-read when: `config.py ZONE_CENTROIDS`, `frontend/domain/constants.ts`, `ZoneMap.tsx`, `ingestion.py nearest_zone`
