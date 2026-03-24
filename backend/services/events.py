# services/events.py
# Signal event — Calendrier statique Lyon 2026
# Fallback propre en attendant une vraie source API événementielle sur Lyon

import logging
import math
from datetime import date, timedelta
from typing import Dict, List

from config import ZONE_CENTROIDS

log = logging.getLogger("service.events")

EVENT_RADIUS_KM = 1.2


def _days(start: str, end: str) -> List[date]:
    """Génère la liste des dates entre start et end inclus (format YYYY-MM-DD)."""
    s = date.fromisoformat(start)
    e = date.fromisoformat(end)
    return [s + timedelta(days=i) for i in range((e - s).days + 1)]


# ──────────────────────────────────────────────
# Calendrier statique Lyon 2026
# Sources : Office du Tourisme Lyon, Lyon Première, agenda.grandlyon.com
# ──────────────────────────────────────────────
STATIC_EVENTS: List[dict] = [
    # --- Q1 ---
    # hours = (start_hour, end_hour) — créneau d'activité de l'événement.
    # Utilisé par la simulation pré-événement (pas le scoring live).
    # ramp = heures d'arrivée/départ autour du créneau (afflux transport).
    {
        "name":   "Foire de Lyon (Eurexpo)",
        "dates":  _days("2026-03-20", "2026-03-30"),
        "zone":   "part-dieu",      # impact réel = transit (T3 tram, 80% visiteurs via Part-Dieu)
        "lat":    45.7605, "lng": 4.8597,  # Gare Part-Dieu (hub de transit vers Eurexpo)
        "weight": 1.2,              # réduit vs 1.5 : impact indirect (transit), pas direct (lieu)
        "hours":  (9, 19),          # salon pro/public journée
        "ramp":   2,
    },
    {
        "name":   "Lyon Urban Trail",
        "dates":  [date(2026, 3, 29)],
        "zone":   "vieux-lyon",     # départ Quai Fulchiron, arrivée Place Saint-Jean
        "lat":    45.7594, "lng": 4.8275,
        "weight": 1.2,
        "hours":  (7, 16),          # premier départ 7h (38km), arrivées jusqu'à ~16h
        "ramp":   1,
    },
    # --- OL Ligue 1 (Groupama Stadium, Décines) ---
    # Impact principal = transit Part-Dieu (T3 tram, gare TGV) + afflux centre-ville.
    # 55 000 spectateurs → saturation T3, bouchons A43/Bd périph, bars Presqu'île.
    {
        "name":   "OL — PSG (Ligue 1, Groupama Stadium)",
        "dates":  [date(2026, 4, 5)],
        "zone":   "part-dieu",
        "lat":    45.7605, "lng": 4.8597,   # Gare Part-Dieu (hub transit vers Décines)
        "weight": 1.8,                       # affiche majeure, 55k+ spectateurs
        "hours":  (21, 23),                  # coup d'envoi 21h00
        "ramp":   3,                         # fans arrivent dès 18h, départ jusqu'à 00h
    },
    {
        "name":   "OL — OM (Ligue 1, Groupama Stadium)",
        "dates":  [date(2026, 5, 10)],
        "zone":   "part-dieu",
        "lat":    45.7605, "lng": 4.8597,
        "weight": 1.8,
        "hours":  (15, 17),                  # coup d'envoi 15h00
        "ramp":   3,
    },
    {
        "name":   "OL — Saint-Étienne (Derby, Groupama Stadium)",
        "dates":  [date(2026, 3, 22)],
        "zone":   "part-dieu",
        "lat":    45.7605, "lng": 4.8597,
        "weight": 2.0,                       # derby = tension maximale
        "hours":  (17, 19),                  # coup d'envoi 17h00
        "ramp":   3,
    },
    # --- Q2 ---
    {
        "name":   "Quais du Polar",
        "dates":  _days("2026-04-03", "2026-04-05"),
        "zone":   "presquile",
        "lat":    45.7640, "lng": 4.8340,  # Hôtel de Ville / Palais de la Bourse
        "weight": 0.8,
        "hours":  (10, 22),         # festival littéraire journée + soirée
        "ramp":   1,
    },
    {
        "name":   "Nuits Sonores",
        "dates":  _days("2026-05-13", "2026-05-17"),
        "zone":   "confluence",
        "lat":    45.7364, "lng": 4.8150,  # La Sucrière, quai Rambaud
        "weight": 1.0,
        "hours":  (16, 23),         # Days 16h + Nuits 22h → couvert par 16-23
        "ramp":   2,
    },
    {
        "name":   "Les Intergalactiques",
        "dates":  _days("2026-06-05", "2026-06-07"),
        "zone":   "part-dieu",
        "lat":    45.7600, "lng": 4.8600,
        "weight": 0.8,
        "hours":  (14, 22),         # convention SF après-midi + soirée
        "ramp":   1,
    },
    {
        "name":   "Fête de la Musique",
        "dates":  [date(2026, 6, 21)],
        "zone":   "presquile",
        "lat":    45.7600, "lng": 4.8350,
        "weight": 1.0,
        "hours":  (17, 23),         # concerts en plein air fin d'après-midi → nuit
        "ramp":   1,
    },
    {
        "name":   "Lyon Street Food Festival",
        "dates":  _days("2026-06-11", "2026-06-14"),
        "zone":   "confluence",     # Grandes Locos, La Mulatière (nearest zone)
        "lat":    45.7212, "lng": 4.8159,
        "weight": 0.8,
        "hours":  (11, 23),         # food festival midi → soirée
        "ramp":   1,
    },
    # ── Nuits de Fourvière 2026 — 80e édition (28 mai – 25 juillet) ──────
    # Entrées par concert/spectacle — remplace l'ancienne entrée "saison" unique.
    # Grand Théâtre (~4500 pl.) + Odéon (~1100 pl.) : coords (45.7622, 4.8200)
    # Poids = notoriété × jauge × imprévisibilité foule :
    #   S=1.8 (headliner intl sold-out)  A=1.5 (headliner majeur/sécu-sensible)
    #   A-=1.3 (star nationale forte)    B=1.0 (bon headliner)
    #   C+=0.8 (samedis festifs/électro) C=0.7 (thématiques/world)
    #   D=0.5 (niche/danse/cirque)
    # Sources : nuitsdefourviere.com, infoconcert.com, sortiraparis.com, grandlyon.com
    #
    # --- Ouverture ---
    {
        "name":   "NdF — Circa « Revoir les étoiles » (ouverture)",
        "dates":  _days("2026-05-28", "2026-05-30"),
        "zone":   "fourviere",
        "lat":    45.7622, "lng": 4.8200,
        "weight": 0.5,
        "hours":  (20, 22),
        "ramp":   1,
    },
    {
        "name":   "NdF — Radio Live (Musée des Confluences)",
        "dates":  _days("2026-05-30", "2026-05-31"),
        "zone":   "confluence",
        "lat":    45.7329, "lng": 4.8183,
        "weight": 0.5,
        "hours":  (18, 22),
        "ramp":   1,
    },
    # --- Juin — Grand Théâtre ---
    {
        "name":   "NdF — MC Solaar & Youssoupha",
        "dates":  [date(2026, 6, 2)],
        "zone":   "fourviere",
        "lat":    45.7622, "lng": 4.8200,
        "weight": 1.0,            # hip-hop français, création unique
        "hours":  (21, 23),
        "ramp":   2,
    },
    {
        "name":   "NdF — Bertrand Belin / Yaël Naïm",
        "dates":  [date(2026, 6, 3)],
        "zone":   "fourviere",
        "lat":    45.7622, "lng": 4.8200,
        "weight": 0.7,            # chanson française, public modéré
        "hours":  (21, 23),
        "ramp":   1,
    },
    {
        "name":   "NdF — Little Simz",
        "dates":  [date(2026, 6, 4)],
        "zone":   "fourviere",
        "lat":    45.7622, "lng": 4.8200,
        "weight": 1.5,            # UK rapper, Mercury Prize, 4500 pl.
        "hours":  (20, 23),
        "ramp":   2,
    },
    {
        "name":   "NdF — Gaël Faye + Pat Kalla",
        "dates":  [date(2026, 6, 5)],
        "zone":   "fourviere",
        "lat":    45.7622, "lng": 4.8200,
        "weight": 1.0,            # rap/world, Goncourt des lycéens
        "hours":  (21, 23),
        "ramp":   2,
    },
    {
        "name":   "NdF — Samedi Hexagone (Odezenne, Yelle, Melba)",
        "dates":  [date(2026, 6, 6)],
        "zone":   "fourviere",
        "lat":    45.7622, "lng": 4.8200,
        "weight": 0.8,            # samedi multi-artistes, format festif
        "hours":  (20, 23),
        "ramp":   2,
    },
    {
        "name":   "NdF — Les Dames du raï (Odéon)",
        "dates":  [date(2026, 6, 7)],
        "zone":   "fourviere",
        "lat":    45.7622, "lng": 4.8200,
        "weight": 0.5,            # Odéon ~1100 pl., world/raï
        "hours":  (20, 23),
        "ramp":   1,
    },
    {
        "name":   "NdF — Vanessa Paradis",
        "dates":  _days("2026-06-08", "2026-06-09"),
        "zone":   "fourviere",
        "lat":    45.7622, "lng": 4.8200,
        "weight": 1.3,            # star nationale, 2 soirs, 66 EUR
        "hours":  (21, 23),
        "ramp":   2,
    },
    {
        "name":   "NdF — Massive Attack",
        "dates":  _days("2026-06-10", "2026-06-11"),
        "zone":   "fourviere",
        "lat":    45.7622, "lng": 4.8200,
        "weight": 1.8,            # S-tier : headliner intl, sold-out, 85 EUR, 2 soirs
        "hours":  (21, 23),
        "ramp":   3,              # fans arrivent dès 18h30
    },
    {
        "name":   "NdF — Cesaria Evora Orchestra",
        "dates":  [date(2026, 6, 12)],
        "zone":   "fourviere",
        "lat":    45.7622, "lng": 4.8200,
        "weight": 0.7,            # hommage, world music
        "hours":  (21, 23),
        "ramp":   2,
    },
    {
        "name":   "NdF — Samedi Bal Masqué (Barbara Butch)",
        "dates":  [date(2026, 6, 13)],
        "zone":   "fourviere",
        "lat":    45.7622, "lng": 4.8200,
        "weight": 0.7,            # format bal, foule imprévisible mais petit prix
        "hours":  (21, 23),
        "ramp":   2,
    },
    {
        "name":   "NdF — Gravity & Other Myths (cirque)",
        "dates":  _days("2026-06-14", "2026-06-16"),
        "zone":   "fourviere",
        "lat":    45.7622, "lng": 4.8200,
        "weight": 0.5,
        "hours":  (20, 22),
        "ramp":   1,
    },
    {
        "name":   "NdF — Résurrection (Mahler / Opéra de Lyon)",
        "dates":  [date(2026, 6, 17)],
        "zone":   "fourviere",
        "lat":    45.7622, "lng": 4.8200,
        "weight": 0.5,            # classique, public discipliné
        "hours":  (21, 23),
        "ramp":   1,
    },
    {
        "name":   "NdF — Jack White",
        "dates":  [date(2026, 6, 18)],
        "zone":   "fourviere",
        "lat":    45.7622, "lng": 4.8200,
        "weight": 1.5,            # A-tier : ex-White Stripes, rock, 68 EUR
        "hours":  (21, 23),
        "ramp":   3,
    },
    {
        "name":   "NdF — Sébastien Tellier + Giorgio Poi",
        "dates":  [date(2026, 6, 19)],
        "zone":   "fourviere",
        "lat":    45.7622, "lng": 4.8200,
        "weight": 0.8,            # électro/pop français
        "hours":  (21, 23),
        "ramp":   1,
    },
    {
        "name":   "NdF — Samedi Hip-Hop (Yame, Ino Casablanca)",
        "dates":  [date(2026, 6, 20)],
        "zone":   "fourviere",
        "lat":    45.7622, "lng": 4.8200,
        "weight": 0.8,            # samedi festif, public jeune
        "hours":  (20, 23),
        "ramp":   2,
    },
    {
        "name":   "NdF — Sharon Eyal + Ballet Opéra de Lyon",
        "dates":  _days("2026-06-23", "2026-06-24"),
        "zone":   "fourviere",
        "lat":    45.7622, "lng": 4.8200,
        "weight": 0.5,            # danse contemporaine
        "hours":  (21, 23),
        "ramp":   1,
    },
    {
        "name":   "NdF — Selah Sue",
        "dates":  [date(2026, 6, 25)],
        "zone":   "fourviere",
        "lat":    45.7622, "lng": 4.8200,
        "weight": 1.0,            # soul/pop belge, 52 EUR
        "hours":  (21, 23),
        "ramp":   2,
    },
    {
        "name":   "NdF — Eddy de Pretto × Maud Le Pladec",
        "dates":  [date(2026, 6, 26)],
        "zone":   "fourviere",
        "lat":    45.7622, "lng": 4.8200,
        "weight": 0.8,            # pop/rap + danse, création
        "hours":  (22, 23),
        "ramp":   2,
    },
    {
        "name":   "NdF — Samedi Soul (Curtis Harding, José James)",
        "dates":  [date(2026, 6, 27)],
        "zone":   "fourviere",
        "lat":    45.7622, "lng": 4.8200,
        "weight": 0.7,            # samedi thématique soul/blues
        "hours":  (20, 23),
        "ramp":   2,
    },
    {
        "name":   "NdF — 1, 2, 3 Poquelin (tg STAN)",
        "dates":  _days("2026-06-28", "2026-06-29"),
        "zone":   "fourviere",
        "lat":    45.7622, "lng": 4.8200,
        "weight": 0.5,            # théâtre
        "hours":  (20, 22),
        "ramp":   1,
    },
    # --- Juillet — Grand Théâtre ---
    {
        "name":   "NdF — Ballet Preljocaj « Le Lac des cygnes »",
        "dates":  _days("2026-07-01", "2026-07-03"),
        "zone":   "fourviere",
        "lat":    45.7622, "lng": 4.8200,
        "weight": 0.8,            # ballet renommé, Grand Théâtre plein air
        "hours":  (22, 23),
        "ramp":   2,
    },
    {
        "name":   "NdF — Samedi 100% Lyon (Trinix, Plum, Dowdelin)",
        "dates":  [date(2026, 7, 4)],
        "zone":   "fourviere",
        "lat":    45.7622, "lng": 4.8200,
        "weight": 0.7,            # samedi local
        "hours":  (20, 23),
        "ramp":   2,
    },
    {
        "name":   "NdF — Nuit de la Poésie (Clara Ysé)",
        "dates":  [date(2026, 7, 5)],
        "zone":   "fourviere",
        "lat":    45.7622, "lng": 4.8200,
        "weight": 0.5,            # niche, public littéraire
        "hours":  (21, 23),
        "ramp":   1,
    },
    {
        "name":   "NdF — Zip Zap Circus « Moya »",
        "dates":  [date(2026, 7, 6)],
        "zone":   "fourviere",
        "lat":    45.7622, "lng": 4.8200,
        "weight": 0.5,
        "hours":  (20, 22),
        "ramp":   1,
    },
    {
        "name":   "NdF — Camille Symphonique + ONL",
        "dates":  [date(2026, 7, 7)],
        "zone":   "fourviere",
        "lat":    45.7622, "lng": 4.8200,
        "weight": 1.3,            # A- : Camille + Orchestre National de Lyon, 62 EUR
        "hours":  (20, 23),
        "ramp":   2,
    },
    {
        "name":   "NdF — Pulp",
        "dates":  [date(2026, 7, 8)],
        "zone":   "fourviere",
        "lat":    45.7622, "lng": 4.8200,
        "weight": 1.8,            # S-tier : reformation britpop, intl, 68 EUR
        "hours":  (21, 23),
        "ramp":   3,
    },
    {
        "name":   "NdF — Agnès Obel + Quatuor Debussy",
        "dates":  [date(2026, 7, 9)],
        "zone":   "fourviere",
        "lat":    45.7622, "lng": 4.8200,
        "weight": 1.0,            # indie/classical, 59 EUR
        "hours":  (21, 23),
        "ramp":   2,
    },
    {
        "name":   "NdF — Darkside (Nicolas Jaar) + SUUNS",
        "dates":  [date(2026, 7, 10)],
        "zone":   "fourviere",
        "lat":    45.7622, "lng": 4.8200,
        "weight": 0.8,            # electronic/experimental
        "hours":  (20, 23),
        "ramp":   2,
    },
    {
        "name":   "NdF — Samedi Cubain (Los Van Van, Eliades Ochoa)",
        "dates":  [date(2026, 7, 11)],
        "zone":   "fourviere",
        "lat":    45.7622, "lng": 4.8200,
        "weight": 0.7,            # samedi world/salsa
        "hours":  (20, 23),
        "ramp":   2,
    },
    {
        "name":   "NdF — Wet Leg + Lambrini Girls",
        "dates":  [date(2026, 7, 13)],
        "zone":   "fourviere",
        "lat":    45.7622, "lng": 4.8200,
        "weight": 1.0,            # UK indie buzz, 45 EUR
        "hours":  (20, 23),
        "ramp":   2,
    },
    {
        "name":   "NdF — Lorde",
        "dates":  [date(2026, 7, 15)],
        "zone":   "fourviere",
        "lat":    45.7622, "lng": 4.8200,
        "weight": 1.8,            # S-tier : global pop star, public jeune, 69 EUR
        "hours":  (21, 23),
        "ramp":   3,
    },
    {
        "name":   "NdF — Asaf Avidan + Mina Tindle",
        "dates":  [date(2026, 7, 16)],
        "zone":   "fourviere",
        "lat":    45.7622, "lng": 4.8200,
        "weight": 1.0,            # folk/rock, fanbase fidèle, 68 EUR
        "hours":  (21, 23),
        "ramp":   2,
    },
    {
        "name":   "NdF — Charlotte Cardin",
        "dates":  [date(2026, 7, 17)],
        "zone":   "fourviere",
        "lat":    45.7622, "lng": 4.8200,
        "weight": 1.3,            # A- : rising star canadienne, 68 EUR
        "hours":  (21, 23),
        "ramp":   2,
    },
    {
        "name":   "NdF — Samedi Electro (Polo & Pan, Roller Disco)",
        "dates":  [date(2026, 7, 18)],
        "zone":   "fourviere",
        "lat":    45.7622, "lng": 4.8200,
        "weight": 1.0,            # Polo & Pan headliner + format fête
        "hours":  (20, 23),
        "ramp":   2,
    },
    {
        "name":   "NdF — The Köln Concert (Enhco, Namekawa)",
        "dates":  [date(2026, 7, 19)],
        "zone":   "fourviere",
        "lat":    45.7622, "lng": 4.8200,
        "weight": 0.5,            # jazz/classique, public connaisseur
        "hours":  (21, 23),
        "ramp":   1,
    },
    {
        "name":   "NdF — Patrick Watson + Gildaa",
        "dates":  [date(2026, 7, 20)],
        "zone":   "fourviere",
        "lat":    45.7622, "lng": 4.8200,
        "weight": 1.0,            # indie canadien, 45 EUR
        "hours":  (20, 23),
        "ramp":   2,
    },
    {
        "name":   "NdF — Vincent Delerm / Vincent Dedienne",
        "dates":  [date(2026, 7, 21)],
        "zone":   "fourviere",
        "lat":    45.7622, "lng": 4.8200,
        "weight": 0.7,            # chanson/humour, public familial
        "hours":  (21, 23),
        "ramp":   1,
    },
    {
        "name":   "NdF — Kery James / Isha × Limsa d'Aulnay",
        "dates":  [date(2026, 7, 22)],
        "zone":   "fourviere",
        "lat":    45.7622, "lng": 4.8200,
        "weight": 1.5,            # A-tier : hip-hop engagé, crowd sensible sécu
        "hours":  (20, 23),
        "ramp":   2,
    },
    {
        "name":   "NdF — The Divine Comedy",
        "dates":  [date(2026, 7, 23)],
        "zone":   "fourviere",
        "lat":    45.7622, "lng": 4.8200,
        "weight": 0.7,            # chamber pop
        "hours":  (21, 23),
        "ramp":   1,
    },
    {
        "name":   "NdF — Clair Obscur : Expedition 33",
        "dates":  [date(2026, 7, 24)],
        "zone":   "fourviere",
        "lat":    45.7622, "lng": 4.8200,
        "weight": 0.7,            # concert jeu vidéo, format immersif
        "hours":  (20, 23),
        "ramp":   2,
    },
    {
        "name":   "NdF — Nuit du Raï (clôture)",
        "dates":  [date(2026, 7, 25)],
        "zone":   "fourviere",
        "lat":    45.7622, "lng": 4.8200,
        "weight": 0.7,            # samedi de clôture, raï/world
        "hours":  (20, 23),
        "ramp":   2,
    },
    # --- NdF hors-les-murs (dans rayon 1.2 km d'une zone) ---
    {
        "name":   "NdF — Ce que le ciel ne sait pas (Les Subs)",
        "dates":  _days("2026-06-04", "2026-06-06"),
        "zone":   "presquile",
        "lat":    45.7695, "lng": 4.8265,  # Les Subs, quai Saint-Vincent
        "weight": 0.5,
        "hours":  (20, 22),
        "ramp":   1,
    },
    {
        "name":   "NdF — Boris Charmatz CERCLES (Halle Tony Garnier)",
        "dates":  _days("2026-07-03", "2026-07-04"),
        "zone":   "gerland",
        "lat":    45.7299, "lng": 4.8250,  # Halle Tony Garnier
        "weight": 0.7,
        "hours":  (20, 22),
        "ramp":   1,
    },
    {
        "name":   "NdF — Orchestre vide (Les Subs)",
        "dates":  _days("2026-07-08", "2026-07-09"),
        "zone":   "presquile",
        "lat":    45.7695, "lng": 4.8265,
        "weight": 0.3,
        "hours":  (20, 22),
        "ramp":   1,
    },
    {
        "name":   "NdF — SHANGWE le bal (Les Subs)",
        "dates":  [date(2026, 7, 14)],
        "zone":   "presquile",
        "lat":    45.7695, "lng": 4.8265,
        "weight": 0.5,            # format bal festif
        "hours":  (20, 23),
        "ramp":   1,
    },
    {
        "name":   "NdF — Rebecca Chaillon (Les Subs)",
        "dates":  _days("2026-07-16", "2026-07-19"),
        "zone":   "presquile",
        "lat":    45.7695, "lng": 4.8265,
        "weight": 0.3,
        "hours":  (20, 22),
        "ramp":   1,
    },
    {
        "name":   "Biennale d'Art Contemporain",
        "dates":  _days("2026-09-19", "2026-12-31"),  # Sep 19 → ~Jan 3 2027
        "zone":   "gerland",        # Usines Fagor (29 000 m², plus grand site)
        "lat":    45.7260, "lng": 4.8340,
        "weight": 1.0,
        "hours":  (10, 19),         # expositions journée
        "ramp":   1,
    },
    # --- Q4 ---
    {
        "name":   "Run in Lyon",
        "dates":  [date(2026, 10, 4)],
        "zone":   "presquile",      # départ Vieux-Lyon, arrivée/village Place Bellecour
        "lat":    45.7545, "lng": 4.8260,
        "weight": 1.2,
        "hours":  (7, 15),          # marathon départ 8h, arrivées jusqu'à ~14h30
        "ramp":   1,
    },
    {
        "name":   "Festival Lumière",
        "dates":  _days("2026-10-10", "2026-10-18"),
        "zone":   "montchat",       # Institut Lumière, 25 rue du Premier Film (Lyon 8e)
        "lat":    45.7450, "lng": 4.8706,
        "weight": 1.2,
        "hours":  (10, 23),         # séances cinéma toute la journée
        "ramp":   1,
    },
    {
        "name":   "Equita Lyon (Eurexpo)",
        "dates":  _days("2026-10-28", "2026-11-01"),
        "zone":   "part-dieu",      # impact réel = transit (T3 tram vers Eurexpo)
        "lat":    45.7605, "lng": 4.8597,  # Gare Part-Dieu
        "weight": 1.0,              # réduit : impact indirect (transit)
        "hours":  (8, 20),          # salon 9h-19h, samedi jusqu'à 22h30
        "ramp":   2,
    },
    # Fête des Lumières — ~2M visiteurs sur 4 nuits, Lyon paralysée
    # Sites principaux : poids 0.7 (épicentres CRITIQUE)
    # Gares d'accès (Part-Dieu, Perrache) : poids 0.3 (saturation transport TENDU)
    {
        "name":   "Fête des Lumières — Presqu'île",
        "dates":  _days("2026-12-05", "2026-12-08"),
        "zone":   "presquile",
        "lat":    45.7580, "lng": 4.8330,
        "weight": 0.7,
        "hours":  (18, 23),         # illuminations nocturnes
        "ramp":   2,
    },
    {
        "name":   "Fête des Lumières — Fourvière",
        "dates":  _days("2026-12-05", "2026-12-08"),
        "zone":   "fourviere",
        "lat":    45.7622, "lng": 4.8200,
        "weight": 0.7,
        "hours":  (18, 23),
        "ramp":   2,
    },
    {
        "name":   "Fête des Lumières — Vieux Lyon",
        "dates":  _days("2026-12-05", "2026-12-08"),
        "zone":   "vieux-lyon",
        "lat":    45.7622, "lng": 4.8271,
        "weight": 0.7,
        "hours":  (18, 23),
        "ramp":   2,
    },
    {
        "name":   "Fête des Lumières — Croix-Rousse",
        "dates":  _days("2026-12-05", "2026-12-08"),
        "zone":   "croix-rousse",
        "lat":    45.7760, "lng": 4.8320,
        "weight": 0.7,
        "hours":  (18, 23),
        "ramp":   2,
    },
    {
        "name":   "Fête des Lumières — Parc de la Tête d'Or",
        "dates":  _days("2026-12-05", "2026-12-08"),
        "zone":   "brotteaux",
        "lat":    45.7720, "lng": 4.8570,   # entrée sud du parc, dans le rayon Brotteaux
        "weight": 0.7,
        "hours":  (18, 23),
        "ramp":   2,
    },
    {
        "name":   "Fête des Lumières — Gare Part-Dieu (accès)",
        "dates":  _days("2026-12-05", "2026-12-08"),
        "zone":   "part-dieu",
        "lat":    45.7605, "lng": 4.8597,
        "weight": 0.3,
        "hours":  (16, 23),         # afflux gare dès 16h
        "ramp":   2,
    },
    {
        "name":   "Fête des Lumières — Gare Perrache (accès)",
        "dates":  _days("2026-12-05", "2026-12-08"),
        "zone":   "perrache",
        "lat":    45.7488, "lng": 4.8286,
        "weight": 0.3,
        "hours":  (16, 23),         # afflux gare dès 16h
        "ramp":   2,
    },
]


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _active_events(today: date = None) -> List[dict]:
    if today is None:
        today = date.today()
    return [ev for ev in STATIC_EVENTS if today in ev["dates"]]


# ──────────────────────────────────────────────
# Scoring event → signal float par zone
# ──────────────────────────────────────────────

def compute_event_signals(today: date = None) -> Dict[str, float]:
    """
    Retourne {zone_id: event_signal_float} pour la date donnée.
    Signal ∈ [0.0, 3.0] — cohérent avec les autres signaux du moteur.
    Zone sans event = 0.0 → normalisé légèrement négatif (effet "calme").
    """
    scores: Dict[str, float] = {z: 0.0 for z in ZONE_CENTROIDS}
    active = _active_events(today)

    if not active:
        log.info("Event signals: aucun événement actif aujourd'hui.")
        return scores

    for ev in active:
        for zone_id, (zlat, zlng) in ZONE_CENTROIDS.items():
            dist = _haversine_km(ev["lat"], ev["lng"], zlat, zlng)
            if dist <= EVENT_RADIUS_KM:
                proximity = 1.0 - (dist / EVENT_RADIUS_KM)
                scores[zone_id] += ev["weight"] * proximity

    result = {z: round(min(v, 3.0), 4) for z, v in scores.items()}
    active_zones = {z: v for z, v in result.items() if v > 0}
    log.info(f"Event signals: {len(active)} événement(s) actif(s) → zones impactées: {active_zones}")
    return result


# ──────────────────────────────────────────────
# Point d'entrée pour ingestion.py
# ──────────────────────────────────────────────

async def fetch_event_signals() -> Dict[str, float]:
    """
    Appelé par ingestion.py — retourne {zone_id: float} prêt à injecter.
    Async pour compatibilité avec asyncio.gather dans ingestion.py.
    """
    return compute_event_signals()
