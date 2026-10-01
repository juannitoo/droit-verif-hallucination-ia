"""Entry point. No argument: the window. With a document: the command line.

  python -m citecheck                               # the window
  python -m citecheck brief.pdf                     # text report
  python -m citecheck brief.pdf --json              # JSON report, for an AI
  python -m citecheck brief.pdf --pdf               # + brief-citations-verifiees.pdf
  python -m citecheck brief.docx -o rapport.pdf     # the report as a PDF
  python -m citecheck brief.pdf --reference-date 2019-03-21   # articles read at that date
  python -m citecheck --number 17-28268 --date 2019-03-21
  python -m citecheck --case cases/perigueux.json   # benchmark on a real case
"""
import argparse
import json
import sys

from pathlib import Path

from . import NAME, __version__, annotate, output, reader, report, report_pdf
from .countries import COUNTRIES, DEFAULT
from .engine import check_citations, check_document, valid_date
from .locales import t


def log(line):
    print(line, file=sys.stderr)


def benchmark(path):
    """Replay a real case whose answer is known. Exit code 1 if any verdict differs."""
    with open(path, encoding="utf-8") as f:
        case = json.load(f)
    r = check_citations(case["citations"], case["source"], case.get("country", "france"), log,
                        case.get("options"))
    print(report.to_text(r))
    gaps = [c for c in r["citations"]
            if c["verdict"] != "NOT_TESTED" and c["verdict"] != c.get("expected")]
    untested = sum(c["verdict"] == "NOT_TESTED" for c in r["citations"])
    tested = len(r["citations"]) - untested
    print(t.BENCH_RESULT.format(ok=tested - len(gaps), tested=tested, untested=untested))
    for c in gaps:
        print(t.BENCH_GAP.format(number=c["number"], expected=c.get("expected"),
                                 got=c["verdict"]))
    return 1 if gaps or not tested else 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog=NAME, description=t.CLI_DESCRIPTION)
    ap.add_argument("document", nargs="?", help=".pdf .docx .odt .txt .md")
    ap.add_argument("--json", action="store_true", help="JSON report, for an AI")
    ap.add_argument("-o", "--output", help="write the report to this file; a name ending "
                    "in .pdf gives the report as a PDF")
    ap.add_argument("--number", help="check a single decision number")
    ap.add_argument("--date", help="cited date for --number, YYYY-MM-DD")
    ap.add_argument("--order", choices=["administrative", "judicial"],
                    help="order of the decision for --number (guessed from its format)")
    ap.add_argument("--reference-date", help="date the cited articles must be read at, "
                    "YYYY-MM-DD (default: today)")
    ap.add_argument("--idcc", help="IDCC of the collective agreement, for articles cited "
                    "without one")
    ap.add_argument("--with-excerpts", action="store_true",
                    help="keep excerpts of the document in the report (default: none, only "
                    "numbers, dates and verdicts, as the window does)")
    ap.add_argument("--pdf", action="store_true",
                    help="also write the annotated PDF next to the document: each citation "
                    "highlighted in the colour of its verdict, and linked to what was found")
    ap.add_argument("--case", help="benchmark: a case file whose answer is known")
    ap.add_argument("--scope", action="store_true", help=t.CLI_SCOPE)
    ap.add_argument("--version", action="version", version=f"{NAME} {__version__}")
    a = ap.parse_args(argv)
    for d in (a.reference_date, a.date):
        if d and not valid_date(d):
            ap.error(t.REFERENCE_INVALID)
    if a.idcc and not a.idcc.isdigit():
        ap.error(t.IDCC_INVALID)

    if a.scope:
        for heading, lines in COUNTRIES[DEFAULT].scope():
            print(heading)
            for line in lines:
                print(f"  - {line}")
            print()
        return 0
    if not (a.document or a.number or a.case):
        from .gui import run
        return run()
    if a.case:
        return benchmark(a.case)

    if a.output and a.document and (output.same_file(a.output, a.document) or (
            a.pdf and output.same_file(a.output, annotate.output_name(Path(a.document))))):
        print(t.NOT_OVER_DOCUMENT, file=sys.stderr)    # avant de vérifier : rien n'est perdu
        return 2

    if a.number:
        order = a.order or ("judicial" if "-" in a.number else "administrative")
        citation = {"order": order, "court": "Cass" if order == "judicial" else "CE",
                    "number": a.number, "cited_date": a.date}
        r = check_citations([citation], f"n° {a.number}", log=log)
    else:
        try:
            r = check_document(a.document, log=log, options={
                "reference_date": a.reference_date, "idcc": a.idcc})
        except reader.Unreadable as e:
            print(t.CLI_UNREADABLE.format(error=e), file=sys.stderr)
            return 2
        if a.pdf and Path(a.document).suffix.lower() == ".pdf":
            target = annotate.output_name(Path(a.document))
            try:
                placed, missed = annotate.annotate(a.document, target, r)
                log(t.PDF_SAVED.format(path=target, placed=placed)
                    + (t.PDF_MISSED.format(n=missed) if missed else ""))
            except annotate.TooHeavy as e:
                log(t.PDF_FAILED_ANNOTATE.format(error=e))
        elif a.pdf:
            log(t.PDF_ONLY)

    if not a.with_excerpts:
        r = report.without_excerpts(r)
    out = report.to_json(r) if a.json else report.to_text(r)
    if a.output and a.output.lower().endswith(".pdf"):
        report_pdf.write(r, a.output, document=a.document)
    elif a.output:
        output.write(a.output, out, document=a.document)
    else:
        print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
