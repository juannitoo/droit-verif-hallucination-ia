"""From a document to a report. Both the window and the command line go through here."""
from datetime import date
from pathlib import Path

from . import keys, reader, report
from .countries import COUNTRIES, DEFAULT
from .locales import t


def valid_date(text):
    """True for a real calendar date written YYYY-MM-DD."""
    try:
        date.fromisoformat(text)
        return len(text) == 10
    except ValueError:
        return False


def available_keys(country):
    return {name: keys.get(name) for name in country.KEYS if keys.get(name)}


def check_document(path, country_code=DEFAULT, log=lambda s: None, reference_date=None):
    """Read, extract, check. Raises reader.Unreadable if the document cannot be read."""
    country = COUNTRIES[country_code]
    doc = reader.read(path)
    citations, remarks = country.extract(doc.text)
    log(t.FOUND.format(n=len(citations)))
    for c in citations:
        start, end = c.pop("span")
        page, in_notes = doc.locate(start)
        c["location"] = {"page": page, "page_exact": doc.pages == "exact",
                         "in_notes": in_notes, "excerpt": doc.excerpt(start, end)}
    results = country.check(citations, available_keys(country), log, reference_date)
    return report.build(Path(path).name, country_code, results, remarks, reference_date)


def check_citations(citations, source, country_code=DEFAULT, log=lambda s: None,
                    reference_date=None):
    country = COUNTRIES[country_code]
    results = country.check(citations, available_keys(country), log, reference_date)
    return report.build(source, country_code, results, [], reference_date)
