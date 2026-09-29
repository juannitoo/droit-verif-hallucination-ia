"""The report, in two forms: text for a human, JSON for an AI.

The JSON closes the loop "the AI writes, this program checks, the AI fixes": give the
report back to the AI that wrote the document and it corrects its citations.
"""
import json
from collections import Counter
from datetime import date

from . import NAME, __version__
from .countries import COUNTRIES
from .locales import t


def build(source, country, results, remarks, options=None):
    options = options or {}
    return {
        "program": f"{NAME} {__version__}",
        "date": date.today().isoformat(),
        "source": source,
        "country": country,
        # The date the cited articles were read at; None means "today, by default".
        "reference_date": options.get("reference_date"),
        # The IDCC the user gave for conventions cited without one.
        "idcc": options.get("idcc"),
        "disclaimer": t.DISCLAIMER,
        "summary": dict(Counter(r["verdict"] for r in results)),
        # `verdict` is a stable code, the same in every language; `verdict_label` is for humans.
        "citations": [{**r, "verdict_label": t.VERDICTS[r["verdict"]]} for r in results],
        "remarks": remarks,
    }


def to_json(report):
    return json.dumps(report, ensure_ascii=False, indent=2)


def _where(r):
    loc = r.get("location")
    if not loc:
        return ""
    if loc["in_notes"]:
        return t.WHERE_NOTES
    if loc["page"]:
        return (t.WHERE_PAGE if loc["page_exact"] else t.WHERE_PAGE_APPROX).format(page=loc["page"])
    return ""


def to_text(report):
    lines = [t.TITLE, t.DOCUMENT_LINE.format(source=report["source"]),
             t.CHECKED_LINE.format(date=report["date"], program=report["program"]), "",
             t.DISCLAIMER, ""]
    cits = report["citations"]
    if any(c.get("kind") in ("article", "convention_article") for c in cits):
        lines.append(t.REFERENCE_LINE.format(
            date=report["reference_date"] or report["date"],
            default="" if report["reference_date"] else t.REFERENCE_DEFAULT))
        lines.append("")
    if not cits:
        lines.append(t.NO_CITATION)
    for r in cits:
        if r.get("kind") in ("article", "convention_article"):
            if r["kind"] == "article":
                head = t.ARTICLE_LINE.format(code=r["code"], number=r["number"])
            else:
                head = t.CONVENTION_LINE.format(idcc=r.get("idcc") or report.get("idcc") or t.IDCC_UNKNOWN,
                                                number=r["number"])
            lines.append(head + _where(r))
            if r.get("quote"):
                q = r["quote"] if len(r["quote"]) <= 160 else r["quote"][:157] + "..."
                lines.append(t.QUOTE_LINE.format(quote=q))
        else:
            lines.append(t.CITATION_LINE.format(court=r["court"], number=r["number"],
                                                date=r.get("cited_date") or t.NO_DATE)
                         + _where(r))
        if r.get("location"):
            lines.append(t.EXCERPT_LINE.format(excerpt=r["location"]["excerpt"]))
        lines.append(f"    {t.VERDICTS[r['verdict']]} : {r['explanation']}")
        lines.append("")
    if cits:
        lines.append(t.SUMMARY)
        for code, label in t.VERDICTS.items():
            if report["summary"].get(code):
                lines.append(f"    {report['summary'][code]:>3}  {label}")
        lines.append("")
    for rq in report["remarks"]:
        lines.append(t.REMARK.format(text=rq))
    if report["remarks"]:
        lines.append("")
    if report["summary"].get("NOT_PUBLISHED"):
        lines.append(t.NOTE_NOT_PUBLISHED)
    if report["summary"].get("WRONG_DATE"):
        lines.append(t.NOTE_WRONG_DATE)
    if report["summary"].get("ARTICLE_OTHER_VERSION"):
        lines.append(t.NOTE_OTHER_VERSION)
    lines.append("")
    lines.append(t.NOT_CHECKED.format(
        what=COUNTRIES[report["country"]].not_checked_summary()))
    return "\n".join(lines).rstrip() + "\n"
