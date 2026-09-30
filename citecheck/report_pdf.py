"""Le rapport en PDF : le même contenu que le rapport texte, pour un avocat qui relit,
imprime ou verse au dossier. Un vrai tableau, les couleurs des verdicts (les mêmes que dans
le PDF annoté), et des liens qui s'ouvrent d'un clic.

Il est écrit par fpdf2, qui ne reçoit que du texte : aucune image, rien du document
vérifié sinon les extraits, et aucun extrait si le rapport a été fait « sans extraits ».
Police : Roboto, celle que customtkinter fournit déjà pour la fenêtre.
"""
from pathlib import Path

import customtkinter
from fpdf import FPDF
from fpdf.fonts import FontFace

from . import report as rep
from .countries import COUNTRIES
from .locales import t

FONTS = Path(customtkinter.__file__).parent / "assets" / "fonts" / "Roboto"
INK = (30, 30, 38)
MUTED = (100, 100, 112)
ACCENT = (6, 82, 133)          # le bleu foncé du thème, pour les titres et les liens
RULE = (200, 200, 208)
# Fonds des cellules de verdict : les couleurs du PDF annoté, éclaircies pour l'écrit.
FILLS = {rep.CONFIRMED: (214, 230, 255), rep.CHECK: (255, 226, 190),
         rep.INVENTED: (255, 208, 206), rep.UNCHECKED: (228, 228, 232)}
# Colonnes du tableau, en mm (la page utile fait 180 mm).
WIDTHS = (10, 14, 72, 58, 26)


class _Pdf(FPDF):
    def footer(self):
        self.set_y(-12)
        self.set_font("Roboto", size=8)
        self.set_text_color(*MUTED)
        self.cell(0, 5, t.PDF_REPORT_FOOTER.format(program=self.program, page=self.page_no(),
                                                   pages="{nb}"), align="C")


def _heading(pdf, text):
    pdf.ln(3)
    pdf.set_font("Roboto", "B", 12)
    pdf.set_text_color(*ACCENT)
    pdf.multi_cell(0, 6, text, new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(*INK)
    pdf.ln(1)


def _para(pdf, text, size=10, color=INK, style="", indent=0, gap=1.5):
    pdf.set_font("Roboto", style, size)
    pdf.set_text_color(*color)
    pdf.set_x(pdf.l_margin + indent)
    pdf.multi_cell(0, size * 0.48, text, new_x="LMARGIN", new_y="NEXT", align="L")
    pdf.ln(gap)
    pdf.set_text_color(*INK)


def _link(pdf, url, indent):
    pdf.set_font("Roboto", size=8.5)
    pdf.set_text_color(*ACCENT)
    pdf.set_x(pdf.l_margin + indent)
    pdf.multi_cell(0, 4.2, url, link=url, new_x="LMARGIN", new_y="NEXT", align="L")
    pdf.set_text_color(*INK)
    pdf.ln(1.5)


def _legend(pdf, report):
    """Les quatre couleurs, avec combien de citations dans chacune."""
    counts = {}
    for r in report["citations"]:
        counts[rep.light(r["verdict"])] = counts.get(rep.light(r["verdict"]), 0) + 1
    pdf.set_font("Roboto", size=9.5)
    for light in (rep.CONFIRMED, rep.CHECK, rep.INVENTED, rep.UNCHECKED):
        label = f" {counts.get(light, 0)} {t.LIGHT_LABELS[light]}"
        pdf.set_fill_color(*FILLS[light])
        pdf.cell(5, 5, "", fill=True, border=0)
        pdf.cell(pdf.get_string_width(label) + 7, 5, label)
    pdf.ln(8)


def _table(pdf, report):
    pdf.set_font("Roboto", size=9)
    pdf.set_draw_color(*RULE)
    pdf.set_fill_color(255, 255, 255)       # la légende a laissé sa dernière couleur
    head = FontFace(emphasis="BOLD", color=(255, 255, 255), fill_color=ACCENT)
    with pdf.table(col_widths=WIDTHS, width=sum(WIDTHS), line_height=4.6,
                   text_align="LEFT", headings_style=head, padding=1.4,
                   first_row_as_headings=True, repeat_headings=1) as table:
        row = table.row()
        for name in (t.COL_NUMBER, t.COL_PAGE, t.COL_CITATION, t.COL_VERDICT, t.COL_SOURCE):
            row.cell(name)
        for n, r in enumerate(report["citations"], 1):
            row = table.row()
            row.cell(str(n))
            row.cell(rep.page_label(r))
            row.cell(rep.citation_label(r, report))
            row.cell(t.VERDICTS[r["verdict"]],
                     style=FontFace(fill_color=FILLS[rep.light(r["verdict"])]))
            if r.get("link"):
                row.cell(t.OPEN_LINK, link=r["link"],
                         style=FontFace(color=ACCENT, emphasis="UNDERLINE"))
            else:
                row.cell("")


def _details(pdf, report):
    _heading(pdf, t.DETAILS.rstrip(" :"))
    for n, r in enumerate(report["citations"], 1):
        # Une citation et son détail sur la même page : sa hauteur, estimée d'après sa
        # longueur (une ligne pour 110 caractères environ).
        chars = len(r["explanation"]) + len((r.get("location") or {}).get("excerpt") or "")
        if pdf.will_page_break(18 + 5 * (chars // 110 + 2) + (5 if r.get("link") else 0)):
            pdf.add_page()
        _para(pdf, f"{n}. {rep.citation_label(r, report)}", size=10, style="B", gap=0.5)
        light = rep.light(r["verdict"])
        pdf.set_fill_color(*FILLS[light])
        pdf.set_font("Roboto", "B", 9)
        pdf.set_x(pdf.l_margin + 5)
        pdf.cell(pdf.get_string_width(t.VERDICTS[r["verdict"]]) + 3, 5,
                 t.VERDICTS[r["verdict"]], fill=True, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(0.8)
        _para(pdf, r["explanation"], size=9.5, indent=5, gap=0.8)
        if r.get("link"):
            _link(pdf, r["link"], 5)
        if r.get("quote"):
            q = r["quote"] if len(r["quote"]) <= 300 else r["quote"][:299] + "…"
            _para(pdf, t.QUOTE_LINE.format(quote=q), size=9, color=MUTED, indent=5, gap=0.8)
        if (r.get("location") or {}).get("excerpt"):
            _para(pdf, t.EXCERPT_LINE.format(excerpt=r["location"]["excerpt"]), size=9,
                  color=MUTED, indent=5, gap=0.8)
        pdf.ln(2.5)


def write(report, target):
    """Écrit le rapport en PDF dans `target`."""
    pdf = _Pdf(format="A4")
    pdf.program = report["program"]
    pdf.set_margins(15, 15, 15)
    pdf.set_auto_page_break(True, margin=18)
    pdf.add_font("Roboto", "", str(FONTS / "Roboto-Regular.ttf"))
    pdf.add_font("Roboto", "B", str(FONTS / "Roboto-Medium.ttf"))
    pdf.set_title(t.TITLE)
    pdf.set_creator(report["program"])
    pdf.add_page()

    pdf.set_font("Roboto", "B", 17)
    pdf.set_text_color(*ACCENT)
    pdf.multi_cell(0, 8, t.TITLE, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1)
    _para(pdf, t.DOCUMENT_LINE.format(source=report["source"]), size=10.5, style="B", gap=0.5)
    _para(pdf, t.CHECKED_LINE.format(date=report["date"], program=report["program"]),
          size=9.5, color=MUTED)
    cits = report["citations"]
    if any(c.get("kind") in rep.LEGISLATION for c in cits):
        _para(pdf, t.REFERENCE_LINE.format(
            date=report["reference_date"] or report["date"],
            default="" if report["reference_date"] else t.REFERENCE_DEFAULT), size=9.5)
    _para(pdf, t.DISCLAIMER, size=9, color=MUTED, gap=3)

    if not cits:
        _para(pdf, t.NO_CITATION)
    else:
        _legend(pdf, report)
        _table(pdf, report)
        pdf.ln(3)
        _details(pdf, report)
    if report["remarks"]:
        _heading(pdf, t.REMARKS_HEADING)
        for rq in report["remarks"]:
            _para(pdf, rq, size=9.5)
    notes = [note for code, note in (("NOT_PUBLISHED", t.NOTE_NOT_PUBLISHED),
                                     ("WRONG_DATE", t.NOTE_WRONG_DATE),
                                     ("ARTICLE_OTHER_VERSION", t.NOTE_OTHER_VERSION))
             if report["summary"].get(code)]
    if notes or cits:
        _heading(pdf, t.READING_HEADING)
        for note in notes:
            _para(pdf, note, size=9.5)
    _para(pdf, t.NOT_CHECKED.format(what=COUNTRIES[report["country"]].not_checked_summary()),
          size=9, color=MUTED)
    pdf.output(str(target))


def output_name(document, without_excerpts):
    """« conclusions.pdf » -> « conclusions-rapport-citations.pdf ». Sans extraits, le nom du
    document n'y figure pas : il peut contenir celui d'une partie."""
    if without_excerpts or not document:
        return f"{t.REPORT_FILE}.pdf"
    return f"{Path(document).stem}-{t.REPORT_FILE}.pdf"
