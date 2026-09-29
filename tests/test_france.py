"""Offline tests: extraction, verdicts, report. The network is tested with
`python -m citecheck --case cases/perigueux.json`."""
import json
import unittest

from citecheck import report
from citecheck.countries.france import verdict_admin, verdict_judicial
from citecheck.countries.france.extract import extract

PERIGUEUX = ("Voir Conseil d'État du 5 juin 2009, n° 308850, et Cour de cassation, "
             "2e civ., 21 mars 2019, n° 17-28268. Aussi CE, 30 novembre 2018, n° 402517 ; "
             "Cass. soc., 14/12/2017, pourvoi 16-26.694.")


class Extraction(unittest.TestCase):
    def test_perigueux(self):
        citations, remarks = extract(PERIGUEUX)
        seen = {c["number"]: (c["order"], c["cited_date"]) for c in citations}
        self.assertEqual(seen["308850"], ("administrative", "2009-06-05"))
        self.assertEqual(seen["17-28268"], ("judicial", "2019-03-21"))
        self.assertEqual(seen["402517"], ("administrative", "2018-11-30"))
        self.assertEqual(seen["16-26.694"], ("judicial", "2017-12-14"))
        self.assertEqual(remarks, [])

    def test_communication_is_not_com(self):
        """"communication" must not turn a Conseil d'État decision into a judicial one."""
        citations, _ = extract("Sur la communication des pièces, CE, 12 mars 2019, n° 416043.")
        self.assertEqual([(c["number"], c["order"]) for c in citations],
                         [("416043", "administrative")])

    def test_missing_date_is_reported(self):
        citations, remarks = extract("Conseil d'État, n° 308850.")
        self.assertIsNone(citations[0]["cited_date"])
        self.assertTrue(remarks)


class Verdicts(unittest.TestCase):
    def test_admin(self):
        self.assertEqual(verdict_admin(0, set(), "2009-06-05")[0], "NOT_PUBLISHED")
        self.assertEqual(verdict_admin(-1, set(), None)[0], "ERROR")
        self.assertEqual(verdict_admin(12, {"2009-06-05"}, "2009-06-05")[0], "CONFIRMED")
        self.assertEqual(verdict_admin(12, {"2009-06-05"}, "2009-06-06")[0], "WRONG_DATE")
        self.assertEqual(verdict_admin(2, set(), "2009-06-05")[0], "DOUBTFUL")

    def test_cited_by_others_is_never_confirmed(self):
        verdict, why, _ = verdict_admin(40, set(), "2009-06-05")
        self.assertEqual(verdict, "EXISTS_DATE_UNCHECKED")
        self.assertIn("NON contrôlée", why)

    def test_judicial(self):
        record = {"decision_date": "2019-04-10", "chamber": "civ1", "solution": "rejet"}
        self.assertEqual(verdict_judicial(record, "2019-04-10")[0], "CONFIRMED")
        self.assertEqual(verdict_judicial(record, "2019-03-21")[0], "WRONG_DATE")
        self.assertEqual(verdict_judicial(None, "2019-03-21")[0], "NOT_PUBLISHED")
        self.assertEqual(verdict_judicial({"_err": "HTTP 500"}, None)[0], "ERROR")


class Report(unittest.TestCase):
    def test_disclaimer_always_present(self):
        r = report.build("empty.txt", "france", [], [])
        self.assertIn("sans garantie", report.to_text(r))
        self.assertIn("sans garantie", json.loads(report.to_json(r))["disclaimer"])


if __name__ == "__main__":
    unittest.main()
