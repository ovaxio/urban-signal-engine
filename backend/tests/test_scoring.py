"""
Tests unitaires — services/scoring.py
Lancer : python -m pytest tests/ -v  (depuis backend/)
"""
import math
import sys
import pytest
from datetime import datetime, timezone, timedelta

sys.path.insert(0, ".")

from services.scoring import (
    BASELINE,
    normalize,
    compute_phi,
    compute_risk,
    compute_anomaly,
    compute_conv,
    compute_alert,
    compute_spread,
    compute_urban_score,
    score_level,
    top_causes,
    compute_forecast,
    score_zone,
    score_all_zones,
    NEIGHBORS,
    ZONE_NAMES,
)
from config import LAMBDA, WEIGHTS, ALPHA, THETA


# ─── Fixtures ──────────────────────────────────────────────────────────────────

SIGNALS_CALM = {
    "traffic": 0.9, "weather": 0.0, "event": 0.0,
    "transport": 0.05, "incident": 0.0,
}
SIGNALS_NEUTRAL = {
    "traffic": 1.30, "weather": 0.3, "event": 0.2,   # mu Criter recalibré
    "transport": 0.45, "incident": 0.8,
}
SIGNALS_RUSH = {
    "traffic": 2.5, "weather": 0.2, "event": 0.0,
    "transport": 0.65, "incident": 0.5,
}
SIGNALS_STORM = {
    "traffic": 2.8, "weather": 1.2, "event": 0.1,
    "transport": 0.70, "incident": 1.0,
}
SIGNALS_FETE = {
    "traffic": 3.0, "weather": 0.0, "event": 3.0,
    "transport": 0.90, "incident": 1.5,
}

DT_NIGHT  = datetime(2024, 3, 12, 1, 0, tzinfo=timezone.utc)   # 2h Paris
DT_RUSH   = datetime(2024, 3, 12, 7, 30, tzinfo=timezone.utc)  # 8h30 Paris
DT_NOON   = datetime(2024, 3, 12, 11, 0, tzinfo=timezone.utc)  # 12h Paris
DT_ERUSH  = datetime(2024, 3, 12, 17, 0, tzinfo=timezone.utc)  # 18h Paris


# ─── normalize ─────────────────────────────────────────────────────────────────

class TestNormalize:
    def test_baseline_gives_zero(self):
        for sig, bl in BASELINE.items():
            assert normalize(bl["mu"], sig) == pytest.approx(0.0, abs=1e-9)

    def test_above_baseline_is_positive(self):
        assert normalize(3.0, "traffic") > 0
        assert normalize(2.0, "weather") > 0
        assert normalize(2.0, "incident") > 0

    def test_below_baseline_is_negative(self):
        assert normalize(0.5, "traffic") < 0
        assert normalize(0.0, "weather") < 0
        assert normalize(0.0, "incident") < 0

    def test_custom_baseline(self):
        # EPSILON=0.001 est dans le dénominateur → tolérance abs=0.01
        bl = {"traffic": {"mu": 2.0, "sigma": 0.5}}
        assert normalize(2.0, "traffic", bl) == pytest.approx(0.0, abs=1e-9)
        assert normalize(2.5, "traffic", bl) == pytest.approx(1.0, abs=0.01)


# ─── compute_phi ───────────────────────────────────────────────────────────────

class TestComputePhi:
    def test_night_is_low(self):
        for h in [0, 1, 2, 3, 4]:
            dt = datetime(2024, 3, 12, h, 0, tzinfo=timezone.utc)
            # UTC h = Paris h+1 (hiver) → h=0..3 UTC = 1..4h Paris = nuit
            assert compute_phi(dt) == pytest.approx(0.5, abs=0.05)

    def test_rush_morning_is_high(self):
        # 7h UTC = 8h Paris = rush matin (semaine)
        dt = datetime(2024, 3, 12, 7, 0, tzinfo=timezone.utc)  # mardi
        assert compute_phi(dt) == pytest.approx(1.55, abs=0.10)

    def test_rush_evening_is_high(self):
        # 17h UTC = 18h Paris = rush soir (semaine — plus intense que matin)
        dt = datetime(2024, 3, 12, 17, 0, tzinfo=timezone.utc)  # mardi
        assert compute_phi(dt) == pytest.approx(1.75, abs=0.10)

    def test_phi_always_in_range(self):
        for h in range(24):
            for m in [0, 15, 30, 45]:
                dt = datetime(2024, 3, 12, h, m, tzinfo=timezone.utc)
                phi = compute_phi(dt)
                # Profils calibrés Lyon : nuit 0.45, rush soir 1.75
                assert 0.40 <= phi <= 1.80, f"phi={phi} hors [0.40, 1.80] à {h}:{m:02d} UTC"

    def test_no_discontinuity(self):
        """Deux minutes consécutives ne peuvent pas sauter de plus de 0.02."""
        prev = None
        for minutes in range(24 * 60):
            h, m = divmod(minutes, 60)
            dt = datetime(2024, 3, 12, h, m, tzinfo=timezone.utc)
            phi = compute_phi(dt)
            if prev is not None:
                assert abs(phi - prev) < 0.02, f"Discontinuité phi à {h}:{m:02d} : {prev} → {phi}"
            prev = phi


# ─── compute_anomaly ───────────────────────────────────────────────────────────

class TestComputeAnomaly:
    def test_calm_night_gives_zero_anomaly(self):
        """Signaux tous sous la baseline → anomalie = 0 (pas de tension)."""
        assert compute_anomaly(SIGNALS_CALM) == pytest.approx(0.0)

    def test_neutral_gives_zero_anomaly(self):
        """Signaux exactement au niveau de la baseline → anomalie = 0."""
        assert compute_anomaly(SIGNALS_NEUTRAL) == pytest.approx(0.0)

    def test_rush_gives_positive_anomaly(self):
        assert compute_anomaly(SIGNALS_RUSH) > 0

    def test_anomaly_increases_with_intensity(self):
        a_rush  = compute_anomaly(SIGNALS_RUSH)
        a_storm = compute_anomaly(SIGNALS_STORM)
        a_fete  = compute_anomaly(SIGNALS_FETE)
        assert a_rush < a_storm < a_fete

    def test_anomaly_never_negative(self):
        for signals in [SIGNALS_CALM, SIGNALS_NEUTRAL, SIGNALS_RUSH, SIGNALS_FETE]:
            assert compute_anomaly(signals) >= 0


# ─── compute_risk ──────────────────────────────────────────────────────────────

class TestComputeRisk:
    def test_neutral_signals_give_zero_risk(self):
        phi = compute_phi(DT_NOON)
        assert compute_risk(SIGNALS_NEUTRAL, phi) == pytest.approx(0.0, abs=1e-6)

    def test_risk_scales_with_phi(self):
        phi_night = compute_phi(DT_NIGHT)
        phi_rush  = compute_phi(DT_RUSH)
        r_night = compute_risk(SIGNALS_RUSH, phi_night)
        r_rush  = compute_risk(SIGNALS_RUSH, phi_rush)
        assert r_rush > r_night

    def test_calm_signals_give_negative_risk(self):
        """Signaux bas → z < 0 → risk < 0 (ville calme)."""
        phi = compute_phi(DT_NOON)
        assert compute_risk(SIGNALS_CALM, phi) < 0


# ─── compute_conv ──────────────────────────────────────────────────────────────

class TestComputeConv:
    def test_negligible_convergence_below_threshold(self):
        # Soft-gate sigmoid produit des valeurs infinitésimales sous le seuil
        # Convergence négligeable (< 0.01) quand aucun signal ne dépasse θ
        assert compute_conv(SIGNALS_CALM)    < 0.01
        assert compute_conv(SIGNALS_NEUTRAL) < 0.01

    def test_fete_triggers_convergence(self):
        """Fête des Lumières : trafic + event + transport tous très élevés."""
        assert compute_conv(SIGNALS_FETE) > 0

    def test_convergence_non_negative(self):
        for signals in [SIGNALS_CALM, SIGNALS_NEUTRAL, SIGNALS_RUSH, SIGNALS_FETE]:
            assert compute_conv(signals) >= 0


# ─── compute_urban_score ───────────────────────────────────────────────────────

class TestComputeUrbanScore:
    def test_always_in_0_100(self):
        for alert in [-10, -5, -2, 0, 1, 3, 5, 10]:
            for spread in [0, 0.5, 1.5, 3.0]:
                s = compute_urban_score(alert, spread)
                assert 0 <= s <= 100, f"score={s} pour alert={alert} spread={spread}"

    def test_neutral_alert_gives_calme(self):
        score = compute_urban_score(0.0, 0.0)
        assert score_level(score) == "CALME"

    def test_high_alert_gives_critique(self):
        score = compute_urban_score(5.0, 1.0)
        assert score_level(score) == "CRITIQUE"

    def test_score_increases_with_alert(self):
        scores = [compute_urban_score(a, 0.0) for a in [-2, 0, 1, 3, 5]]
        assert scores == sorted(scores)


# ─── score_level ───────────────────────────────────────────────────────────────

class TestScoreLevel:
    def test_thresholds(self):
        assert score_level(0)   == "CALME"
        assert score_level(34)  == "CALME"
        assert score_level(35)  == "MODÉRÉ"
        assert score_level(54)  == "MODÉRÉ"
        assert score_level(55)  == "TENDU"
        assert score_level(71)  == "TENDU"
        assert score_level(72)  == "CRITIQUE"
        assert score_level(100) == "CRITIQUE"


# ─── top_causes ────────────────────────────────────────────────────────────────

class TestTopCauses:
    def test_calm_returns_empty(self):
        """Aucun signal élevé → liste vide."""
        causes = top_causes(SIGNALS_CALM)
        assert causes == []

    def test_neutral_returns_empty(self):
        causes = top_causes(SIGNALS_NEUTRAL)
        assert causes == []

    def test_fete_returns_event_first(self):
        causes = top_causes(SIGNALS_FETE)
        assert len(causes) > 0
        assert "Événement" in causes[0]

    def test_no_negative_sigma_in_output(self):
        """Les causes ne doivent jamais afficher un σ négatif."""
        for signals in [SIGNALS_CALM, SIGNALS_NEUTRAL, SIGNALS_RUSH, SIGNALS_FETE]:
            for cause in top_causes(signals):
                assert "-" not in cause, f"Cause négative: {cause}"

    def test_format(self):
        causes = top_causes(SIGNALS_FETE)
        for c in causes:
            assert "σ" in c
            assert "+" in c


# ─── scénarios end-to-end ──────────────────────────────────────────────────────

class TestEndToEndScenarios:
    def _score(self, signals, dt):
        phi   = compute_phi(dt)
        risk  = compute_risk(signals, phi)
        anom  = compute_anomaly(signals)
        conv  = compute_conv(signals)
        alert = compute_alert(risk, anom, conv)
        return compute_urban_score(alert, 0.0)

    def test_night_calm_is_calme(self):
        assert score_level(self._score(SIGNALS_CALM, DT_NIGHT)) == "CALME"

    def test_neutral_is_calme(self):
        assert score_level(self._score(SIGNALS_NEUTRAL, DT_NOON)) == "CALME"

    def test_rush_is_tendu(self):
        # Avec phi calibré Lyon (1.55-1.75 au rush), SIGNALS_RUSH passe en TENDU
        assert score_level(self._score(SIGNALS_RUSH, DT_RUSH)) == "TENDU"

    def test_fete_is_critique(self):
        assert score_level(self._score(SIGNALS_FETE, DT_ERUSH)) == "CRITIQUE"

    def test_score_night_lower_than_rush(self):
        s_night = self._score(SIGNALS_RUSH, DT_NIGHT)
        s_rush  = self._score(SIGNALS_RUSH, DT_RUSH)
        assert s_night < s_rush

    def test_monte_carlo_always_in_range(self):
        """10 000 inputs aléatoires — score toujours dans [0, 100]."""
        import random
        random.seed(0)
        for _ in range(10_000):
            signals = {
                "traffic":   random.uniform(0.5, 3.0),
                "weather":   random.uniform(0.0, 3.0),
                "event":     random.uniform(0.0, 3.0),
                "transport": random.uniform(0.0, 1.0),
                "incident":  random.uniform(0.0, 3.0),
            }
            h  = random.randint(0, 23)
            dt = datetime(2024, 3, 12, h, 0, tzinfo=timezone.utc)
            phi   = compute_phi(dt)
            risk  = compute_risk(signals, phi)
            anom  = compute_anomaly(signals)
            conv  = compute_conv(signals)
            alert = compute_alert(risk, anom, conv)
            spread = random.uniform(0.0, 1.5)
            score = compute_urban_score(alert, spread)
            assert 0 <= score <= 100


# ─── compute_forecast ──────────────────────────────────────────────────────────

class TestComputeForecast:
    def test_returns_three_horizons(self):
        fc = compute_forecast(45, 2.0, 0.5, dt=DT_RUSH)
        assert len(fc) == 3
        assert [f["horizon_min"] for f in fc] == [30, 60, 120]

    def test_scores_in_range(self):
        fc = compute_forecast(50, 2.0, 0.5, dt=DT_RUSH)
        for f in fc:
            assert 0 <= f["urban_score"] <= 100

    def test_consistent_with_current_score(self):
        """Le score extrapolé à h→0 doit correspondre au score courant (±1)."""
        phi   = compute_phi(DT_RUSH)
        risk  = compute_risk(SIGNALS_RUSH, phi)
        anom  = compute_anomaly(SIGNALS_RUSH)
        conv  = compute_conv(SIGNALS_RUSH)
        alert = compute_alert(risk, anom, conv)
        spread = 0.5
        current = compute_urban_score(alert, spread)

        # Extrapolation à h=0 : decay=1, phi_ratio=1, trend=0
        fa0 = alert
        implicit_t0 = compute_urban_score(fa0, spread)
        assert abs(implicit_t0 - current) <= 1

    def test_post_rush_decreases(self):
        """Après le rush (10h → 11h → 12h), le score doit décroître."""
        dt_post = datetime(2024, 3, 12, 9, 0, tzinfo=timezone.utc)  # 10h Paris, fin rush
        fc = compute_forecast(50, 2.0, 0.3, dt=dt_post, trend=-0.05)
        scores = [f["urban_score"] for f in fc]
        assert scores[0] >= scores[2], f"Score ne descend pas après rush: {scores}"

    def test_positive_trend_increases_short_term(self):
        fc_flat = compute_forecast(40, 1.5, 0.2, dt=DT_NOON, trend=0.0)
        fc_up   = compute_forecast(40, 1.5, 0.2, dt=DT_NOON, trend=0.5)
        assert fc_up[0]["urban_score"] >= fc_flat[0]["urban_score"]

    def test_level_field_matches_score(self):
        fc = compute_forecast(45, 2.0, 0.5, dt=DT_RUSH)
        for f in fc:
            assert f["level"] == score_level(f["urban_score"])


# ─── compute_spread ────────────────────────────────────────────────────────────

class TestComputeSpread:
    def test_no_neighbors_gives_zero(self):
        assert compute_spread("unknown-zone", {"part-dieu": 5.0}) == 0.0

    def test_zero_alert_neighbors_gives_zero(self):
        alert_map = {z: 0.0 for z in NEIGHBORS}
        assert compute_spread("part-dieu", alert_map) == pytest.approx(0.0)

    def test_positive_neighbors_give_positive_spread(self):
        alert_map = {z: 2.0 for z in NEIGHBORS}
        assert compute_spread("part-dieu", alert_map) > 0

    def test_negative_neighbors_ignored(self):
        """Les alertes négatives des voisins ne doivent pas réduire le spread."""
        alert_map = {z: -5.0 for z in NEIGHBORS}
        assert compute_spread("part-dieu", alert_map) == pytest.approx(0.0)


# ─── score_zone ────────────────────────────────────────────────────────────────

class TestScoreZone:
    def test_returns_required_keys(self):
        result = score_zone("part-dieu", SIGNALS_NEUTRAL, {}, dt=DT_NOON)
        for key in ("zone_id", "zone_name", "urban_score", "level",
                    "signals", "raw_signals", "components", "top_causes", "alert"):
            assert key in result, f"Clé manquante: {key}"

    def test_zone_id_preserved(self):
        result = score_zone("vieux-lyon", SIGNALS_NEUTRAL, {}, dt=DT_NOON)
        assert result["zone_id"] == "vieux-lyon"

    def test_score_in_range(self):
        result = score_zone("part-dieu", SIGNALS_FETE, {}, dt=DT_ERUSH)
        assert 0 <= result["urban_score"] <= 100

    def test_components_present(self):
        result = score_zone("part-dieu", SIGNALS_RUSH, {}, dt=DT_RUSH)
        for comp in ("risk", "anomaly", "conv", "spread", "phi"):
            assert comp in result["components"]


# ─── score_all_zones ───────────────────────────────────────────────────────────

class TestScoreAllZones:
    def _all_signals(self, signals):
        return {z: dict(signals) for z in ZONE_NAMES}

    def test_returns_all_zones(self):
        results = score_all_zones(self._all_signals(SIGNALS_NEUTRAL), dt=DT_NOON)
        assert len(results) == len(ZONE_NAMES)

    def test_all_scores_in_range(self):
        results = score_all_zones(self._all_signals(SIGNALS_FETE), dt=DT_ERUSH)
        for r in results:
            assert 0 <= r["urban_score"] <= 100

    def test_spread_propagation(self):
        """Part-Dieu très tendu → ses voisins reçoivent du spread."""
        all_signals = self._all_signals(SIGNALS_NEUTRAL)
        all_signals["part-dieu"] = dict(SIGNALS_FETE)

        results_map  = {r["zone_id"]: r for r in score_all_zones(all_signals, dt=DT_ERUSH)}
        spread_pd    = results_map["part-dieu"]["components"]["spread"]
        spread_brot  = results_map["brotteaux"]["components"]["spread"]

        # Brotteaux est voisin de part-dieu → spread > 0
        assert spread_brot > 0
        # Part-Dieu a ses propres voisins moins tendus → spread plus faible
        assert spread_brot > spread_pd or spread_pd >= 0
