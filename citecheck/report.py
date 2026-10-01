"""The report, in two forms: text for a human, JSON for an AI.

The JSON closes the loop "the AI writes, this program checks, the AI fixes": give the
report back to the AI that wrote the document and it corrects its citations.
"""
import json
import re
import textwrap
from collections import Counter
from datetime import date

from . import NAME, __version__
from .countries import COUNTRIES
from .locales import t

QUOTE_MAX = 300     # characters of a quoted passage kept in the report: a pair of quotation
                    # marks around half the document must not carry half the document


def _capped(r):
    q = r.get("quote")
    if q and len(q) > QUOTE_MAX:
        r = {**r, "quote": q[:QUOTE_MAX - 1] + "…"}
    return r


# Control characters and bidirectional overrides, in any text that reaches the report:
# labels sent back by a database (chamber, solution, court, title), and what is read in the
# document. A line break in a label would add a line that looks like a verdict; an escape
# sequence would hide or recolour lines in a terminal; a bidi override would show a number
# reversed. None of them is ever part of a real label. U+2028 and U+2029 are line and
# paragraph separators, U+200B a zero-width space (audit du 01/10/2026).
_CONTROL = re.compile(r"[\x00-\x1f\x7f-\x9f\u200b\u200e\u200f\u2028\u2029\u202a-\u202e"
                      r"\u2066-\u2069]")


def _clean(v):
    if isinstance(v, str):
        return _CONTROL.sub(" ", v)
    if isinstance(v, dict):
        return {k: _clean(x) for k, x in v.items()}
    if isinstance(v, list):
        return [_clean(x) for x in v]
    return v


# The only hosts a link may point to: the official databases this program reads. A link
# is clicked straight from the report or the annotated PDF, so anything else is dropped.
LINK_HOSTS = frozenset({"www.legifrance.gouv.fr", "www.courdecassation.fr",
                        "www.conseil-etat.fr", "eur-lex.europa.eu", "hudoc.echr.coe.int"})


def safe_link(url):
    """True for an https address on one of LINK_HOSTS, with no user, password or port, made
    of visible ASCII only (a line separator would hide the rest of the address)."""
    from urllib.parse import urlsplit
    if not isinstance(url, str) or not all("!" <= ch <= "~" for ch in url):
        return False
    try:
        u = urlsplit(url)
        return bool(u and u.scheme == "https" and u.netloc in LINK_HOSTS)
    except ValueError:
        return False


def _linked(r):
    if "link" in r and not safe_link(r["link"]):
        r = {k: v for k, v in r.items() if k != "link"}
    return r


def build(source, country, results, remarks, options=None):
    options = options or {}
    results = [_linked(_clean(r)) for r in results]
    return {
        "program": f"{NAME} {__version__}",
        "date": date.today().isoformat(),
        "source": _clean(source),
        "country": country,
        # The date the cited articles were read at; None means "today, by default".
        "reference_date": options.get("reference_date"),
        # The IDCC the user gave for conventions cited without one.
        "idcc": options.get("idcc"),
        "disclaimer": t.DISCLAIMER,
        "summary": dict(Counter(r["verdict"] for r in results)),
        # `verdict` is a stable code, the same in every language; `verdict_label` is for humans.
        "citations": [{**_capped(r), "verdict_label": t.VERDICTS[r["verdict"]]}
                      for r in results],
        "remarks": _clean(remarks),
    }


def without_excerpts(report):
    """A copy with no text taken from the document: no excerpt, no quoted passage. Only
    numbers, dates and verdicts remain. For a report handed to an online AI, when the
    document holds names and facts that must not leave the office."""
    out = dict(report)
    out["source"] = t.SOURCE_WITHHELD      # « Dupont c. Martin.pdf » : un nom de partie
    out["citations"] = []
    for r in report["citations"]:
        r = {k: v for k, v in r.items() if k != "quote"}
        # « CA Paris » : le nom de ville est lu dans le document, il peut être autre chose
        # (audit K6). On ne garde que le type de juridiction ; l'explication cite le libellé
        # officiel de Judilibre quand il a été trouvé.
        # Les explications ne recopient pas ce nom (lower_courts.py) : rien à y chercher.
        place = r.pop("place", None)
        if place:
            court = r["court"]
            r["court"] = (court[:-len(place)] if court.endswith(place)
                          else court.split(" ", 1)[0]).strip()
        if r.get("location"):
            r["location"] = {k: v for k, v in r["location"].items()
                             if k in ("page", "page_exact", "in_notes")}
        out["citations"].append(r)
    out["excerpts_removed"] = True
    return out


def to_json(report):
    return json.dumps(report, ensure_ascii=False, indent=2)


LEGISLATION = ("article", "convention_article", "text_article")

# Le feu de chaque verdict, le même dans le rapport et dans le PDF annoté : vert (bleu à
# l'écran) ce qui est confirmé, rouge ce qui semble inventé, gris ce qui n'a pas été vérifié,
# et orange tout le reste. Un verdict douteux n'est jamais « confirmé ».
CONFIRMED, CHECK, INVENTED, UNCHECKED = "ok", "check", "invented", "unchecked"
LIGHTS = {
    "CONFIRMED": CONFIRMED, "ARTICLE_IN_FORCE": CONFIRMED,
    "NOT_PUBLISHED": INVENTED, "TEXT_NOT_FOUND": INVENTED, "ARTICLE_NOT_FOUND": INVENTED,
    "CONVENTION_NOT_FOUND": INVENTED,
    "NOT_TESTED": UNCHECKED, "ERROR": UNCHECKED, "UNVERIFIABLE_PERIOD": UNCHECKED,
    "MANUAL_CHECK": UNCHECKED,
}


# La couleur de chaque feu, en RVB 0-255 : UNE palette pour le surligneur du PDF annoté,
# sa légende et le rapport PDF. Ce qu'on voit dans la légende est ce qu'on voit dans le texte.
COLORS = {CONFIRMED: (158, 199, 255), CHECK: (255, 189, 97), INVENTED: (255, 133, 128),
          UNCHECKED: (199, 199, 199)}


def light(verdict):
    return LIGHTS.get(verdict, CHECK)


def citation_label(r, report=None):
    """« Cass. n° 17-28268, cité au 2019-03-21 », « Code civil, article 1240 »."""
    if r.get("kind") == "article":
        return t.ARTICLE_LINE.format(code=r["code"], number=r["number"])
    if r.get("kind") == "text_article":
        return t.ARTICLE_LINE.format(code=r["court"], number=r["number"])
    if r.get("kind") == "convention_article":
        idcc = r.get("idcc") or (report or {}).get("idcc") or t.IDCC_UNKNOWN
        return t.CONVENTION_LINE.format(idcc=idcc, number=r["number"])
    if r.get("number") is None:
        return t.UNNUMBERED_LINE.format(court=r["court"], date=r["cited_date"])
    line = t.RG_LINE if r.get("order") == "lower" else t.CITATION_LINE
    return line.format(court=r["court"], number=r["number"],
                       date=t.CITED_ON.format(date=r["cited_date"])
                       if r.get("cited_date") else t.NO_DATE)


def page_label(r):
    loc = r.get("location")
    if not loc:
        return ""
    if loc["in_notes"]:
        return t.PAGE_NOTES
    if loc["page"]:
        return (t.PAGE_EXACT if loc["page_exact"] else t.PAGE_APPROX).format(page=loc["page"])
    return ""


# Le tableau : une ligne par citation, les cellules longues passent à la ligne. Le détail
# (explication, lien, extrait) suit, sous le même numéro.
COLUMNS = ((t.COL_NUMBER, 3), (t.COL_PAGE, 7), (t.COL_CITATION, 38), (t.COL_VERDICT, 32))


WIDTH = 94      # la largeur du tableau : le rapport entier tient dans une fenêtre de
                # bloc-notes, sans ligne qui file à droite


def _para(text, indent=""):
    """Un paragraphe, coupé à la largeur du rapport."""
    return textwrap.wrap(text, WIDTH, initial_indent=indent, subsequent_indent=indent,
                         break_on_hyphens=False) or [""]


def _wrap(text, width):
    return textwrap.wrap(text, width, break_long_words=True, break_on_hyphens=False) or [""]


def _table(rows):
    """En ASCII (+ - |), pas en traits de tableau (┼ ─ │) : une police qui n'a pas ces traits
    les emprunte à une autre, plus large, et le tableau se décale (vu dans VS Code)."""
    widths = [w for _, w in COLUMNS]

    def rule(fill="-"):
        return "+" + "+".join(fill * (w + 2) for w in widths) + "+"

    def line(cells):
        cells = [_wrap(c, w) for c, w in zip(cells, widths)]
        out = []
        for i in range(max(len(c) for c in cells)):
            out.append("|" + "|".join(f" {(c[i] if i < len(c) else ''):<{w}} "
                                      for c, w in zip(cells, widths)) + "|")
        return out

    lines = [rule()] + line([name for name, _ in COLUMNS]) + [rule("=")]
    for i, row in enumerate(rows):
        lines += ([rule()] if i else []) + line(row)
    return lines + [rule()]


def to_text(report):
    lines = [t.TITLE, *_para(t.DOCUMENT_LINE.format(source=report["source"])),
             t.CHECKED_LINE.format(date=report["date"], program=report["program"]), "",
             *_para(t.DISCLAIMER), ""]
    cits = report["citations"]
    if any(c.get("kind") in LEGISLATION for c in cits):
        lines += _para(t.REFERENCE_LINE.format(
            date=report["reference_date"] or report["date"],
            default="" if report["reference_date"] else t.REFERENCE_DEFAULT))
        lines.append("")
    if not cits:
        lines += _para(t.NO_CITATION)
    else:
        lines += _table([(str(n), page_label(r), citation_label(r, report),
                          t.VERDICTS[r["verdict"]])
                         for n, r in enumerate(cits, 1)])
        lines += ["", t.DETAILS, ""]
    for n, r in enumerate(cits, 1):
        lines.append(f"{n:>3}. {citation_label(r, report)}")
        lines += _para(f"{t.VERDICTS[r['verdict']]} : {r['explanation']}", "     ")
        if r.get("link"):
            lines.append(t.LINK_LINE.format(link=r["link"]))    # jamais coupé : il se clique
        if r.get("quote"):
            q = r["quote"] if len(r["quote"]) <= 160 else r["quote"][:157] + "..."
            lines += _para(t.QUOTE_LINE.format(quote=q), "     ")
        if (r.get("location") or {}).get("excerpt"):
            lines += _para(t.EXCERPT_LINE.format(excerpt=r["location"]["excerpt"]), "     ")
        lines.append("")
    if cits:
        lines.append(t.SUMMARY)
        for code, label in t.VERDICTS.items():
            if report["summary"].get(code):
                lines.append(f"    {report['summary'][code]:>3}  {label}")
        lines.append("")
    for rq in report["remarks"]:
        lines += _para(t.REMARK.format(text=rq))
    if report["remarks"]:
        lines.append("")
    for code, note in (("NOT_PUBLISHED", t.NOTE_NOT_PUBLISHED), ("WRONG_DATE", t.NOTE_WRONG_DATE),
                       ("ARTICLE_OTHER_VERSION", t.NOTE_OTHER_VERSION)):
        if report["summary"].get(code):
            lines += _para(note)
    lines.append("")
    lines += _para(t.NOT_CHECKED.format(
        what=COUNTRIES[report["country"]].not_checked_summary()))
    return "\n".join(lines).rstrip() + "\n"
