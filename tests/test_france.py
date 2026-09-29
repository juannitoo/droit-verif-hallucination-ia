"""Offline tests: extraction, verdicts, report. The network is tested with
`python -m citecheck --case cases/perigueux.json`."""
import json
import unittest

from citecheck import report
from citecheck.countries.france.codes import ABBREVIATIONS, find_code
from citecheck.countries.france.conventions import _key
from citecheck.reader import NOTES, PAGE, Document
from citecheck.countries.france import verdict_admin, verdict_judicial
from citecheck.countries.france.articles import quote_fragments, quote_in, version_at
from citecheck.countries.france.extract import extract, normalize_number

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


class Articles(unittest.TestCase):
    TEXT = ("Selon l'article L. 3121-2 du Code du travail, « les temps consacrés aux pauses "
            "sont considérés comme du temps de travail effectif ». Voir aussi les articles "
            "L. 1234-1 et L. 1234-5 du même code, l'art. 1240 C. civ. et C. trav., art. "
            "L. 1152-1. L'article 700 du code de procédure civile s'applique. « Tout fait "
            "quelconque de l'homme, qui cause à autrui un dommage » (C. civ., art. 1382). "
            "L'article 22 de la loi du 6 juillet 1989 aussi.")

    def test_codes_and_numbers(self):
        citations, remarks = extract(self.TEXT)
        seen = [(c["code"], c["number"]) for c in citations if c["kind"] == "article"]
        self.assertEqual(seen, [
            ("Code du travail", "L3121-2"), ("Code du travail", "L1234-1"),
            ("Code du travail", "L1234-5"), ("Code civil", "1240"),
            ("Code du travail", "L1152-1"), ("Code de procédure civile", "700"),
            ("Code civil", "1382")])
        self.assertTrue(any("22" in r for r in remarks))    # la loi : signalée, pas devinée

    def test_each_quote_goes_to_one_citation(self):
        citations, _ = extract(self.TEXT)
        quotes = {c["number"]: c["quote"] for c in citations if c["kind"] == "article"}
        self.assertTrue(quotes["L3121-2"].startswith("les temps consacrés"))
        self.assertTrue(quotes["1382"].startswith("Tout fait quelconque"))
        self.assertIsNone(quotes["700"])
        self.assertIsNone(quotes["1240"])

    def test_number_normalization(self):
        self.assertEqual(normalize_number("L. 3121-2"), "L3121-2")
        self.assertEqual(normalize_number("R.* 4624-10"), "R4624-10")
        self.assertEqual(normalize_number("1240"), "1240")

    def test_quote_matching(self):
        article = "Le temps nécessaire à la restauration [...] est du temps de travail effectif."
        self.assertTrue(quote_in(quote_fragments("le temps nécessaire à la restauration"), article))
        self.assertTrue(quote_in(quote_fragments(
            "Le temps nécessaire à la restauration (...) est du temps de travail"), article))
        self.assertFalse(quote_in(quote_fragments("les pauses ne sont jamais payées"), article))
        self.assertEqual(quote_fragments("trop court"), [])

    def test_version_at(self):
        versions = [{"debut": "2008-05-01", "fin": "2016-08-10"},
                    {"debut": "2016-08-10", "fin": "2999-01-01"}]
        self.assertEqual(version_at(versions, "2012-01-01")["debut"], "2008-05-01")
        self.assertEqual(version_at(versions, "2016-08-10")["debut"], "2016-08-10")
        self.assertIsNone(version_at(versions, "2000-01-01"))


class Conventions(unittest.TestCase):
    TEXT = ("Selon l'article 21 de la convention collective nationale des hôtels, cafés "
            "restaurants (IDCC 1979), « Pour les cuisiniers, la durée hebdomadaire au travail "
            "est de 43 heures ». Voir aussi l'article 25.1 de la CCN et l'article 12.1 de "
            "ladite convention. « Les parties conviennent » (art. 3 de l'avenant n° 2).")

    def test_idcc_numbers_and_quote(self):
        citations, remarks = extract(self.TEXT)
        seen = [(c["idcc"], c["number"], bool(c["quote"])) for c in citations
                if c["kind"] == "convention_article"]
        # 25.1 est dans la phrase suivante : son IDCC n'est pas deviné.
        self.assertEqual(seen, [("1979", "21", True), (None, "25.1", False),
                                ("1979", "12.1", False)])
        self.assertTrue(any("avenant" in r for r in remarks))

    def test_number_keys(self):
        self.assertEqual(_key("1er"), _key("1"))
        self.assertEqual(_key("8 (1)"), "8")
        self.assertEqual(_key("25.1"), "25.1")


class LowerCourts(unittest.TestCase):
    def test_rg_needs_a_court_in_the_sentence(self):
        text = ("Voir CA Paris, pôle 4, ch. 3, 2 octobre 2013, RG n° 11/18803. La cour d'appel "
                "d'Aix-en-Provence, 12 mars 2024, n° 22/01234. TJ Périgueux, 18 décembre 2025, "
                "RG 23/00452. Un RG 21/00999 sans juridiction. En mars 03/2019 rien.")
        citations, remarks = extract(text)
        seen = [(c["jurisdiction"], c["place"], c["number"], c["cited_date"])
                for c in citations if c.get("order") == "lower"]
        self.assertEqual(seen, [("ca", "Paris", "11/18803", "2013-10-02"),
                                ("ca", "Aix-en-Provence", "22/01234", "2024-03-12"),
                                ("tj", "Périgueux", "23/00452", "2025-12-18")])
        self.assertTrue(any("21/00999" in r for r in remarks))


class Scope(unittest.TestCase):
    def test_every_displayed_abbreviation_is_recognized(self):
        """The "what is checked" tab must not promise an abbreviation we do not read."""
        for forms, _, title in ABBREVIATIONS:
            for form in forms:
                self.assertEqual(find_code(f"art. 1 {form} x")[0], title, form)


class Location(unittest.TestCase):
    def test_pages_and_notes(self):
        doc = Document(f"page un{PAGE}page deux{PAGE}page trois{NOTES}une note", "exact")
        self.assertEqual(doc.locate(0), (1, False))
        self.assertEqual(doc.locate(doc.text.index("deux")), (2, False))
        self.assertEqual(doc.locate(doc.text.index("trois")), (3, False))
        self.assertEqual(doc.locate(doc.text.index("note")), (None, True))

    def test_no_pages_means_no_page(self):
        self.assertEqual(Document("texte brut", None).locate(3), (None, False))

    def test_excerpt(self):
        doc = Document("a" * 100 + " article 1240 du Code civil " + "b" * 100, "exact")
        start = doc.text.index("article")
        ex = doc.excerpt(start, start + 12, margin=10)
        self.assertTrue(ex.startswith("…") and ex.endswith("…") and "article 1240" in ex)


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
