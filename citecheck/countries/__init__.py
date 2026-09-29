"""One package per country. Each exposes the same interface:

  NAME                          display name
  KEYS                          {key name: label}, the keys the user must provide
  KEY_HELP_URL                  where to get them
  prepare(keys, log)            -> remarks. Called before extract: refresh what extract
                                recognizes from the databases (must never fail, never
                                block); the remarks go into the report
  extract(text)                 -> (citations, remarks)
  check(citations, keys, log, options) -> results, one per citation, in order
                                options: reference_date, idcc (see the country)
  scope()                       -> [(heading, lines)], what is and is not checked
  not_checked_summary()         -> one line, printed at the end of every report

A citation is a dict with at least: order, court, number, cited_date (ISO or None).
A result is the citation plus: verdict (a code from locales), explanation, actual_date.

Comments and explanations inside a country package are written in that country's
language. Adding a country means adding a package and one line below, nothing else.
"""
from . import france

COUNTRIES = {"france": france}
DEFAULT = "france"
