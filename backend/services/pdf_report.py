"""
Urban Signal Engine --- PDF Report Generator
==============================================
Render pre-event simulation data as a professional PDF document.
Uses fpdf2 (pure Python, no C deps).
"""

from fpdf import FPDF
from typing import Any, Dict, List


# ---- Colors ----

_COLORS = {
    "CALME":    (76, 175, 80),     # green
    "MODERE":   (255, 193, 7),     # amber
    "TENDU":    (255, 152, 0),     # orange
    "CRITIQUE": (244, 67, 54),     # red
    "bg_dark":  (33, 37, 41),      # dark bg
    "bg_light": (248, 249, 250),   # light bg
    "accent":   (59, 130, 246),    # blue
    "text":     (33, 37, 41),
    "muted":    (108, 117, 125),
}


def _level_color(level: str) -> tuple:
    return _COLORS.get(level.replace("É", "E"), _COLORS["CALME"])


def _score_color(score: int) -> tuple:
    if score >= 72:
        return _COLORS["CRITIQUE"]
    if score >= 55:
        return _COLORS["TENDU"]
    if score >= 35:
        return _COLORS["MODERE"]
    return _COLORS["CALME"]


def _sanitize(text: str) -> str:
    """Replace non-Latin-1 chars for Helvetica compatibility."""
    replacements = {
        "\u2014": "-",  # em-dash
        "\u2013": "-",  # en-dash
        "\u2018": "'",  # left single quote
        "\u2019": "'",  # right single quote
        "\u201c": '"',  # left double quote
        "\u201d": '"',  # right double quote
        "\u2026": "...",  # ellipsis
        "\u00c9": "E",  # É
        "\u00e9": "e",  # é
        "\u00e8": "e",  # è
        "\u00ea": "e",  # ê
        "\u00e0": "a",  # à
        "\u00e2": "a",  # â
        "\u00f4": "o",  # ô
        "\u00ee": "i",  # î
        "\u00e7": "c",  # ç
        "\u00f9": "u",  # ù
        "\u00fb": "u",  # û
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    # Final fallback: strip any remaining non-latin1
    return text.encode("latin-1", errors="replace").decode("latin-1")


class PreEventPDF(FPDF):
    """Custom PDF class with header/footer."""

    def __init__(self, event_name: str, date_str: str):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.event_name = _sanitize(event_name)
        self.date_str = date_str
        self.set_auto_page_break(auto=True, margin=20)

    def header(self):
        if self.page_no() == 1:
            return  # cover page has custom header
        self.set_font("Helvetica", "B", 8)
        self.set_text_color(*_COLORS["muted"])
        self.cell(0, 6, "URBAN SIGNAL ENGINE", align="L")
        self.cell(0, 6, f"{self.event_name} | {self.date_str}", align="R", new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(*_COLORS["accent"])
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(4)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "", 7)
        self.set_text_color(*_COLORS["muted"])
        self.cell(0, 10, f"Page {self.page_no()}/{{nb}}", align="C")

    def _section_title(self, title: str):
        self.set_font("Helvetica", "B", 13)
        self.set_text_color(*_COLORS["bg_dark"])
        self.cell(0, 10, title, new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(*_COLORS["accent"])
        self.line(10, self.get_y(), 80, self.get_y())
        self.ln(4)

    def _label_value(self, label: str, value: str, bold_value: bool = False):
        self.set_font("Helvetica", "", 9)
        self.set_text_color(*_COLORS["muted"])
        self.cell(55, 6, _sanitize(label))
        self.set_font("Helvetica", "B" if bold_value else "", 9)
        self.set_text_color(*_COLORS["text"])
        self.cell(0, 6, _sanitize(str(value)), new_x="LMARGIN", new_y="NEXT")

    def _risk_badge(self, level: str, score: int, x: float = None, y: float = None):
        color = _level_color(level)
        if x is not None:
            self.set_xy(x, y)
        self.set_fill_color(*color)
        self.set_text_color(255, 255, 255)
        self.set_font("Helvetica", "B", 11)
        text = f"  {level}  {score}/100  "
        self.cell(50, 8, text, fill=True, align="C")
        self.set_text_color(*_COLORS["text"])


def generate_pre_event_pdf(report: Dict[str, Any]) -> bytes:
    """
    Generate a pre-event analysis PDF from the JSON report data.
    Returns PDF bytes (ready to stream as HTTP response).
    """
    ev = report["event"]
    event_name = ev["name"]
    date_str = ev["date"]
    summary = report["executive_summary"]

    pdf = PreEventPDF(event_name, date_str)
    pdf.alias_nb_pages()

    # ── PAGE 1: Cover ─────────────────────────────────────────────────
    pdf.add_page()

    # Dark header block
    pdf.set_fill_color(*_COLORS["bg_dark"])
    pdf.rect(0, 0, 210, 90, "F")

    pdf.set_xy(15, 15)
    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(180, 180, 180)
    pdf.cell(0, 6, "URBAN SIGNAL ENGINE", new_x="LMARGIN", new_y="NEXT")

    pdf.set_xy(15, 25)
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(*_COLORS["accent"])
    pdf.cell(0, 5, "RAPPORT PRE-EVENEMENT", new_x="LMARGIN", new_y="NEXT")

    pdf.set_xy(15, 38)
    pdf.set_font("Helvetica", "B", 22)
    pdf.set_text_color(255, 255, 255)
    # Truncate long names
    display_name = _sanitize(event_name if len(event_name) <= 45 else event_name[:42] + "...")
    pdf.cell(0, 12, display_name, new_x="LMARGIN", new_y="NEXT")

    pdf.set_xy(15, 55)
    pdf.set_font("Helvetica", "", 12)
    pdf.set_text_color(200, 200, 200)
    pdf.cell(0, 8, date_str, new_x="LMARGIN", new_y="NEXT")

    # Risk badge on cover
    pdf.set_xy(15, 70)
    pdf._risk_badge(summary["overall_risk"], summary["overall_peak_score"])

    # BLUF section
    pdf.set_xy(15, 100)
    pdf._section_title("Synthese")
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*_COLORS["text"])
    pdf.multi_cell(180, 6, _sanitize(report["bluf"]))
    pdf.ln(6)

    # Key metrics
    pdf._section_title("Indicateurs cles")
    critical_zones_str = ", ".join(
        ev.get("zone_names", {}).get(z, z) for z in summary.get("critical_zones", [])
    ) or "Aucune"
    pw = summary.get("peak_window", {})
    peak_window_str = f"{pw.get('from', '?')}h - {pw.get('to', '?')}h"

    pdf._label_value("Pic de tension estime", f"{summary['overall_peak_score']}/100 ({summary['overall_risk']})", True)
    pdf._label_value("Zones critiques", critical_zones_str)
    pdf._label_value("Fenetre de risque principale", peak_window_str)
    pdf._label_value("Confiance donnees", report.get("data_confidence", "N/A"))
    pdf._label_value("Meteo", _sanitize(report.get("weather_context", {}).get("summary", "N/A")[:80]))
    pdf.ln(4)

    # DPS
    dps = report.get("dps", {})
    if dps:
        pdf._label_value("Categorie DPS", f"{dps.get('categorie', '?')} - {dps.get('description', '?')}")
        pdf._label_value("Estimation effectifs", dps.get("staffing_estimate", "?"))

    # ── PAGE 2: Score Timeline ────────────────────────────────────────
    pdf.add_page()
    pdf._section_title("Profil horaire 24h par zone")

    zones_analysis = report.get("zones_analysis", {})
    if zones_analysis:
        _render_score_timeline(pdf, zones_analysis)

    # ── PAGE 3: Risk Windows & Signal Breakdown ──────────────────────
    pdf.add_page()
    pdf._section_title("Fenetres de risque")

    risk_windows = report.get("risk_windows_summary", [])
    if risk_windows:
        _render_risk_windows(pdf, risk_windows)
    else:
        pdf.set_font("Helvetica", "I", 9)
        pdf.cell(0, 6, "Aucune fenetre de risque detectee (score < 55 sur toutes les zones).", new_x="LMARGIN", new_y="NEXT")

    pdf.ln(6)
    pdf._section_title("Decomposition des signaux")
    signals_bd = report.get("signals_breakdown", {})
    if signals_bd:
        _render_signals_breakdown(pdf, signals_bd)

    # ── PAGE 4: Recommendations & Escalation ─────────────────────────
    pdf.add_page()
    pdf._section_title("Recommandations operationnelles")

    recos = report.get("recommendations", [])
    for r in recos:
        pdf.set_font("Helvetica", "", 9)
        level = r.get("level", 0)
        bullet = ["*", "!", "!!", "!!!"][min(level, 3)]
        pdf.set_text_color(*_COLORS["text"])
        pdf.multi_cell(180, 5, _sanitize(f"  [{bullet}]  {r['text']}"))
        pdf.ln(2)

    pdf.ln(4)
    pdf._section_title("Declencheurs d'escalade")

    triggers = report.get("escalation_triggers", [])
    for t in triggers:
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(*_COLORS["CRITIQUE"])
        pdf.set_x(10)
        pdf.multi_cell(180, 5, _sanitize(f"  SI : {t['condition']}"))
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(*_COLORS["text"])
        pdf.set_x(10)
        pdf.multi_cell(180, 5, _sanitize(f"  ALORS : {t['action']}"))
        pdf.ln(3)

    # Footer note
    pdf.ln(10)
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(*_COLORS["muted"])
    pdf.multi_cell(180, 4, _sanitize(
        f"Document genere automatiquement par Urban Signal Engine le {report.get('generated_at', '?')[:10]}. "
        f"Donnees de simulation basees sur les profils historiques, la meteo prevue, et le calendrier evenementiel. "
        f"Ce document ne se substitue pas a une analyse de terrain."
    ))

    return pdf.output()


# ── Score Timeline Table ─────────────────────────────────────────────

def _render_score_timeline(pdf: PreEventPDF, zones_analysis: Dict):
    """Render a color-coded score table: hours (columns) x zones (rows)."""
    zones = sorted(zones_analysis.keys())
    if not zones:
        return

    # Collect all hours
    all_hours = set()
    for zdata in zones_analysis.values():
        for h in zdata.get("hourly", []):
            all_hours.add(h["hour"])
    hours = sorted(all_hours)

    if not hours:
        return

    # Layout
    label_w = 28
    cell_w = min(9.5, (180 - label_w) / len(hours))
    cell_h = 7

    # Header row (hours)
    pdf.set_font("Helvetica", "B", 6)
    pdf.set_text_color(*_COLORS["muted"])
    pdf.cell(label_w, cell_h, "Zone / Heure")
    for h in hours:
        pdf.cell(cell_w, cell_h, f"{h}h", align="C")
    pdf.ln()

    # Build score lookup
    for zone_id in zones:
        zdata = zones_analysis[zone_id]
        hourly = {h["hour"]: h for h in zdata.get("hourly", [])}

        # Zone name
        from services.scoring import ZONE_NAMES
        zname = ZONE_NAMES.get(zone_id, zone_id)[:12]
        pdf.set_font("Helvetica", "", 7)
        pdf.set_text_color(*_COLORS["text"])
        pdf.cell(label_w, cell_h, zname)

        for h in hours:
            entry = hourly.get(h)
            if entry:
                score = entry["score"]
                color = _score_color(score)
                pdf.set_fill_color(*color)
                # White text on dark bg, dark text on light bg
                if score >= 55:
                    pdf.set_text_color(255, 255, 255)
                else:
                    pdf.set_text_color(*_COLORS["text"])
                pdf.set_font("Helvetica", "B" if score >= 55 else "", 6)
                pdf.cell(cell_w, cell_h, str(score), fill=True, align="C")
            else:
                pdf.set_fill_color(*_COLORS["bg_light"])
                pdf.set_text_color(*_COLORS["muted"])
                pdf.set_font("Helvetica", "", 6)
                pdf.cell(cell_w, cell_h, "-", fill=True, align="C")

        pdf.ln()

    pdf.set_text_color(*_COLORS["text"])
    pdf.ln(4)

    # Legend
    pdf.set_font("Helvetica", "", 7)
    pdf.set_text_color(*_COLORS["muted"])
    for level, label in [("CALME", "< 35 CALME"), ("MODERE", "35-54 MODERE"),
                          ("TENDU", "55-71 TENDU"), ("CRITIQUE", "72+ CRITIQUE")]:
        pdf.set_fill_color(*_COLORS[level])
        pdf.cell(4, 4, "", fill=True)
        pdf.cell(1, 4, "")
        pdf.set_text_color(*_COLORS["muted"])
        pdf.cell(25, 4, label)
    pdf.ln(6)


# ── Risk Windows Table ───────────────────────────────────────────────

def _render_risk_windows(pdf: PreEventPDF, windows: List[Dict]):
    """Render risk windows as structured blocks."""
    for w in windows[:10]:
        color = _level_color(w.get("level", "CALME"))

        # Score badge + zone + time header
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_fill_color(*color)
        pdf.set_text_color(255, 255, 255)
        pdf.cell(30, 7, f" {w.get('peak_score', '?')} {w.get('level', '')} ", fill=True, align="C")

        pdf.set_text_color(*_COLORS["text"])
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(5, 7, "")
        pdf.cell(0, 7, _sanitize(
            f"{w.get('zone_name', '?')}  |  {w.get('from', '?')}h - {w.get('to', '?')}h  |  Signal : {w.get('main_signal', '?')}"
        ), new_x="LMARGIN", new_y="NEXT")

        # Full recommendation (wraps)
        reco = w.get("recommendation", "")
        if reco:
            pdf.set_font("Helvetica", "", 8)
            pdf.set_text_color(*_COLORS["muted"])
            pdf.set_x(10)
            pdf.multi_cell(180, 5, _sanitize(f"  {reco}"))
        pdf.ln(2)


# ── Signals Breakdown Table ──────────────────────────────────────────

def _render_signals_breakdown(pdf: PreEventPDF, breakdown: Dict):
    """Render average z-scores per zone as a table."""
    from services.scoring import ZONE_NAMES

    col_widths = [30, 22, 22, 22, 22, 22, 30]
    headers = ["Zone", "Trafic", "Meteo", "Transport", "Event", "Incident", "Dominant"]

    pdf.set_font("Helvetica", "B", 8)
    pdf.set_fill_color(*_COLORS["bg_light"])
    pdf.set_text_color(*_COLORS["text"])
    for i, h in enumerate(headers):
        pdf.cell(col_widths[i], 7, h, fill=True, align="C" if i > 0 else "L")
    pdf.ln()

    sig_keys = ["traffic", "weather", "transport", "event", "incident"]

    for zone_id in sorted(breakdown.keys()):
        data = breakdown[zone_id]
        zname = ZONE_NAMES.get(zone_id, zone_id)[:12]

        pdf.set_font("Helvetica", "", 7)
        pdf.set_text_color(*_COLORS["text"])
        pdf.cell(col_widths[0], 6, zname)

        dominant = data.get("dominant_signal", "")
        for i, s in enumerate(sig_keys):
            val = data.get(f"{s}_zscore", 0.0)
            is_dominant = (s == dominant)

            if val > 1.5:
                pdf.set_text_color(*_COLORS["CRITIQUE"])
            elif val > 0.5:
                pdf.set_text_color(*_COLORS["TENDU"])
            else:
                pdf.set_text_color(*_COLORS["muted"])

            pdf.set_font("Helvetica", "B" if is_dominant else "", 7)
            pdf.cell(col_widths[i + 1], 6, f"{val:+.1f}", align="C")

        pdf.set_font("Helvetica", "B", 7)
        pdf.set_text_color(*_COLORS["accent"])
        pdf.cell(col_widths[6], 6, dominant.capitalize(), align="C")
        pdf.ln()

    pdf.set_text_color(*_COLORS["text"])
