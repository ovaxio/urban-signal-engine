# ADR-017 — WMO Granular Weather Score Scale

**Date**: 2026-03-28
**Status**: Accepted
**Source**: Guillaume — replace binary WMO thresholds with validated granular lookup table

## Decision
Replace the two binary WMO thresholds (`WEATHER_WMO_MODERATE=61 → +0.8`, `WEATHER_WMO_SEVERE=95 → +1.5`) with a granular lookup dict `WEATHER_WMO_SCORE` in `config.py` and a helper `_wmo_contribution(wmo)` in `ingestion.py`.

## Values
```python
WEATHER_WMO_SCORE: Dict[int, float] = {
    0: 0.0, 1: 0.0, 2: 0.0, 3: 0.0,          # Clear/cloudy
    45: 0.4, 48: 0.4,                           # Fog
    51: 0.2, 53: 0.2, 55: 0.2,                 # Drizzle
    61: 0.3, 63: 0.5, 65: 0.8,                 # Rain (slight/moderate/heavy)
    71: 0.7, 73: 0.7, 75: 0.7, 77: 0.7,       # Snow
    80: 0.2, 81: 0.5, 82: 1.0,                 # Rain showers (slight/moderate/violent)
    85: 0.7, 86: 0.7,                           # Snow showers
    95: 1.5, 96: 1.5, 99: 1.5,                 # Thunderstorm
}
```
Unchanged: `WEATHER_PRECIP_DIVISOR=5.0`, `WEATHER_WIND_THRESHOLD=50.0`, `WEATHER_SCORE_MAX=3.0`.

## Rationale
- The previous binary system mapped any rain code ≥61 to +0.8, ignoring the wide operational difference between slight drizzle (WMO 61) and violent showers (WMO 82).
- Granular lookup allows proportional scoring: drizzle (+0.2) vs heavy rain (+0.8) vs violent showers (+1.0) vs thunderstorm (+1.5).
- The weather score models operational disruption (traffic slowdowns, reduced pedestrian mobility, event cancellations), NOT criminological risk. Boston studies show rain reduces crime incidents — the weather component is intentionally decoupled from that dynamic.
- Codes not in the table default to 0.0 (safe fallback for unknown/future WMO codes).
- `WEATHER_WMO_MODERATE` and `WEATHER_WMO_SEVERE` constants are removed — they were the only callers.

## Consequences
- Weather score now varies more finely with actual conditions; slight rain drops from +0.8 to +0.3 → lower daytime scores on mild wet days.
- Violent showers (WMO 82) score +1.0, slightly below the previous heavy-rain cap of +0.8 being the max non-storm value — more accurate.
- `_weather_score_from_values()` in `ingestion.py` still called identically; no callers change.
- Forecast weather score (hourly loop) benefits from the same precision.

## DO NOT
- Do not add a ≥-threshold fallback ("if wmo >= X") — this reintroduces the binary problem; use exact dict lookup with 0.0 default.
- Do not interpret this as a criminological risk signal — weather captures mobility/operational disruption only.

## Triggers
Re-read when: ingestion.py `_weather_score_from_values`, `_wmo_contribution`, config.py `WEATHER_WMO_SCORE`, weather signal calibration, forecast weather scoring.
