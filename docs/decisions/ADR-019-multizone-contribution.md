# ADR-019 — Multi-zone weighted contribution (Gaussian falloff)

**Date**: 2026-04-01
**Status**: Accepted
**Source**: Live comparison Google Maps vs USE — Perrache under-scored at 53 despite visible congestion

## Decision
Replace winner-takes-all `_nearest_zone()` with `_zone_weights()`: each data point (traffic segment, incident, station) contributes to multiple zones with Gaussian-decay weights, normalized to sum=1.

## Values
- Gaussian sigma: 1.2 km (at 0.8km: w=0.72, at 1.2km: w=0.61, at 2km: w=0.19)
- Minimum weight threshold: 0.05 (drop negligible contributions)
- Hard cutoff: unchanged 2km (_MAX_ZONE_D2)
- Feature flag: MULTIZONE_ENABLED (env var, default false)

## Rationale
- Perrache centroid is 0.82km from Presqu'ile, 1.16km from Guillotiere, 1.18km from Confluence — nearest-centroid assigns boundary segments to neighbors, starving Perrache
- Events system (events.py) already uses proximity-weighted multi-zone — proven pattern
- Gaussian decay is smooth, differentiable, and produces intuitive weight distributions
- Flag toggle allows A/B comparison and safe rollback

## Consequences
- ingestion.py: new `_zone_weights()`, 4 callers modified (traffic, incidents, TomTom, Velov)
- config.py: 3 new constants (MULTIZONE_ENABLED, MULTIZONE_SIGMA_KM, MULTIZONE_MIN_WEIGHT)
- Boundary zones (Perrache, Confluence) gain segments; interior zones (Montchat, Villette) unchanged
- Baselines recalibrate automatically on next weekly cycle post-activation
- Scoring pipeline (scoring.py, smoothing.py) unchanged — same Dict[zone, signal] interface

## DO NOT
- Enable flag without running backtest_multizone.py first
- Change sigma below 0.8 (collapses to nearest-centroid) or above 2.0 (all zones blur together)
- Apply multi-zone to static lookup tables (ARRET_ZONE, PARC_ZONE) — those are manually curated

## Triggers
Re-read when: ingestion.py _zone_weights, config.py MULTIZONE_*, backtest_multizone.py, _nearest_zone
