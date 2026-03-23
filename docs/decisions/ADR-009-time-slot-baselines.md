# ADR-009 — Baselines segmentées par créneau horaire

**Date**: 2026-03-23
**Status**: Accepted
**Source**: Claude Code session — fix scores 21-25 à 7h10 (sous baseline) malgré trafic en montée

## Decision
Les baselines de calibration sont segmentées en 4 créneaux horaires (nuit/matin/après-midi/soir) au lieu d'un calcul toutes heures confondues.

## Values
- Slots : nuit (0-6h), matin (6-12h), aprem (12-18h), soir (18-24h)
- min_count slot global : 200 | slot+zone : 30
- Fallback : zone+slot → slot global → zone global → BASELINE hardcodé
- MIN_SIGMA inchangés (traffic=0.15, transport=0.20, weather=0.10, incident=0.15)
- Event exclu des slots (non-stationnaire)

## Rationale
- À 7h10, trafic V=1.0 < mu_global=1.05 → z négatif amplifié par φ=1.55 → scores 21-25
- Baseline global mélange nuit (trafic~0.5) et rush (trafic~2.0) → moyenne non représentative
- Avec slot "matin", mu_matin > mu_global et sigma_matin plus large → z moins négatif

## Consequences
- Les scores 7h10 passent de 21-25 à ~27-29 (pré-rush moins pénalisé)
- Le rush 8h-9h30 reste bien capté (z toujours fortement positif vs mu_matin)
- `_effective_baseline(zone_id, dt)` requiert maintenant un paramètre `dt`

## DO NOT
- Ne pas passer à 6+ slots sans 30+ jours de données (sous-échantillonnage)
- Ne pas inclure event dans la calibration par slot
- Ne pas modifier sigmoid center (1.5) ou φ profiles en réponse à ce changement

## Triggers
Re-read when: storage.py calibration, scoring.py _effective_baseline, main.py _apply_calibration, config.py BASELINE
