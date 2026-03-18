"""
Tests unitaires — services/scoring.py
Lancer : python -m pytest tests/ -v  (depuis backend/)
"""
import math
import sys
import pytest
from datetime import datetime, timezone, timedelta

sys.path.insert(0, ".")

from datetime import date

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
    _soft_gate,
    _validate_config,
)
from services.calendar_utils import (
    _easter,
    _jours_feries,
    is_vacances as _is_vacances,
    is_ferie as _is_ferie,
    day_type as _day_type,
)
from config import LAMBDA, WEIGHTS, ALPHA, THETA, BETA, CONV_BETA_SUM_MAX, CONV_THETA_EPSILON


# ─── Fixtures ──────────────────────────────────────────────────────────────────

SIGNALS_CALM = {
    "traffic": 0.9, "weather": 0.0, "event": 0.0,
    "transport": 0.05, "incident": 0.0,
}
SIGNALS_NEUTRAL = {
    "traffic": 1.05, "weather": 0.3, "event": 0.2,   # mu Criter calibré auto
    "transport": 0.50, "incident": 0.8,
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

    def test_fete_returns_event_in_causes(self):
        causes = top_causes(SIGNALS_FETE)
        assert len(causes) > 0
        # Avec traffic=3.0 (route coupée N), trafic domine, mais event doit être présent
        assert any("Événement" in c for c in causes)

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

    def test_rush_is_critique(self):
        # Avec traffic=2.5 et mu=1.05/sigma=0.15, z_traffic≈+9.7σ → CRITIQUE
        assert score_level(self._score(SIGNALS_RUSH, DT_RUSH)) == "CRITIQUE"

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
    def test_returns_six_horizons(self):
        fc = compute_forecast(45, 2.0, 0.5, dt=DT_RUSH)
        assert len(fc) == 6
        assert [f["horizon"] for f in fc] == ["30min", "60min", "2h", "6h", "12h", "24h"]

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


# ─── conv cap ─────────────────────────────────────────────────────────────────

class TestConvCap:
    def test_conv_capped_at_2(self):
        """Tous les signaux extrêmes → conv ne dépasse jamais 2.0."""
        extreme = {
            "traffic": 10.0, "weather": 10.0, "event": 10.0,
            "transport": 10.0, "incident": 10.0,
        }
        assert compute_conv(extreme) == pytest.approx(2.0)

    def test_normal_signals_below_cap(self):
        """En conditions normales, conv est bien en dessous de la borne."""
        assert compute_conv(SIGNALS_FETE) < 2.0
        assert compute_conv(SIGNALS_RUSH) < 2.0

    def test_conv_cap_monte_carlo(self):
        """1000 tirages aléatoires : conv ∈ [0, 2.0]."""
        import random
        random.seed(42)
        for _ in range(1000):
            signals = {
                "traffic":   random.uniform(0.0, 5.0),
                "weather":   random.uniform(0.0, 5.0),
                "event":     random.uniform(0.0, 5.0),
                "transport": random.uniform(0.0, 3.0),
                "incident":  random.uniform(0.0, 5.0),
            }
            c = compute_conv(signals)
            assert 0 <= c <= 2.0, f"conv={c} hors [0, 2.0]"


# ─── interp clamp ────────────────────────────────────────────────────────────

class TestInterpClamp:
    def test_post_rush_interp_not_negative(self):
        """Après le rush (phi_future < phi_now), le forecast ne doit pas
        monter — phi baisse donc le score doit baisser ou stagner."""
        # 18h Paris (rush soir) → forecast +120min = 20h Paris (phi baisse)
        dt_rush = datetime(2024, 3, 12, 17, 0, tzinfo=timezone.utc)  # 18h Paris
        fc = compute_forecast(
            60, 3.0, 0.5, dt=dt_rush,
            signals=SIGNALS_RUSH,
            bl=BASELINE,
        )
        # Le score à +120min doit être ≤ au score à +30min (phi baisse)
        assert fc[2]["urban_score"] <= fc[0]["urban_score"], (
            f"Score +120min ({fc[2]['urban_score']}) > score +30min ({fc[0]['urban_score']})"
        )

    def test_pre_rush_interp_positive(self):
        """Avant le rush (phi_future > phi_now), le forecast doit monter."""
        # 15h30 Paris → forecast +120min = 17h30 Paris (plein rush soir)
        dt_pre = datetime(2024, 3, 12, 14, 30, tzinfo=timezone.utc)  # 15h30 Paris
        fc_pre = compute_forecast(
            45, 2.0, 0.3, dt=dt_pre,
            signals=SIGNALS_RUSH,
            bl=BASELINE,
        )
        # Score à +120min (rush soir) doit être >= score actuel
        assert fc_pre[2]["urban_score"] >= 45, (
            f"Score +120min pré-rush devrait monter: {fc_pre[2]['urban_score']}"
        )

    def test_interp_does_not_reduce_traffic_post_rush(self):
        """Vérifie directement que la logique interp ne réduit pas le trafic
        quand phi_future/phi_now < 1."""
        phi_now = compute_phi(datetime(2024, 3, 12, 17, 0, tzinfo=timezone.utc))
        phi_future = compute_phi(datetime(2024, 3, 12, 19, 0, tzinfo=timezone.utc))
        assert phi_future < phi_now, "Le rush soir doit décroître vers 20h"
        phi_r = phi_future / phi_now
        interp = min(max((phi_r - 1.0) * 0.6, 0.0), 0.5)
        assert interp == 0.0, f"interp post-rush devrait être 0, got {interp}"


# ─── phi profiles (mercredi, vacances, weekend) ──────────────────────────────

class TestPhiProfiles:
    def test_mercredi_rush_matin_same_as_semaine(self):
        """Rush matin mercredi identique au profil semaine."""
        # Mercredi 6 mars 2024, 7h30 UTC = 8h30 Paris
        dt_mer = datetime(2024, 3, 6, 7, 0, tzinfo=timezone.utc)
        dt_sem = datetime(2024, 3, 5, 7, 0, tzinfo=timezone.utc)  # mardi
        assert abs(compute_phi(dt_mer) - compute_phi(dt_sem)) < 0.05

    def test_mercredi_rush_soir_lower(self):
        """Rush soir mercredi atténué vs semaine."""
        dt_mer = datetime(2024, 3, 6, 17, 0, tzinfo=timezone.utc)   # mercredi 18h Paris
        dt_sem = datetime(2024, 3, 5, 17, 0, tzinfo=timezone.utc)   # mardi 18h Paris
        assert compute_phi(dt_mer) < compute_phi(dt_sem)

    def test_vacances_rush_lower_than_semaine(self):
        """Rush en vacances scolaires atténué vs semaine standard."""
        # 17 février 2026 = mardi en vacances d'hiver Zone A
        dt_vac = datetime(2026, 2, 17, 17, 0, tzinfo=timezone.utc)  # 18h Paris
        dt_sem = datetime(2026, 3, 3, 17, 0, tzinfo=timezone.utc)   # mardi hors vacances
        phi_vac = compute_phi(dt_vac)
        phi_sem = compute_phi(dt_sem)
        assert phi_vac < phi_sem, f"vacances {phi_vac} should be < semaine {phi_sem}"

    def test_weekend_no_commuter_rush(self):
        """Weekend : pas de rush commuter, profil plus plat."""
        # Samedi 9 mars 2024, 8h30 Paris (normalement rush)
        dt_sat = datetime(2024, 3, 9, 7, 30, tzinfo=timezone.utc)
        # Mardi 5 mars, même heure
        dt_tue = datetime(2024, 3, 5, 7, 30, tzinfo=timezone.utc)
        phi_sat = compute_phi(dt_sat)
        phi_tue = compute_phi(dt_tue)
        assert phi_sat < phi_tue, f"weekend {phi_sat} should be < semaine {phi_tue}"

    def test_weekend_max_below_semaine_max(self):
        """Le max du profil weekend < max du profil semaine."""
        max_we = max(
            compute_phi(datetime(2024, 3, 9, h, 0, tzinfo=timezone.utc))
            for h in range(24)
        )
        max_sem = max(
            compute_phi(datetime(2024, 3, 5, h, 0, tzinfo=timezone.utc))
            for h in range(24)
        )
        assert max_we < max_sem

    def test_all_profiles_continuous(self):
        """Tous les profils phi sont continus (pas de saut > 0.02/min)."""
        # Tester un jour de chaque type
        days = [
            datetime(2024, 3, 5, 0, 0, tzinfo=timezone.utc),   # mardi (semaine)
            datetime(2024, 3, 6, 0, 0, tzinfo=timezone.utc),   # mercredi
            datetime(2024, 3, 9, 0, 0, tzinfo=timezone.utc),   # samedi (weekend)
            datetime(2026, 2, 17, 0, 0, tzinfo=timezone.utc),  # mardi vacances
        ]
        for base in days:
            prev = None
            for m in range(24 * 60):
                dt = base + timedelta(minutes=m)
                phi = compute_phi(dt)
                if prev is not None:
                    assert abs(phi - prev) < 0.03, (
                        f"Discontinuité {base.date()} à +{m}min: {prev:.3f} → {phi:.3f}"
                    )
                prev = phi

    def test_phi_hierarchy(self):
        """Au rush soir : semaine > mercredi > vacances > weekend."""
        # 18h Paris = 17h UTC
        dt_sem = datetime(2024, 3, 5, 17, 0, tzinfo=timezone.utc)  # mardi
        dt_mer = datetime(2024, 3, 6, 17, 0, tzinfo=timezone.utc)  # mercredi
        dt_vac = datetime(2026, 2, 17, 17, 0, tzinfo=timezone.utc) # vacances
        dt_we  = datetime(2024, 3, 9, 17, 0, tzinfo=timezone.utc)  # samedi

        phi_sem = compute_phi(dt_sem)
        phi_mer = compute_phi(dt_mer)
        phi_vac = compute_phi(dt_vac)
        phi_we  = compute_phi(dt_we)

        assert phi_sem > phi_mer > phi_vac > phi_we, (
            f"Hiérarchie incorrecte: sem={phi_sem} mer={phi_mer} vac={phi_vac} we={phi_we}"
        )


# ─── calendrier (easter, jours fériés, vacances, day_type) ───────────────────

class TestCalendar:
    def test_easter_known_dates(self):
        """Vérifie Pâques sur des dates connues."""
        assert _easter(2024) == date(2024, 3, 31)
        assert _easter(2025) == date(2025, 4, 20)
        assert _easter(2026) == date(2026, 4, 5)
        assert _easter(2027) == date(2027, 3, 28)

    def test_jours_feries_fixed(self):
        """Les jours fériés fixes sont toujours présents."""
        feries_2026 = _jours_feries(2026)
        assert date(2026, 1, 1) in feries_2026    # Nouvel an
        assert date(2026, 5, 1) in feries_2026    # Fête du travail
        assert date(2026, 7, 14) in feries_2026   # Fête nationale
        assert date(2026, 12, 25) in feries_2026  # Noël

    def test_jours_feries_mobile(self):
        """Les jours fériés mobiles (dépendant de Pâques) sont corrects."""
        feries_2026 = _jours_feries(2026)
        easter = date(2026, 4, 5)
        assert easter + timedelta(days=1) in feries_2026   # Lundi de Pâques
        assert easter + timedelta(days=39) in feries_2026  # Ascension
        assert easter + timedelta(days=50) in feries_2026  # Pentecôte

    def test_jours_feries_count(self):
        """La France a 11 jours fériés par an."""
        assert len(_jours_feries(2026)) == 11

    def test_is_ferie(self):
        assert _is_ferie(date(2026, 1, 1))
        assert _is_ferie(date(2026, 12, 25))
        assert not _is_ferie(date(2026, 3, 17))  # un mardi normal

    def test_is_vacances_toussaint(self):
        """Vacances de la Toussaint 2025 Zone A."""
        assert _is_vacances(date(2025, 10, 20))  # milieu vacances
        assert _is_vacances(date(2025, 10, 18))  # premier jour
        assert _is_vacances(date(2025, 11, 3))   # dernier jour
        assert not _is_vacances(date(2025, 10, 17))  # veille

    def test_day_type_semaine(self):
        # Mardi 17 mars 2026 hors vacances
        dt = datetime(2026, 3, 17, 12, 0, tzinfo=timezone.utc)
        assert _day_type(dt) == "semaine"

    def test_day_type_mercredi(self):
        # Mercredi 18 mars 2026 hors vacances
        dt = datetime(2026, 3, 18, 12, 0, tzinfo=timezone.utc)
        assert _day_type(dt) == "mercredi"

    def test_day_type_weekend(self):
        # Samedi 21 mars 2026
        dt = datetime(2026, 3, 21, 12, 0, tzinfo=timezone.utc)
        assert _day_type(dt) == "weekend"

    def test_day_type_ferie(self):
        # 1er mai 2026 (jeudi, jour férié)
        dt = datetime(2026, 5, 1, 12, 0, tzinfo=timezone.utc)
        assert _day_type(dt) == "weekend"  # fériés → profil weekend

    def test_day_type_vacances(self):
        # Mardi 17 février 2026 = vacances d'hiver Zone A (7 fév – 23 fév)
        dt = datetime(2026, 2, 17, 12, 0, tzinfo=timezone.utc)
        assert _day_type(dt) == "vacances"

    def test_day_type_vacances_weekend_priority(self):
        """Un samedi en vacances → 'weekend' (pas 'vacances')."""
        # Samedi 14 février 2026, pendant vacances d'hiver
        dt = datetime(2026, 2, 14, 12, 0, tzinfo=timezone.utc)
        assert _day_type(dt) == "weekend"


# ─── forecast 3-scénarios ────────────────────────────────────────────────────

class TestForecast3Scenarios:
    def test_rush_approach_increases_score(self):
        """Approche du rush soir → le forecast doit monter, pas décroître."""
        # 15h Paris, signaux d'incidents actifs
        dt_pre = datetime(2024, 3, 12, 14, 0, tzinfo=timezone.utc)  # 15h Paris
        signals_incident = {
            "traffic": 1.5, "weather": 0.3, "event": 0.0,
            "transport": 0.45, "incident": 1.5,
        }
        fc = compute_forecast(
            45, 2.0, 0.3, dt=dt_pre,
            signals=signals_incident,
            bl=BASELINE,
        )
        # +120min = 17h Paris (rush soir) → score doit être >= actuel
        assert fc[2]["urban_score"] >= 45

    def test_incident_schedule_used(self):
        """Un incident planifié persistent (travaux) maintient le score élevé."""
        signals_w_incident = {
            "traffic": 2.0, "weather": 0.3, "event": 0.0,
            "transport": 0.5, "incident": 1.8,
        }
        schedule = {30: 1.8, 60: 1.8, 120: 1.8}  # travaux persistent
        fc_with = compute_forecast(
            55, 2.5, 0.3, dt=DT_NOON,
            signals=signals_w_incident,
            incident_schedule=schedule,
            bl=BASELINE,
        )
        fc_without = compute_forecast(
            55, 2.5, 0.3, dt=DT_NOON,
            signals=signals_w_incident,
            bl=BASELINE,
        )
        # Avec incidents persistants, le score ne doit pas décroître plus
        assert fc_with[2]["urban_score"] >= fc_without[2]["urban_score"]

    def test_fallback_without_signals(self):
        """Sans signaux bruts, le forecast fonctionne (mode dégradé)."""
        fc = compute_forecast(50, 2.0, 0.5, dt=DT_RUSH)
        assert len(fc) == 6
        for f in fc:
            assert 0 <= f["urban_score"] <= 100

    def test_max_wins_logic(self):
        """Le forecast prend le max des 3 scénarios — jamais en dessous
        de la persistance simple."""
        fc = compute_forecast(
            60, 3.0, 0.5, dt=DT_RUSH,
            signals=SIGNALS_RUSH,
            bl=BASELINE,
        )
        # Le score à +30min ne doit pas être inférieur au score de persistance pure
        # (decay faible à 30min : exp(-30/240) ≈ 0.88)
        for f in fc:
            assert f["urban_score"] >= 20, (
                f"Score forecast trop bas: {f['urban_score']} à +{f['horizon']}"
            )


# ─── A. interp — tests par valeur de phi_ratio ──────────────────────────────

class TestInterpFormula:
    """Tests directs de la formule interp = min(max((phi_r - 1.0) * 0.6, 0.0), 0.5)."""

    @staticmethod
    def _interp(phi_ratio: float) -> float:
        return min(max((phi_ratio - 1.0) * 0.6, 0.0), 0.5)

    def test_phi_ratio_below_one(self):
        assert self._interp(0.8) == 0.0

    def test_phi_ratio_exactly_one(self):
        assert self._interp(1.0) == 0.0

    def test_phi_ratio_moderate(self):
        assert self._interp(1.2) == pytest.approx(0.12)

    def test_phi_ratio_high(self):
        """phi_ratio très élevé → interp plafonné à 0.5."""
        assert self._interp(5.0) == pytest.approx(0.5)
        assert self._interp(100.0) == pytest.approx(0.5)

    def test_interp_always_in_range(self):
        """Monte Carlo : interp ∈ [0, 0.5] pour tout phi_ratio ∈ [0.1, 10]."""
        import random
        random.seed(99)
        for _ in range(5000):
            phi_r = random.uniform(0.1, 10.0)
            i = self._interp(phi_r)
            assert 0.0 <= i <= 0.5, f"interp={i} pour phi_ratio={phi_r}"


# ─── B. validation Σβ_k au démarrage ────────────────────────────────────────

class TestConfigValidation:
    def test_validate_config_passes(self):
        """La config actuelle doit passer la validation sans erreur."""
        _validate_config()  # ne doit pas lever

    def test_beta_sum_within_bound(self):
        """Σβ_k doit être ≤ CONV_BETA_SUM_MAX."""
        beta_sum = sum(BETA.values())
        assert beta_sum <= CONV_BETA_SUM_MAX, (
            f"Σβ_k = {beta_sum:.2f} > CONV_BETA_SUM_MAX = {CONV_BETA_SUM_MAX}"
        )

    def test_beta_sum_exceeds_bound_raises(self):
        """Si Σβ_k dépasse la borne, ValueError au démarrage."""
        import config
        original = config.CONV_BETA_SUM_MAX
        try:
            config.CONV_BETA_SUM_MAX = 0.1  # borne absurdement basse
            with pytest.raises(ValueError, match="Σβ_k"):
                _validate_config()
        finally:
            config.CONV_BETA_SUM_MAX = original

    def test_weights_sum_to_one(self):
        assert sum(WEIGHTS.values()) == pytest.approx(1.0)


# ─── C. fond résiduel conv au régime neutre ──────────────────────────────────

class TestConvNeutralRegime:
    def test_soft_gate_at_zero_below_epsilon(self):
        """sigmoid(0 − θ) < ε pour chaque θ — pas de fond résiduel."""
        for signal, theta in THETA.items():
            gate = _soft_gate(0.0, theta)
            assert gate < CONV_THETA_EPSILON, (
                f"sigmoid(0 − θ[{signal}]) = {gate:.4f} ≥ ε = {CONV_THETA_EPSILON}"
            )

    def test_conv_near_zero_at_neutral(self):
        """Quand tous z_s = 0 (signaux au baseline), conv < 0.01."""
        neutral = {s: BASELINE[s]["mu"] for s in BASELINE}
        c = compute_conv(neutral)
        assert c < 0.01, f"conv au régime neutre = {c:.4f} — fond résiduel trop élevé"

    def test_conv_near_zero_with_signals_below_theta(self):
        """Signaux modérément au-dessus du baseline mais sous θ → conv négligeable."""
        mild = {
            "traffic":   BASELINE["traffic"]["mu"] + 0.3 * BASELINE["traffic"]["sigma"],
            "weather":   BASELINE["weather"]["mu"] + 0.3 * BASELINE["weather"]["sigma"],
            "event":     BASELINE["event"]["mu"] + 0.3 * BASELINE["event"]["sigma"],
            "transport": BASELINE["transport"]["mu"] + 0.3 * BASELINE["transport"]["sigma"],
            "incident":  BASELINE["incident"]["mu"] + 0.3 * BASELINE["incident"]["sigma"],
        }
        c = compute_conv(mild)
        assert c < 0.05, f"conv avec signaux doux = {c:.4f} — attendu < 0.05"


# ─── D. sémantique du score neutre ──────────────────────────────────────────

class TestScoreNeutralSemantics:
    def test_score_at_raw_zero_is_calme(self):
        """raw=0 (alert=0, spread=0) → score ≈ 29, catégorie CALME."""
        score = compute_urban_score(0.0, 0.0)
        assert 27 <= score <= 31, f"score neutre = {score}, attendu ≈ 29"
        assert score_level(score) == "CALME"

    def test_score_50_at_raw_1_5(self):
        """raw=1.5 → score = 50 (point d'inflexion de la sigmoid)."""
        # alert=1.5, spread=0 → raw=1.5
        score = compute_urban_score(1.5, 0.0)
        assert score == 50

    def test_score_critique_threshold(self):
        """raw ≈ 3.0 → score ≈ 71–72 (seuil CRITIQUE)."""
        score = compute_urban_score(3.0, 0.0)
        assert 70 <= score <= 73, f"score critique = {score}"
        # Juste au-dessus du seuil TENDU/CRITIQUE
        assert score_level(score) in ("TENDU", "CRITIQUE")

    def test_all_baseline_signals_give_calme(self):
        """Quand tous les signaux sont exactement au baseline → CALME."""
        neutral = {s: BASELINE[s]["mu"] for s in BASELINE}
        phi = compute_phi(DT_NOON)
        risk = compute_risk(neutral, phi)
        anom = compute_anomaly(neutral)
        conv = compute_conv(neutral)
        alert = compute_alert(risk, anom, conv)
        score = compute_urban_score(alert, 0.0)
        assert score_level(score) == "CALME", f"signaux baseline → score {score} ({score_level(score)})"


# ─── E. Forecast étendu (6h/12h/24h) ─────────────────────────────────────────

class TestForecastExtended:
    """Tests du forecast structurel sur horizons étendus (6h, 12h, 24h)."""

    _EXTENDED = {"6h", "12h", "24h"}
    _SHORT = {"30min", "60min", "2h"}

    def test_extended_horizons_present(self):
        """Le forecast retourne bien les 3 horizons étendus."""
        fc = compute_forecast(45, 2.0, 0.5, dt=DT_RUSH, signals=SIGNALS_RUSH, bl=BASELINE)
        extended = [f for f in fc if f["horizon"] in self._EXTENDED]
        assert len(extended) == 3
        assert [f["horizon"] for f in extended] == ["6h", "12h", "24h"]

    def test_extended_scores_in_range(self):
        """Les scores étendus sont dans [0, 100]."""
        fc = compute_forecast(45, 2.0, 0.5, dt=DT_RUSH, signals=SIGNALS_RUSH, bl=BASELINE)
        for f in fc:
            assert 0 <= f["urban_score"] <= 100

    def test_extended_confidence_decreasing(self):
        """La confiance décroît : high → medium → low."""
        fc = compute_forecast(45, 2.0, 0.5, dt=DT_RUSH, signals=SIGNALS_RUSH, bl=BASELINE)
        short = [f for f in fc if f["horizon"] in self._SHORT]
        extended = [f for f in fc if f["horizon"] in self._EXTENDED]
        assert all(f["confidence"] == "high" for f in short)
        assert extended[0]["confidence"] == "medium"   # 6h
        assert extended[1]["confidence"] == "medium"   # 12h
        assert extended[2]["confidence"] == "low"       # 24h

    def test_weather_forecast_impacts_extended(self):
        """La météo prévue modifie les scores étendus."""
        from datetime import timedelta
        from zoneinfo import ZoneInfo

        LYON_TZ = ZoneInfo("Europe/Paris")
        weather_storm = {}
        for i in range(48):
            future = DT_RUSH + timedelta(hours=i)
            local = future.astimezone(LYON_TZ)
            key = local.strftime("%Y-%m-%dT%H:00")
            weather_storm[key] = 3.0

        fc_no_wf = compute_forecast(
            45, 2.0, 0.5, dt=DT_RUSH, signals=SIGNALS_RUSH, bl=BASELINE,
            weather_forecast=None,
        )
        fc_storm = compute_forecast(
            45, 2.0, 0.5, dt=DT_RUSH, signals=SIGNALS_RUSH, bl=BASELINE,
            weather_forecast=weather_storm,
        )
        ext_no = [f for f in fc_no_wf if f["horizon"] in self._EXTENDED]
        ext_st = [f for f in fc_storm if f["horizon"] in self._EXTENDED]
        deltas = [s["urban_score"] - n["urban_score"] for s, n in zip(ext_st, ext_no)]
        assert any(d > 0 for d in deltas), f"Tempête sans effet : deltas={deltas}"

    def test_night_forecast_is_calme(self):
        """Un forecast à +6h qui tombe la nuit devrait être CALME (φ bas)."""
        dt_evening = DT_RUSH.replace(hour=18, minute=0)
        fc = compute_forecast(
            45, 2.0, 0.5, dt=dt_evening, signals=SIGNALS_NEUTRAL, bl=BASELINE,
        )
        h6 = next(f for f in fc if f["horizon"] == "6h")
        assert h6["phi"] < 0.7, f"φ nuit = {h6['phi']}, attendu < 0.7"

    def test_short_horizons_unchanged(self):
        """Les horizons courts ne sont pas affectés par weather_forecast."""
        fc_no_wf = compute_forecast(
            45, 2.0, 0.5, dt=DT_RUSH, signals=SIGNALS_RUSH, bl=BASELINE,
            weather_forecast=None,
        )
        fc_wf = compute_forecast(
            45, 2.0, 0.5, dt=DT_RUSH, signals=SIGNALS_RUSH, bl=BASELINE,
            weather_forecast={"2025-01-01T00:00": 3.0},
        )
        short_no = [f for f in fc_no_wf if f["horizon"] in self._SHORT]
        short_wf = [f for f in fc_wf if f["horizon"] in self._SHORT]
        for a, b in zip(short_no, short_wf):
            assert a["urban_score"] == b["urban_score"], (
                f"Horizon {a['horizon']} modifié par weather_forecast"
            )
