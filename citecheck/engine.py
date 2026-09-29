"""From a document to a report. Both the window and the command line go through here."""
from pathlib import Path

from . import keys, reader, report
from .countries import COUNTRIES, DEFAULT
from .locales import t


def available_keys(country):
    return {name: keys.get(name) for name in country.KEYS if keys.get(name)}


def check_document(path, country_code=DEFAULT, log=lambda s: None):
    """Read, extract, check. Raises reader.Unreadable if the document cannot be read."""
    country = COUNTRIES[country_code]
    text = reader.text_of(path)
    citations, remarks = country.extract(text)
    log(t.FOUND.format(n=len(citations)))
    results = country.check(citations, available_keys(country), log)
    return report.build(Path(path).name, country_code, results, remarks)


def check_citations(citations, source, country_code=DEFAULT, log=lambda s: None):
    country = COUNTRIES[country_code]
    results = country.check(citations, available_keys(country), log)
    return report.build(source, country_code, results, [])
