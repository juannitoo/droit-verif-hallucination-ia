"""The report, in two forms: text for a human, JSON for an AI.

The JSON closes the loop "the AI writes, this program checks, the AI fixes": give the
report back to the AI that wrote the document and it corrects its citations.
"""
import json
from collections import Counter
from datetime import date

from . import NAME, __version__
from .locales import t


def build(source, country, results, remarks):
    return {
        "program": f"{NAME} {__version__}",
        "date": date.today().isoformat(),
        "source": source,
        "country": country,
        "disclaimer": t.DISCLAIMER,
        "summary": dict(Counter(r["verdict"] for r in results)),
        # `verdict` is a stable code, the same in every language; `verdict_label` is for humans.
        "citations": [{**r, "verdict_label": t.VERDICTS[r["verdict"]]} for r in results],
        "remarks": remarks,
    }


def to_json(report):
    return json.dumps(report, ensure_ascii=False, indent=2)


def to_text(report):
    lines = [t.TITLE, t.DOCUMENT_LINE.format(source=report["source"]),
             t.CHECKED_LINE.format(date=report["date"], program=report["program"]), "",
             t.DISCLAIMER, ""]
    cits = report["citations"]
    if not cits:
        lines.append(t.NO_CITATION)
    for r in cits:
        lines.append(t.CITATION_LINE.format(court=r["court"], number=r["number"],
                                            date=r.get("cited_date") or t.NO_DATE))
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
    return "\n".join(lines).rstrip() + "\n"
