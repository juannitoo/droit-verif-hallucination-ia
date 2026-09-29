"""Offline tests: extraction, verdicts, report. The network is tested with
`python -m citecheck --case cases/perigueux.json`."""
import json
import unittest

from citecheck import report
from citecheck.countries.france import codes
from citecheck.countries.france.codes import ABBREVIATIONS, TITLES, find_code, learn
from citecheck.countries.france.conventions import _key
from citecheck.reader import NOTES, PAGE, Document
from citecheck.countries.france import verdict_admin, verdict_judicial
from citecheck.countries.france.articles import (check_article, quote_fragments, quote_in,
                                                  version_at)
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

    def test_impossible_date_is_not_a_date(self):
        citations, _ = extract("Cass. soc., 31/02/2019, n° 17-28268.")
        self.assertIsNone(citations[0]["cited_date"])

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
        self.assertEqual(normalize_number("1er"), "1")      # Légifrance écrit « 1 »

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


class AuditPass2(unittest.TestCase):
    """Les points de la seconde passe d'audit (K1 à K10), pour qu'ils ne reviennent pas."""

    def test_k3_a_date_belongs_to_one_number(self):
        citations, _ = extract("CE n° 308850 du 5 juin 2009 et n° 402517.")
        self.assertEqual([(c["number"], c["cited_date"]) for c in citations],
                         [("308850", "2009-06-05"), ("402517", None)])

    def test_k3_no_date_across_a_sentence(self):
        citations, _ = extract("Le 5 juin 2009, rien. CE n° 402517 : sans date.")
        self.assertIsNone(citations[0]["cited_date"])

    def test_k2_two_dates_two_checks(self):
        citations, remarks = extract("Cass. soc., 21 mars 2019, n° 17-28268. Plus loin : "
                                     "Cass. soc., 14 mai 2020, n° 17-28268.")
        self.assertEqual([c["cited_date"] for c in citations], ["2019-03-21", "2020-05-14"])
        self.assertTrue(any("2 dates différentes" in r for r in remarks))

    def test_k4_overload_is_not_an_unknown_idcc(self):
        from citecheck.countries.france.legifrance import Client, Unavailable

        class Down(Client):
            def _post(self, route, body):
                raise Unavailable("HTTP 500", 500)
        with self.assertRaises(Unavailable):
            Down("id", "secret").convention("1234")

    def test_k4_unknown_idcc_when_the_base_is_fine(self):
        from citecheck.countries.france.legifrance import Client, Unavailable

        class Picky(Client):
            def _post(self, route, body):
                if body["id"] == "1979":
                    return {"titre": "HCR", "texteBaseId": ["KALITEXT1"]}
                raise Unavailable("HTTP 500", 500)
        self.assertIsNone(Picky("id", "secret").convention("9998"))

    def test_k6_no_document_word_left(self):
        cit = {"kind": "decision", "order": "lower", "court": "CA Dupont Martin",
               "place": "Dupont Martin", "number": "11/18803", "cited_date": None,
               "verdict": "NOT_TESTED",
               "explanation": "cour d'appel « Dupont Martin » non reconnue"}
        r = report.without_excerpts(report.build("doc.pdf", "france", [cit], []))
        self.assertNotIn("Dupont", report.to_json(r))
        self.assertNotIn("Dupont", report.to_text(r))

    def test_k10_deeply_nested_odt_is_refused(self):
        import tempfile
        import zipfile
        from citecheck.reader import Unreadable, text_of
        ns = 'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"'
        deep = "<text:span>" * 5000 + "mot " * 10 + "</text:span>" * 5000
        with tempfile.NamedTemporaryFile(suffix=".odt", delete=False) as f:
            with zipfile.ZipFile(f, "w") as z:
                z.writestr("content.xml", f"<r {ns}><text:p>{deep}</text:p></r>")
        with self.assertRaises(Unreadable):
            text_of(f.name)


class Scope(unittest.TestCase):
    def test_every_displayed_abbreviation_is_recognized(self):
        """The "what is checked" tab must not promise an abbreviation we do not read."""
        for forms, _, title in ABBREVIATIONS:
            for form in forms:
                self.assertEqual(find_code(f"art. 1 {form} x")[0], title, form)

    def test_every_title_is_recognized_whole(self):
        """A title that is the prefix of another (Code minier / Code minier (nouveau), the
        CGI and its annexes) must not swallow the longer one."""
        self.assertEqual(len(TITLES), 76)
        for title in TITLES:
            self.assertEqual(find_code(f"art. 1 du {title}, x")[0], title, title)

    def test_a_code_learned_from_legifrance_is_recognized(self):
        saved = list(TITLES)
        try:
            self.assertIsNone(find_code("art. 3 du Code imaginaire des essais, x"))
            self.assertEqual(learn(["Code civil", "Code imaginaire des essais"]),
                             ["Code imaginaire des essais"])
            self.assertEqual(find_code("art. 3 du Code imaginaire des essais, x")[0],
                             "Code imaginaire des essais")
        finally:
            TITLES[:] = saved
            codes._build()


class FakeLegifrance:
    """Codes et articles en mémoire : {titre: {numéro: [versions]}}."""

    def __init__(self, articles):
        self.articles = articles

    def codes(self):
        return {title: f"LEGITEXT{i}" for i, title in enumerate(self.articles)}

    def versions(self, title, code_id, number):
        return self.articles[title].get(number, [])


class AmbiguousCode(unittest.TestCase):
    V = [{"id": "x", "etat": "VIGUEUR", "debut": "2011-03-01", "fin": "2999-01-01"}]

    def check(self, new, old):
        client = FakeLegifrance({"Code minier (nouveau)": new, "Code minier": old})
        return check_article(client, {"code": "Code minier", "number": "L111-1"},
                             "2026-09-30", {})

    def test_found_in_one_says_which(self):
        verdict, why, _ = self.check({"L111-1": self.V}, {})
        self.assertEqual(verdict, "ARTICLE_IN_FORCE")
        self.assertIn("n'existe que dans le Code minier (nouveau)", why)

    def test_found_in_both_does_not_choose(self):
        verdict, why, _ = self.check({"L111-1": self.V}, {"L111-1": self.V})
        self.assertEqual(verdict, "DOUBTFUL")
        self.assertIn("à vous de dire", why)

    def test_found_in_neither(self):
        self.assertEqual(self.check({}, {})[0], "ARTICLE_NOT_FOUND")


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
        self.assertEqual(verdict_judicial(None, "2019-03-21", "1987")[0], "NOT_PUBLISHED")
        self.assertEqual(verdict_judicial(None, "1983-03-21", "1987")[0], "UNVERIFIABLE_PERIOD")
        self.assertEqual(verdict_judicial(None, None, "1987")[0], "UNVERIFIABLE_PERIOD")
        self.assertEqual(verdict_judicial({"_err": "HTTP 500"}, None)[0], "ERROR")


class Report(unittest.TestCase):
    def test_without_excerpts_leaves_no_document_text(self):
        secret = "Madame Dupont, licenciée le 3 mars"
        cit = {"kind": "article", "code": "Code civil", "number": "1240", "court": "Code civil",
               "quote": secret, "verdict": "ARTICLE_IN_FORCE", "explanation": "x",
               "location": {"page": 1, "page_exact": True, "in_notes": False,
                            "excerpt": secret}}
        r = report.without_excerpts(report.build("doc.pdf", "france", [cit], []))
        self.assertNotIn(secret, report.to_json(r))
        self.assertNotIn(secret, report.to_text(r))
        self.assertIn("1240", report.to_json(r))

    def test_disclaimer_always_present(self):
        r = report.build("empty.txt", "france", [], [])
        self.assertIn("sans garantie", report.to_text(r))
        self.assertIn("sans garantie", json.loads(report.to_json(r))["disclaimer"])


if __name__ == "__main__":
    unittest.main()
