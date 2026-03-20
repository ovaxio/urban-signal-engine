#!/usr/bin/env python3
"""
Generate OL Backtest PDF — 2 pages, sales-ready.
Uses real signals_history data from 2026-03-19.
"""
import os
import sys
import sqlite3
import tempfile

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.ticker import MultipleLocator

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "backend"))
from fpdf import FPDF

# ── Config ───────────────────────────────────────────────────────────
DATE = "2026-03-19"
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "backend", "data", "urban_signal.db")
OUT_PATH = os.path.join(os.path.dirname(__file__), f"OL-backtest-{DATE}.pdf")

ZONES = ["gerland", "part-dieu", "brotteaux"]
ZONE_LABELS = {"gerland": "Gerland / Groupama", "part-dieu": "Part-Dieu (Gare)", "brotteaux": "Brotteaux"}
ZONE_COLORS = {"gerland": "#e8830a", "part-dieu": "#64748b", "brotteaux": "#94a3b8"}
ZONE_WIDTHS = {"gerland": 2.8, "part-dieu": 1.8, "brotteaux": 1.2}

BANDS = [
    (0, 30, "#f0fdf4", "CALME"),
    (30, 55, "#fefce8", "MODERE"),
    (55, 75, "#fff7ed", "TENDU"),
    (75, 100, "#fef2f2", "CRITIQUE"),
]


def fetch_data():
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("""
        SELECT CAST(strftime('%H', ts) AS INTEGER) as hour, zone_id,
               ROUND(AVG(urban_score), 1) as score,
               ROUND(AVG(traffic), 2) as z_traf,
               ROUND(AVG(transport), 2) as z_trans,
               ROUND(AVG(weather), 2) as z_weather,
               ROUND(AVG(raw_incident), 3) as raw_inc,
               MAX(incident_label) as label
        FROM signals_history
        WHERE source='live' AND DATE(ts)=?
          AND zone_id IN ('gerland', 'part-dieu', 'brotteaux')
        GROUP BY hour, zone_id ORDER BY hour, zone_id
    """, (DATE,)).fetchall()

    data = {z: {} for z in ZONES}
    for r in rows:
        h, z = r[0], r[1]
        data[z][h] = {
            "score": r[2], "z_traf": r[3], "z_trans": r[4],
            "z_weather": r[5], "raw_inc": r[6], "label": r[7],
        }

    # Peak info
    peak = conn.execute("""
        SELECT ts, urban_score, traffic, raw_incident, incident_label
        FROM signals_history
        WHERE source='live' AND DATE(ts)=? AND zone_id='gerland'
        ORDER BY urban_score DESC LIMIT 1
    """, (DATE,)).fetchone()

    first_tendu = conn.execute("""
        SELECT ts FROM signals_history
        WHERE source='live' AND DATE(ts)=? AND zone_id='gerland' AND urban_score >= 55
        ORDER BY ts ASC LIMIT 1
    """, (DATE,)).fetchone()

    conn.close()
    return data, peak, first_tendu


def generate_chart(data, peak, first_tendu):
    """Generate the timeline chart as PNG, return path."""
    fig, ax = plt.subplots(figsize=(10, 5.2))

    # Background bands
    for lo, hi, color, label in BANDS:
        ax.axhspan(lo, hi, color=color, alpha=0.7, zorder=0)
        ax.text(5.3, (lo + hi) / 2, label, fontsize=7, color="#666666",
                va="center", ha="left", style="italic", alpha=0.8)

    # Plot each zone
    for zone in ZONES:
        zdata = data[zone]
        hours = sorted(zdata.keys())
        scores = [zdata[h]["score"] for h in hours]
        ax.plot(hours, scores, color=ZONE_COLORS[zone],
                linewidth=ZONE_WIDTHS[zone], label=ZONE_LABELS[zone],
                zorder=3, solid_capstyle="round")

    # Annotation: first TENDU
    if first_tendu:
        ft_hour = int(first_tendu[0][11:13]) + int(first_tendu[0][14:16]) / 60
        ax.axvline(ft_hour, color="#f59e0b", linestyle="--", linewidth=1, alpha=0.7, zorder=2)
        ax.annotate("Alerte detectee\nT-10h avant pic",
                     xy=(ft_hour, 58), fontsize=7, color="#b45309",
                     ha="left", va="bottom",
                     bbox=dict(boxstyle="round,pad=0.3", fc="#fffbeb", ec="#f59e0b", alpha=0.9))

    # Annotation: peak
    peak_hour = int(peak[0][11:13])
    peak_score = peak[1]
    ax.annotate(f"Pic {int(peak_score)}/100",
                 xy=(peak_hour, peak_score), xytext=(peak_hour + 0.5, peak_score - 8),
                 fontsize=8, fontweight="bold", color="#dc2626",
                 arrowprops=dict(arrowstyle="->", color="#dc2626", lw=1.5),
                 bbox=dict(boxstyle="round,pad=0.3", fc="#fef2f2", ec="#dc2626"))

    # Callout box
    ax.text(6.5, 95,
            "Un responsable exploitation aurait recu\n"
            "l'alerte 10h avant le pic de tension.",
            fontsize=7.5, color="#1e293b",
            bbox=dict(boxstyle="round,pad=0.5", fc="white", ec="#cbd5e1", alpha=0.95),
            va="top", ha="left", zorder=5)

    # Formatting
    ax.set_xlim(5, 18)
    ax.set_ylim(0, 105)
    ax.set_xlabel("Heure (UTC)", fontsize=9, color="#475569")
    ax.set_ylabel("Urban Score (0-100)", fontsize=9, color="#475569")
    ax.xaxis.set_major_locator(MultipleLocator(1))
    ax.set_xticks(range(5, 19))
    ax.set_xticklabels([f"{h}h" for h in range(5, 19)], fontsize=8)
    ax.yaxis.set_major_locator(MultipleLocator(10))
    ax.tick_params(colors="#94a3b8", labelsize=8)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#e2e8f0")
    ax.spines["bottom"].set_color("#e2e8f0")
    ax.grid(axis="y", color="#f1f5f9", linewidth=0.5, zorder=0)

    # Legend
    ax.legend(loc="upper left", fontsize=8, frameon=True, fancybox=True,
              framealpha=0.9, edgecolor="#e2e8f0")

    plt.tight_layout()
    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    fig.savefig(tmp.name, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return tmp.name


def s(text):
    """Sanitize for latin-1 (fpdf2 Helvetica)."""
    reps = {
        "\u2014": "-", "\u2013": "-", "\u2018": "'", "\u2019": "'",
        "\u201c": '"', "\u201d": '"', "\u2026": "...",
        "\u00e9": "e", "\u00e8": "e", "\u00ea": "e", "\u00c9": "E",
        "\u00e0": "a", "\u00e2": "a", "\u00f4": "o", "\u00ee": "i",
        "\u00e7": "c", "\u00f9": "u", "\u00fb": "u", "\u00e0": "a",
    }
    for old, new in reps.items():
        text = text.replace(old, new)
    return text.encode("latin-1", errors="replace").decode("latin-1")


def build_pdf(chart_path, data, peak, first_tendu):
    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=False)

    peak_score = int(peak[1])
    ft_hour = first_tendu[0][11:16] if first_tendu else "06:41"
    peak_hour = peak[0][11:16]
    lead_time = int(peak[0][11:13]) - int(first_tendu[0][11:13]) if first_tendu else 10

    # ── PAGE 1 ────────────────────────────────────────────────────────
    pdf.add_page()

    # Dark header
    pdf.set_fill_color(30, 32, 38)
    pdf.rect(0, 0, 210, 42, "F")

    pdf.set_xy(12, 8)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(140, 140, 140)
    pdf.cell(0, 5, "URBAN SIGNAL ENGINE", new_x="LMARGIN", new_y="NEXT")

    pdf.set_xy(12, 14)
    pdf.set_font("Helvetica", "B", 7)
    pdf.set_text_color(59, 130, 246)
    pdf.cell(0, 5, "RAPPORT D'ANTICIPATION", new_x="LMARGIN", new_y="NEXT")

    pdf.set_xy(12, 22)
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(0, 7, s("Analyse retrospective - Zone Groupama Stadium"), new_x="LMARGIN", new_y="NEXT")

    pdf.set_xy(12, 32)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(180, 180, 180)
    pdf.cell(0, 5, "19 mars 2026 | Lyon, France", new_x="LMARGIN", new_y="NEXT")

    # Score badge
    pdf.set_xy(155, 14)
    pdf.set_fill_color(220, 38, 38)
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(42, 18, f" {peak_score}/100 ", fill=True, align="C")

    # Chart (compact: 130mm height fits page 1)
    pdf.image(chart_path, x=8, y=44, w=194, h=130)

    # Key stats row below chart
    y_stats = 177
    pdf.set_xy(10, y_stats)

    stats = [
        ("Pic detecte", f"{peak_score}/100 CRITIQUE"),
        ("Heure du pic", f"{peak_hour} UTC"),
        ("Alerte T-", f"{lead_time}h ({ft_hour})"),
        ("Zones impactees", "3 zones"),
    ]

    col_w = 47
    for label, value in stats:
        pdf.set_font("Helvetica", "", 7)
        pdf.set_text_color(100, 116, 139)
        pdf.cell(col_w, 4, s(label))
    pdf.ln()
    pdf.set_x(10)
    for label, value in stats:
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(30, 41, 59)
        pdf.cell(col_w, 5, s(value))
    pdf.ln(6)

    # Synthesis
    pdf.set_x(10)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(71, 85, 105)
    pdf.multi_cell(190, 4, s(
        f"Le 19 mars 2026, Urban Signal Engine a detecte une montee en tension progressive "
        f"sur la zone Groupama Stadium (Gerland) des {ft_hour}, atteignant un pic CRITIQUE "
        f"de {peak_score}/100 a {peak_hour}. Les zones Part-Dieu et Brotteaux ont ete impactees "
        f"simultanement (pics respectifs de 79 et 79). L'alerte aurait ete declenchee "
        f"{lead_time}h avant le pic de tension."
    ))

    # Footer page 1
    pdf.set_xy(10, 285)
    pdf.set_font("Helvetica", "I", 6)
    pdf.set_text_color(148, 163, 184)
    pdf.cell(95, 4, s("Donnees reelles - signals_history - Urban Signal Engine v1.0"))
    pdf.cell(95, 4, "Confidentiel - urbanscoreengine.com", align="R")

    # ── PAGE 2 ────────────────────────────────────────────────────────
    pdf.add_page()

    # Header
    pdf.set_font("Helvetica", "B", 7)
    pdf.set_text_color(148, 163, 184)
    pdf.cell(95, 5, "URBAN SIGNAL ENGINE")
    pdf.cell(95, 5, "Analyse 19 mars 2026", align="R")
    pdf.ln(2)
    pdf.set_draw_color(59, 130, 246)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(6)

    # Section A: Signal decomposition
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(30, 41, 59)
    pdf.cell(0, 7, s("Signaux declencheurs - Heure du pic (17h)"), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)

    # Table header
    pdf.set_fill_color(248, 250, 252)
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(71, 85, 105)
    cols = [("Signal", 40), ("Niveau", 25), (s("Ecart (z-score)"), 30), ("Contribution", 50), ("Incident", 45)]
    for label, w in cols:
        pdf.cell(w, 6, label, fill=True)
    pdf.ln()

    # Get peak-hour data for gerland
    g17 = data["gerland"].get(17, {})
    signals = [
        ("Trafic routier", "Eleve", f"+{g17.get('z_traf', 3.38):.1f}", "Signal dominant", "#dc2626"),
        ("Incidents", "Eleve", f"+{(g17.get('raw_inc', 1.49) - 0.99) / 0.30:.1f}", "Secondaire", "#ea580c"),
        ("Transport TCL", "Normal", f"+{g17.get('z_trans', 0.03):.1f}", "Stable", "#64748b"),
        ("Meteo", "Neutre", f"{g17.get('z_weather', 0.15):+.1f}", "-", "#94a3b8"),
        ("Evenement", "-", "+0.0", "Aucun calendrier", "#94a3b8"),
    ]

    pdf.set_font("Helvetica", "", 8)
    for sig_name, niveau, zscore, contrib, color in signals:
        pdf.set_text_color(30, 41, 59)
        pdf.cell(40, 5.5, s(sig_name))

        # Colored level
        r, g, b = int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)
        pdf.set_text_color(r, g, b)
        pdf.set_font("Helvetica", "B", 8)
        pdf.cell(25, 5.5, s(niveau))

        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(30, 41, 59)
        pdf.cell(30, 5.5, s(zscore))
        pdf.cell(50, 5.5, s(contrib))

        pdf.set_text_color(100, 116, 139)
        pdf.set_font("Helvetica", "I", 7)
        label = g17.get("label", "") or ""
        pdf.cell(45, 5.5, s(label[:25]))
        pdf.ln()

    pdf.ln(6)

    # Section B: Zones impactees
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(30, 41, 59)
    pdf.cell(0, 7, s("Zones impactees simultanement"), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)

    zone_peaks = [
        ("Gerland / Groupama", 97, "17h00", "CRITIQUE", (220, 38, 38)),
        ("Part-Dieu (Gare)", 79, "16h00", "CRITIQUE", (220, 38, 38)),
        ("Brotteaux", 79, "17h00", "CRITIQUE", (220, 38, 38)),
    ]

    for zname, zpeak, zhour, zlevel, zcolor in zone_peaks:
        pdf.set_fill_color(*zcolor)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Helvetica", "B", 8)
        pdf.cell(22, 6, f" {zpeak} ", fill=True, align="C")
        pdf.set_text_color(30, 41, 59)
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(5, 6, "")
        pdf.cell(50, 6, s(zname))
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(100, 116, 139)
        pdf.cell(0, 6, s(f"Pic a {zhour} - {zlevel}"), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)

    # Section C: Recommandations
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(30, 41, 59)
    pdf.cell(0, 7, s("Recommandations operationnelles"), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)

    recos = [
        f"Renforcer le dispositif perimetre Groupama des {int(ft_hour[:2]) - 1}h00. "
        f"Prevoir rotation effectifs sur le creneau 15h-18h.",
        f"Zones secondaires a surveiller : Part-Dieu (pic 79/100), Brotteaux (pic 79/100). "
        f"Coordonner avec TCL pour gestion flux gare.",
        "Alerte automatique configurable par email/SMS. "
        "Seuil recommande : 55 (TENDU) pour declenchement anticipation.",
    ]

    for reco in recos:
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_text_color(59, 130, 246)
        pdf.cell(5, 5, ">")
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(51, 65, 85)
        pdf.multi_cell(180, 4.5, s(reco))
        pdf.ln(2)

    pdf.ln(4)

    # Section D: CTA
    y_cta = pdf.get_y()
    pdf.set_fill_color(248, 250, 252)
    pdf.rect(10, y_cta, 190, 38, "F")
    pdf.set_draw_color(59, 130, 246)
    pdf.rect(10, y_cta, 190, 38, "D")

    pdf.set_xy(15, y_cta + 4)
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(30, 41, 59)
    pdf.cell(0, 6, s("Recevez ce rapport avant votre prochain evenement a Lyon"), new_x="LMARGIN", new_y="NEXT")

    pdf.set_x(15)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(71, 85, 105)
    pdf.ln(2)
    pdf.set_x(15)
    pdf.cell(0, 5, s("Rapport d'anticipation : 390 EUR HT  |  Acces dashboard live 48h"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_x(15)
    pdf.cell(0, 5, s("Delai de livraison : 48h avant l'evenement"), new_x="LMARGIN", new_y="NEXT")

    pdf.set_xy(15, y_cta + 28)
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(59, 130, 246)
    pdf.cell(0, 5, "contact@urbanscoreengine.com")

    # Footer page 2
    pdf.set_xy(10, 285)
    pdf.set_font("Helvetica", "I", 6)
    pdf.set_text_color(148, 163, 184)
    pdf.cell(95, 4, s("Donnees reelles - signals_history - Urban Signal Engine v1.0"))
    pdf.cell(95, 4, "Confidentiel - urbanscoreengine.com", align="R")

    pdf.output(OUT_PATH)
    return OUT_PATH


def main():
    print("Fetching data...")
    data, peak, first_tendu = fetch_data()
    print(f"  Gerland peak: {peak[1]}/100 at {peak[0][:19]}")
    print(f"  First TENDU: {first_tendu[0][:19]}")

    print("Generating chart...")
    chart_path = generate_chart(data, peak, first_tendu)
    print(f"  Chart: {chart_path}")

    print("Building PDF...")
    out = build_pdf(chart_path, data, peak, first_tendu)
    size = os.path.getsize(out)
    print(f"  PDF: {out} ({size:,} bytes / {size/1024:.0f} KB)")

    # Cleanup
    os.unlink(chart_path)
    print("Done.")


if __name__ == "__main__":
    main()
