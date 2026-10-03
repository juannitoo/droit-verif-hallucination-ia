"""Offline tests: extraction, verdicts, report. The network is tested with
`python -m citecheck --case cases/perigueux.json`."""
import json
import unittest
import warnings
from pathlib import Path

from citecheck import report
from citecheck.countries.france import codes
from citecheck.countries.france.codes import (ABBREVIATIONS, ABROGATED, TITLES, find_code,
                                              learn)
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


class OtherCourts(unittest.TestCase):
    """Point A (30/09/2026): numbers of courts this program does not check must never be
    sent to ArianeWeb as Conseil d'État requests."""

    def orders(self, text):
        from citecheck.countries.france import check
        citations, _ = extract(text)
        results = check([c for c in citations if c["order"] == "other"], {})
        return ([(c["order"], c["court"], c["number"], c["cited_date"]) for c in citations],
                {r["verdict"] for r in results})

    def test_echr_is_shown_with_its_link_and_conflicts_is_checked(self):
        from citecheck.countries.france import verdict_other
        seen, verdicts = self.orders(
            "CEDH, 25 mars 1993, Costello-Roberts c. Royaume-Uni, n° 13134/87. "
            "T. confl., 8 février 1873, Blanco, n° 00012.")
        self.assertEqual(seen, [("other", "CEDH", "13134/87", "1993-03-25"),
                                ("conflicts", "T. confl.", "00012", "1873-02-08")])
        self.assertEqual(verdicts, {"MANUAL_CHECK"})
        _, why, _, link = verdict_other({"court": "CEDH", "number": "13134/87"})
        self.assertIn("n'autorise pas", why)
        self.assertEqual(
            "https://hudoc.echr.coe.int/fre#%7B%22appno%22%3A%5B%2213134%2F87%22%5D%7D", link)

    def test_slash_year_is_never_a_ce_request(self):
        seen, _ = self.orders("Requête n° 45678/12.")
        self.assertEqual(seen, [("other", "juridiction non nommée", "45678/12", None)])

    def test_court_is_read_in_the_same_sentence_only(self):
        seen, _ = self.orders("T. confl., 8 février 1873, n° 00012. Voir CE, n° 298348.")
        self.assertEqual([s[0] for s in seen], ["conflicts", "administrative"])

    def test_parties_c_is_not_a_sentence_end(self):
        seen, _ = self.orders("CE, 30 octobre 2009, Mme Perreux c. Ministre, n° 298348.")
        self.assertEqual(seen, [("administrative", "CE", "298348", "2009-10-30")])

    def test_ce_is_not_read_inside_cedh(self):
        seen, _ = self.orders("Cour EDH, n° 13134.")
        self.assertEqual(seen[0][:2], ("other", "CEDH"))


class SeenNotChecked(unittest.TestCase):
    """Point B (30/09/2026): whatever is seen and not checked must be in the report."""

    def seen(self, text):
        citations, remarks = extract(text)
        return [(c["order"], c["court"], c["number"], c["cited_date"]) for c in citations], remarks

    def test_decisions_without_number(self):
        seen, remarks = self.seen(
            "Voir CE, Ass., 30 octobre 2009, Mme Perreux. La Cour de cassation (Cass. soc., "
            "10 juillet 2013) l'a jugé. T. com. Paris, 9 janvier 2026, RG 2024F00234. "
            "CA Paris, 2 octobre 2013. Cass. Com., 3 mars 2020.")
        self.assertEqual(seen, [("unnumbered", "CE", None, "2009-10-30"),
                                ("unnumbered", "Cass.", None, "2013-07-10"),
                                ("lower", "T. com. Paris", "2024F00234", "2026-01-09"),
                                ("unnumbered", "CA", None, "2013-10-02"),
                                ("unnumbered", "Cass.", None, "2020-03-03")])
        self.assertFalse(any("None" in r for r in remarks))

    def test_not_a_decision(self):
        seen, _ = self.seen("La Cour de cassation applique la loi du 6 juillet 1989. "
                            "Le Conseil d'État a jugé le 5 juin 2009 que ce 12 mars 2019 était "
                            "loin. On lit ce 5 mars 2020.")
        self.assertEqual(seen, [("unnumbered", "CE", None, "2009-06-05")])

    def test_numbered_then_repeated_is_one_decision(self):
        seen, _ = self.seen("CE, 5 juin 2009, n° 308850. Le Conseil d'État, le 5 juin 2009, "
                            "a jugé.")
        self.assertEqual(seen, [("administrative", "CE", "308850", "2009-06-05")])

    def test_caa_and_ta_never_go_to_arianeweb(self):
        seen, _ = self.seen("CAA Bordeaux, 3 mars 2022, n° 21BX01234. TA Paris, 5 mai 2020, "
                            "n° 1901234. Tribunal administratif de Lyon, n° 2001234.")
        self.assertEqual([s[:3] for s in seen], [("caa", "CAA", "21BX01234"),
                                                 ("ta", "TA", "1901234"),
                                                 ("ta", "TA", "2001234")])

    def test_caa_title_filter(self):
        from citecheck.countries.france.other_courts import administrative_appeal

        class Fake:
            def decisions(self, fond, number):
                return [(t, "CETATEXT000000000001") for t in ["CAA de NANCY, 2ème chambre, 12/04/2018, 17NC01414, Inédit",
                        "Cour administrative d'appel de Paris, du 3 mars 2005, 17NC01414",
                        "Conseil d'État, 12/04/2019, 17NC01414, Inédit",
                        "CAA de LYON, 12/04/2020, 17NC014145, Inédit"]]
        self.assertEqual(administrative_appeal(Fake(), "17NC01414"),
                         ["2005-03-03", "2018-04-12"])

    def test_verdicts_say_why(self):
        from citecheck.countries.france import verdict_other
        why = verdict_other({"order": "unnumbered", "court": "CE", "number": None})[1]
        self.assertIn("nom des parties", why)
        why = verdict_other({"order": "unnumbered", "court": "CPH", "number": None})[1]
        self.assertIn("Judilibre ne les publie pas", why)

    def test_report_line(self):
        r = report.build("x", "france", [{"kind": "decision", "order": "unnumbered",
                                          "court": "CE", "number": None,
                                          "cited_date": "2009-10-30",
                                          "verdict": "MANUAL_CHECK", "explanation": "e"}], [])
        self.assertIn("CE, décision du 2009-10-30 (aucun numéro lu)", report.to_text(r))


class CommercialCourts(unittest.TestCase):
    def test_extraction(self):
        citations, _ = extract(
            "T. com. Paris, 9 janvier 2026, RG 2024F00234. Le tribunal de commerce de "
            "Bordeaux, le 9 janvier 2026, n° 2025J00123. TAE Nanterre, 3 mars 2026, "
            "J2026000698. Tribunal des activités économiques de Lyon, 5 mai 2026, n° "
            "2026004078. Appelez le 2026004078. T. com. Castres, 6 juillet 2026.")
        self.assertEqual([(c["order"], c["court"], c["number"], c["cited_date"])
                          for c in citations], [
            ("lower", "T. com. Paris", "2024F00234", "2026-01-09"),
            ("lower", "T. com. Bordeaux", "2025J00123", "2026-01-09"),
            ("lower", "T. com. Nanterre", "J2026000698", "2026-03-03"),
            ("lower", "T. com. Lyon", "2026004078", "2026-05-05"),
            ("unnumbered", "T. com.", None, "2026-07-06")])

    def test_date_before_the_registration_year(self):
        from citecheck.countries.france.lower_courts import check_lower_court
        c = {"jurisdiction": "tcom", "place": "Paris", "number": "2025F00234",
             "cited_date": "2024-03-12"}
        verdict, why, *_ = check_lower_court(None, c)     # no network needed
        self.assertEqual(verdict, "DATE_BEFORE_NUMBER")
        self.assertIn("2025", why)

    def test_tae_is_found_under_its_city(self):
        from citecheck.countries.france.lower_courts import _simplify
        self.assertEqual(_simplify("Tribunal des activités économiques de Paris"), "paris")
        self.assertEqual(_simplify("Tribunal de commerce d'Arras"), "arras")

    def test_a_city_with_its_article(self):
        """« TJ Le Mans » est le « Tribunal judiciaire du Mans » de Judilibre."""
        from citecheck.countries.france.lower_courts import _simplify
        for official, written in [("Tribunal judiciaire du Mans", "Le Mans"),
                                  ("Tribunal judiciaire des Sables-d'Olonne",
                                   "Les Sables-d'Olonne"),
                                  ("Tribunal de commerce du Havre", "Le Havre"),
                                  ("Tribunal judiciaire de La Rochelle", "La Rochelle")]:
            self.assertEqual(_simplify(official), _simplify(written), official)
        for text, place in [("Tribunal judiciaire du Mans, 5 juin 2009, RG n° 11/18803.",
                             "Le Mans"),
                            ("TJ du Puy-en-Velay, 5 juin 2009, RG n° 11/18803.",
                             "Le Puy-en-Velay"),
                            ("tribunal judiciaire des Sables-d'Olonne, 5 juin 2009, RG n° "
                             "11/18803.", "Les Sables-d'Olonne"),
                            ("TJ Le Mans, 5 juin 2009, RG n° 11/18803.", "Le Mans"),
                            ("tribunal judiciaire du Le Mans, 5 juin 2009, RG n° 11/18803.",
                             "Le Mans"),
                            ("T. com. du Havre, 5 juin 2009, n° 2025J05588.", "Le Havre")]:
            self.assertEqual([c["place"] for c in extract(text)[0]], [place], text)
        self.assertEqual(
            [extract(t)[0][0]["span"] for t in ["TJ du Mans, 5 juin 2009, RG n° 11/18803."]],
            [(0, 39)])


class LocalAdministrativeBase(unittest.TestCase):
    """A local database built from opendata.justice-administrative.fr, on localhost."""
    DECISIONS = {("CAA", "23MA02610"): "2023-12-29", ("CAA", "23PA00439"): "2023-12-29",
                 ("TA", "2301234"): "2023-05-12"}

    def serve(self, liar=False):
        import http.server
        import threading
        from urllib.parse import parse_qs, urlparse
        decisions = self.DECISIONS

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                url = urlparse(self.path)
                q = {k: v[0] for k, v in parse_qs(url.query).items()}
                if url.path == "/coverage":
                    body = {"CAA": "2022-03-01", "TA": "2022-06-01"}
                else:
                    day = "2023-01-01" if liar else decisions.get((q["court"], q["number"]))
                    body = {"decisions": [{"number": q["number"], "date": day}] if day else []}
                data = json.dumps(body).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *args):
                pass

        server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return f"http://127.0.0.1:{server.server_port}"

    def check(self, number, day, url):
        from citecheck.countries.france import LOCAL_BASE, check
        c = {"kind": "decision", "order": "ta", "court": "TA", "number": number,
             "cited_date": day}
        return check([c], {LOCAL_BASE: url} if url else {})[0]["verdict"]

    def test_verdicts(self):
        url = self.serve()
        self.assertEqual(self.check("2301234", "2023-05-12", url), "CONFIRMED")
        self.assertEqual(self.check("2301234", "2023-05-13", url), "WRONG_DATE")
        self.assertEqual(self.check("2399998", "2023-05-12", url), "NOT_PUBLISHED")
        self.assertEqual(self.check("2199998", "2021-05-12", url), "UNVERIFIABLE_PERIOD")

    def test_without_a_local_base_ta_is_shown(self):
        self.assertEqual(self.check("2301234", "2023-05-12", None), "MANUAL_CHECK")

    def test_a_base_that_says_yes_to_everything_is_not_believed(self):
        self.assertEqual(self.check("2301234", "2023-05-12", self.serve(liar=True)),
                         "MANUAL_CHECK")


class ConstitutionalConflictsEu(unittest.TestCase):
    def test_extraction(self):
        citations, _ = extract(
            "Cons. const., 12 mai 2010, n° 2010-605 DC. Décision n° 2010-14/22 QPC. "
            "TC, 17 juin 2013, Bergoend, n° C3911. T. confl., n° 4112. "
            "CJUE, 6 octobre 2021, C‑561/19. Tribunal de l'Union, T-12/15. "
            "Loi n° 2010-3 L. Voir T-12/15.")
        self.assertEqual([(c["order"], c["number"], c["cited_date"]) for c in citations], [
            ("constitutional", "2010-605", "2010-05-12"),
            ("constitutional", "2010-14/22", None),
            ("conflicts", "C3911", "2013-06-17"),
            ("conflicts", "4112", None),
            ("eu", "C-561/19", "2021-10-06"),
            ("eu", "T-12/15", None)])

    def test_celex(self):
        from citecheck.countries.france.other_courts import celex_numbers
        self.assertEqual(celex_numbers("C-561/19"),
                         ["62019CJ0561", "62019CO0561", "62019CV0561"])
        self.assertEqual(celex_numbers("T-12/89"), ["61989TJ0012", "61989TO0012"])
        self.assertEqual(celex_numbers("13134/87"), [])

    def test_verdicts(self):
        from citecheck.countries.france import verdict_dates
        self.assertEqual(verdict_dates([], "2010-05-12", "Légifrance")[0], "NOT_PUBLISHED")
        self.assertEqual(verdict_dates(["2010-05-12"], "2010-05-12", "L")[0], "CONFIRMED")
        self.assertEqual(verdict_dates(["2010-05-12"], "2010-05-13", "L")[0], "WRONG_DATE")
        self.assertEqual(verdict_dates(["2010-05-12"], None, "L")[0], "EXISTS_DATE_UNCHECKED")

    def test_conflicts_keeps_only_the_tribunal(self):
        """00012 is Blanco AND a Conseil d'État decision of 1977."""
        from citecheck.countries.france.other_courts import conflicts

        class Fake:
            def decisions(self, fond, number):
                return [(t, "CETATEXT000000000002") for t in {"00012": [
                    "Conseil d'Etat, 6 / 2 SSR, du 21 octobre 1977, 00012, mentionné aux tables",
                    "Tribunal des conflits, du 8 février 1873, 00012, publié au recueil Lebon"],
                    "C4112": ["Tribunal des Conflits, , 12/02/2018, C4112, Publié au recueil"],
                }.get(number, [])]
        self.assertEqual(conflicts(Fake(), "00012"), ["1873-02-08"])
        self.assertEqual(conflicts(Fake(), "00012").links,
                         {"1873-02-08": "https://www.legifrance.gouv.fr/ceta/id/"
                                        "CETATEXT000000000002"})
        self.assertEqual(conflicts(Fake(), "4112"), ["2018-02-12"])


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
        # La loi : relevée comme article de loi, jamais attribuée à un code.
        self.assertEqual([(c["text_date"], c["number"]) for c in citations
                          if c["kind"] == "text_article"], [("1989-07-06", "22")])

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
        from unittest import mock
        from citecheck.countries.france.lower_courts import check_lower_court
        cit = {"kind": "decision", "order": "lower", "court": "CA Dupont Martin",
               "jurisdiction": "ca", "place": "Dupont Martin", "number": "11/18803",
               "cited_date": None}
        v, why, actual = check_lower_court(mock.Mock(**{"location.return_value": None}), cit)
        cit = {**cit, "verdict": v, "explanation": why, "actual_date": actual}
        r = report.without_excerpts(report.build("Dupont c. Martin.pdf", "france", [cit], []))
        self.assertNotIn("Dupont", report.to_json(r))
        self.assertNotIn("Dupont", report.to_text(r))

    def test_a_long_quote_does_not_carry_the_document(self):
        long = "Madame Dupont " + "et les faits " * 400
        cit = {"kind": "article", "code": "Code civil", "number": "1240", "court": "Code civil",
               "quote": long, "verdict": "ARTICLE_IN_FORCE", "explanation": "x"}
        r = report.build("doc.pdf", "france", [cit], [])
        self.assertLessEqual(len(r["citations"][0]["quote"]), report.QUOTE_MAX)

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

    def test_every_abrogated_title_is_recognized_whole(self):
        self.assertEqual(len(ABROGATED), 32)
        for title in ABROGATED:
            self.assertEqual(find_code(f"art. 1 du {title}, x")[0], title, title)

    def test_usual_forms_of_old_codes(self):
        for text, title in [("Code des marchés publics", "Code des marchés publics"),
                            ("ancien Code pénal", "Code pénal (ancien)"),
                            ("code forestier", "Code forestier"),
                            ("Code rural", "Code rural"),
                            ("Code rural et de la pêche maritime",
                             "Code rural et de la pêche maritime")]:
            self.assertEqual(find_code(f"art. 1 du {text}, x")[0], title, text)

    def test_an_abrogated_code_is_not_learned_as_new(self):
        self.assertEqual(learn(["Code pénal (ancien)", "Code forestier"]), [])

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


class RecodifiedArticle(unittest.TestCase):
    """CESEDA L611-1 (relevé le 02/10/2026) : deux articles successifs sous le même numéro,
    chacun avec sa fiche. Avant : « liste des versions incohérente »."""

    def client(self, sheets, found):
        from citecheck.countries.france.legifrance import Client
        c = object.__new__(Client)
        c._search_versions = lambda *a: found
        c._post = lambda route, body: {"article": {"articleVersions": sheets[body["id"]]}}
        return c

    MS = {"2005": 1109635200000, "2013": 1357084800000, "2021": 1619827200000,
          "2999": 32472144000000}

    def test_two_chains_are_merged(self):
        ms = self.MS
        old = [{"id": "o1", "etat": "MODIFIE", "dateDebut": ms["2005"], "dateFin": ms["2013"]},
               {"id": "o2", "etat": "ABROGE", "dateDebut": ms["2013"], "dateFin": ms["2021"]}]
        new = [{"id": "n1", "etat": "VIGUEUR", "dateDebut": ms["2021"], "dateFin": ms["2999"]}]
        found = [{"id": i} for i in ("o1", "o2", "n1")]
        versions = self.client({"o1": old, "o2": old, "n1": new}, found).versions("C", "X", "L611-1")
        self.assertEqual([(v["id"], v["debut"]) for v in versions],
                         [("o1", "2005-03-01"), ("o2", "2013-01-02"), ("n1", "2021-05-01")])

    def test_two_in_force_the_same_day_is_not_chosen(self):
        from citecheck.countries.france.legifrance import Unavailable
        ms = self.MS
        a = [{"id": "a", "etat": "VIGUEUR", "dateDebut": ms["2013"], "dateFin": ms["2999"]}]
        b = [{"id": "b", "etat": "VIGUEUR", "dateDebut": ms["2021"], "dateFin": ms["2999"]}]
        with self.assertRaises(Unavailable):
            self.client({"a": a, "b": b}, [{"id": "a"}, {"id": "b"}]).versions("C", "X", "L1")


class AmbiguousCode(unittest.TestCase):
    V = [{"id": "x", "etat": "VIGUEUR", "debut": "2011-03-01", "fin": "2999-01-01"}]

    def check(self, new, old):
        client = FakeLegifrance({"Code minier (nouveau)": new, "Code minier": old})
        return check_article(client, {"code": "Code minier", "number": "L111-1"},
                             "2026-09-30", {})

    def test_found_in_one_says_which(self):
        verdict, why, *_ = self.check({"L111-1": self.V}, {})
        self.assertEqual(verdict, "DOUBTFUL")       # jamais bleu : peut-être l'autre code
        self.assertIn("n'existe que dans le Code minier (nouveau)", why)

    def test_found_in_both_does_not_choose(self):
        verdict, why, *_ = self.check({"L111-1": self.V}, {"L111-1": self.V})
        self.assertEqual(verdict, "DOUBTFUL")
        self.assertIn("à vous de dire", why)

    def test_found_in_neither(self):
        self.assertEqual(self.check({}, {})[0], "ARTICLE_NOT_FOUND")


class TaxCodeNumbers(unittest.TestCase):
    """Point E (30/09/2026): stacked suffixes of the CGI, and its annexes."""

    def read(self, text):
        return [(c["code"], c["number"]) for c in extract(text)[0]]

    def test_stacked_suffixes(self):
        cgi = "Code général des impôts"
        for text, number in [("article 46 quater-0 ZZ bis du CGI.", "46 quater-0 ZZ bis"),
                             ("article 199 undecies B du CGI.", "199 undecies B"),
                             ("article 150-0 A du CGI.", "150-0 A"),
                             ("CGI, art. 238 bis-0 I.", "238 bis-0 I"),
                             ("article 302 bis ZA du CGI.", "302 bis ZA"),
                             ("article 1649 quater-0 B bis du CGI.", "1649 quater-0 B bis"),
                             ("article 81 A du CGI.", "81 A"),
                             ("article 209-0 B du CGI.", "209-0 B")]:
            self.assertEqual(self.read(text), [(cgi, number)], text)
        self.assertEqual(self.read("article L. 80 A du LPF."),
                         [("Livre des procédures fiscales", "L80 A")])

    def test_what_is_not_a_suffix(self):
        self.assertEqual(self.read("art. 1240 C. civ."), [("Code civil", "1240")])
        self.assertEqual(self.read("art. 1240 C. Civ."), [("Code civil", "1240")])
        self.assertEqual(self.read("article 700 CPC."), [("Code de procédure civile", "700")])
        self.assertEqual(self.read("article L. 1152-1 C. trav."), [("Code du travail", "L1152-1")])

    def test_annexes(self):
        a3 = "Code général des impôts, annexe III"
        self.assertEqual(self.read("article 46 quater-0 ZZ bis de l'annexe III au CGI."),
                         [(a3, "46 quater-0 ZZ bis")])
        self.assertEqual(self.read("CGI, ann. III, art. 2."), [(a3, "2")])
        self.assertEqual(self.read("article 171 AB de l'annexe II au code général des impôts."),
                         [("Code général des impôts, annexe II", "171 AB")])
        self.assertEqual(self.read("article 1 de l'annexe IV du CGI."),
                         [("Code général des impôts, annexe IV", "1")])

    def test_normalization(self):
        self.assertEqual(normalize_number("46  Quater-0 ZZ   bis"), "46 quater-0 ZZ bis")
        self.assertEqual(normalize_number("L. 80 A"), "L80 A")


class Succession(unittest.TestCase):
    """Point C (30/09/2026): a code and its abrogated editions."""
    NOW = [{"id": "n", "etat": "VIGUEUR", "debut": "2012-07-01", "fin": "2999-01-01"}]
    OLD = [{"id": "o", "etat": "ABROGE", "debut": "1979-02-07", "fin": "2012-07-01"}]

    def check(self, new, old, code="Code forestier", day="2026-09-30"):
        client = FakeLegifrance({"Code forestier (nouveau)": new, "Code forestier": old,
                                 "Code pénal": new, "Code pénal (ancien)": old})
        return check_article(client, {"code": code, "number": "L124-1"}, day, {})

    def test_the_named_code_in_force_is_silent(self):
        verdict, why, *_ = self.check({"L124-1": self.NOW}, {"L124-1": self.OLD}, "Code pénal")
        self.assertEqual(verdict, "ARTICLE_IN_FORCE")
        self.assertNotIn("ancien", why)

    def test_code_forestier_means_the_new_one(self):
        verdict, why, *_ = self.check({"L124-1": self.NOW}, {"L124-1": self.OLD})
        self.assertEqual(verdict, "ARTICLE_IN_FORCE")
        self.assertIn("dans le Code forestier (nouveau)", why)

    def test_the_date_of_the_facts_finds_the_old_one(self):
        verdict, why, *_ = self.check({"L124-1": self.NOW}, {"L124-1": self.OLD},
                                     day="2010-06-01")
        self.assertEqual(verdict, "ARTICLE_IN_FORCE")
        self.assertIn("il l'est dans l'ancien Code forestier", why)

    def test_only_in_the_old_one_is_abrogated_not_missing(self):
        verdict, why, *_ = self.check({}, {"L124-1": self.OLD}, "Code pénal")
        self.assertEqual(verdict, "ARTICLE_NOT_IN_FORCE")
        self.assertIn("abrogé ou déplacé le 2012-07-01", why)

    def test_in_none(self):
        self.assertEqual(self.check({}, {})[0], "ARTICLE_NOT_FOUND")

    def test_two_editions_in_force_never_blue(self):
        """Audit du 02/10/2026 (11) : l'ancien Code rural est encore en partie en vigueur."""
        client = FakeLegifrance({"Code rural et de la pêche maritime": {"L1": self.NOW},
                                 "Code rural (ancien)": {"L1": self.NOW}})
        verdict, why, *_ = check_article(client, {"code": "Code rural", "number": "L1"},
                                         "2026-09-30", {})
        self.assertEqual(verdict, "DOUBTFUL")
        self.assertIn("vérifiez quelle édition", why)

    def test_only_in_an_older_edition_never_blue(self):
        verdict, why, *_ = self.check({}, {"L124-1": self.OLD}, day="2010-06-01")
        self.assertEqual(verdict, "DOUBTFUL")    # le nouveau n'a pas ce numéro : erreur ?


class Constitution(unittest.TestCase):
    """La Constitution de 1958 et la Déclaration de 1789 (sonde probes/constitution.py)."""
    V = [{"id": "LEGIARTI000019241077", "etat": "VIGUEUR", "debut": "2008-07-25",
          "fin": "2999-01-01"}]

    class Fake:
        def __init__(self, articles):
            self.articles = articles        # {(identifiant du texte, numéro): versions}

        def block_article_versions(self, text_id, number, days):
            return self.articles.get((text_id, number), [])

    def read(self, text):
        return [(c["kind"], c["number"], c["court"]) for c in extract(text, unverified=True)[0]]

    def test_attached(self):
        const, ddhc = "Constitution du 4 octobre 1958", ("Déclaration des droits de l'homme et du "
                                                        "citoyen de 1789")
        self.assertEqual(self.read("l'article 61-1 de la Constitution."),
                         [("text_article", "61-1", const)])
        self.assertEqual(self.read("l'article 16 de la Déclaration de 1789."),
                         [("text_article", "16", ddhc)])
        self.assertEqual(self.read("l'article 6 de la Déclaration des droits de l'homme et du "
                                   "citoyen du 26 août 1789."), [("text_article", "6", ddhc)])
        self.assertEqual(self.read("les articles 6 et 16 de la Déclaration de 1789 ; que"),
                         [("text_article", "6", ddhc), ("text_article", "16", ddhc)])
        # un code nommé plus tôt dans la phrase n'en fait pas douter (décision du CE du
        # 30/09/2026) ; un code écrit devant l'article, si
        self.assertEqual(self.read(
            "les dispositions du livre IV du code de l'entrée et du séjour des étrangers et du "
            "droit d'asile méconnaissent le droit à un recours effectif, garanti par l'article "
            "16 de la Déclaration de 1789."), [("text_article", "16", ddhc)])
        self.assertEqual([k for k, *_ in self.read("C. civ., art. 16 de la Constitution.")],
                         ["unverified"])
        # d'autres textes : jamais pris pour ceux-là
        for text in ("l'article 7 de la Déclaration universelle des droits de l'homme.",
                     "l'article 13 de la Constitution du 27 octobre 1946.",
                     "l'article 13 de la Constitution de 1946."):
            self.assertEqual([k for k, *_ in self.read(text)], ["unverified"], text)

    def test_checked(self):
        from citecheck import report
        from citecheck.countries.france.texts import check_text_article
        from citecheck.countries.france.wire import refusal
        const = extract("l'article 61-1 de la Constitution.")[0][0]
        ddhc = extract("l'article 18 de la Déclaration de 1789.")[0][0]
        self.assertIsNone(refusal(const))
        fake = self.Fake({("LEGITEXT000006071194", "61-1"): self.V})
        verdict, why, *_ = check_text_article(fake, const, "2026-09-30", {})
        self.assertEqual(report.light(verdict), report.CONFIRMED)
        self.assertEqual(check_text_article(fake, const, "2005-01-01", {})[0],
                         "ARTICLE_NOT_IN_FORCE")
        # absent de la Constitution : peut-être abrogé depuis longtemps, à vérifier
        verdict, why, *_ = check_text_article(self.Fake({}), const, "2026-09-30", {})
        self.assertEqual(verdict, "DOUBTFUL")
        # la Déclaration n'a jamais eu que 17 articles
        self.assertEqual(check_text_article(self.Fake({}), ddhc, "2026-09-30", {})[0],
                         "ARTICLE_NOT_FOUND")
        # un identifiant qui n'est pas celui d'un de ces textes ne part pas
        self.assertIsNotNone(refusal({**const, "text_id": "LEGITEXT000000000001"}))


class UncodifiedTexts(unittest.TestCase):
    """Articles of laws, ordinances and decrees that are not in a code."""
    V = [{"id": "x", "etat": "VIGUEUR", "debut": "2014-03-27", "fin": "2999-01-01"}]

    class Fake:
        def __init__(self, texts):
            self.texts = texts      # {id: (title, {article: versions})}

        def texts_by_number(self, number):
            return [(i, t) for i, (t, _) in self.texts.items() if f"n° {number} " in t]

        def texts_by_title(self, words, nature):
            return [(i, t) for i, (t, _) in self.texts.items() if words in t]

        def text_article_versions(self, text_number, text_id, number):
            return self.texts[text_id][1].get(number, [])

        def jorf_articles(self, text_number, number):
            return getattr(self, "jorf", {}).get((text_number, number), [])

        def text_state(self, text_id, day):
            # (état, depuis), « Vigueur » depuis 1992 sauf indication (états de legiPart)
            return getattr(self, "states", {}).get(text_id, ("Vigueur", "1992-01-01"))

    def check(self, texts, **citation):
        from citecheck.countries.france.texts import check_text_article
        c = {"kind": "text_article", "text_nature": "LOI", "text_number": None,
             "text_date": None, "number": "22", **citation}
        return check_text_article(self.Fake(texts), c, "2026-09-30", {})

    def test_by_number(self):
        texts = {"A": ("Loi n° 89-462 du 6 juillet 1989 tendant", {"22": self.V})}
        self.assertEqual(self.check(texts, text_number="89-462")[0], "ARTICLE_IN_FORCE")
        verdict, why, *_ = self.check(texts, text_number="89-462", text_date="1989-07-07")
        self.assertEqual(verdict, "WRONG_DATE")
        self.assertIn("datée du 1989-07-06, pas du 1989-07-07", why)
        self.assertEqual(self.check(texts, text_number="89-9999")[0], "TEXT_NOT_FOUND")
        self.assertEqual(self.check(texts, text_number="89-462", number="999")[0],
                         "ARTICLE_NOT_FOUND")

    def test_by_date_shows_which_one(self):
        texts = {"A": ("Loi n° 89-461 du 6 juillet 1989 modifiant", {}),
                 "B": ("Loi n° 89-462 du 6 juillet 1989 tendant", {"22": self.V}),
                 "C": ("Loi n° 90-1 du 2 janvier 1990 modifiant la loi n° 89-462 du 6 juillet "
                       "1989", {"22": self.V})}
        verdict, why, *_ = self.check(texts, text_date="1989-07-06")
        self.assertEqual(verdict, "DOUBTFUL")       # jamais bleu : peut-être l'autre loi
        self.assertIn("désigne 2 textes", why)          # C is not OF that date
        self.assertIn("il n'existe que dans la loi n° 89-462", why)

    def test_by_date_does_not_choose(self):
        texts = {"A": ("Loi n° 89-461 du 6 juillet 1989 x", {"22": self.V}),
                 "B": ("Loi n° 89-462 du 6 juillet 1989 y", {"22": self.V})}
        verdict, why, *_ = self.check(texts, text_date="1989-07-06")
        self.assertEqual(verdict, "DOUBTFUL")
        self.assertIn("à vous de dire", why)

    def test_a_text_later_than_the_facts(self):
        from citecheck.countries.france.texts import check_text_article
        texts = {"A": ("Ordonnance n° 2016-131 du 10 février 2016 portant", {"1": [
            {"id": "x", "etat": "VIGUEUR", "debut": "2016-10-01", "fin": "2999-01-01"}]})}
        c = {"kind": "text_article", "text_nature": "ORDONNANCE", "text_number": "2016-131",
             "text_date": None, "number": "1"}
        verdict, why, *_ = check_text_article(self.Fake(texts), c, "2010-06-01", {})
        self.assertEqual(verdict, "ARTICLE_NOT_IN_FORCE")
        self.assertIn("le texte n'existait pas encore le 2010-06-01", why)
        self.assertIn("en vigueur depuis le 2016-10-01", why)
        self.assertIn("l'ordonnance n° 2016-131", why)

    def test_nature_must_match(self):
        texts = {"A": ("Décret n° 89-462 du 6 juillet 1989 x", {"22": self.V})}
        self.assertEqual(self.check(texts, text_number="89-462")[0], "TEXT_NOT_FOUND")

    def test_an_article_only_in_the_journal_officiel(self):
        """« article 1er de la loi n° 2014-366 » (ALUR) : absent de la version consolidée,
        publié au JO (relevé le 02/10/2026). Ni inventé, ni confirmé."""
        from citecheck.countries.france.texts import check_text_article
        texts = {"A": ("LOI n° 2014-366 du 24 mars 2014 pour l'accès au logement", {})}
        client = self.Fake(texts)
        client.jorf = {("2014-366", "1"): [
            ("Décision n° 2014-366 du 16 juillet 2014 autorisant", "JORFARTI000029347624"),
            ("LOI n° 2014-366 du 24 mars 2014 pour l'accès au logement",
             "JORFARTI000028772281")]}
        c = {"kind": "text_article", "text_nature": "LOI", "text_number": "2014-366",
             "text_date": "2014-03-24", "number": "1"}
        verdict, why, _, link = check_text_article(client, c, "2026-09-30", {})
        self.assertEqual(verdict, "DOUBTFUL")
        self.assertIn("version publiée au Journal officiel", why)
        self.assertTrue(link.endswith("/jorf/article_jo/JORFARTI000028772281"))
        self.assertEqual(check_text_article(self.Fake(texts), c, "2026-09-30", {})[0],
                         "ARTICLE_NOT_FOUND")

    def test_a_whole_text(self):
        """Un texte cité en entier : existe-t-il, avec ce numéro, cette nature, cette date ?"""
        from citecheck.countries.france.texts import check_text
        texts = {"A": ("Loi n° 91-647 du 10 juillet 1991 relative à l'aide juridique", {}),
                 "B": ("Loi n° 89-462 du 6 juillet 1989 tendant", {}),
                 "C": ("Loi n° 89-461 du 6 juillet 1989 modifiant", {}),
                 "E": ("Ordonnance n° 2005-649 du 6 juin 2005 relative aux marchés", {}),
                 "F": ("Décret n° 2006-975 du 1 août 2006 portant code des marchés publics.",
                       {})}
        states = {"E": ("Abrogé", "2016-04-01"), "F": ("Vigueur", "2006-09-01")}

        def check(nature="LOI", number=None, day=None, reference="2026-09-30"):
            client = self.Fake(texts)
            client.states = states
            return check_text(client, {"kind": "text", "text_nature": nature,
                                       "text_number": number, "text_date": day}, reference)
        from citecheck import report
        verdict, why, *_ = check(number="91-647", day="1991-07-10")
        self.assertEqual(verdict, "TEXT_IN_FORCE")
        self.assertEqual(report.light(verdict), report.CONFIRMED)
        self.assertIn("« Loi n° 91-647 du 10 juillet 1991 relative à l'aide juridique »", why)
        self.assertEqual(check(number="91-647")[0], "TEXT_IN_FORCE")
        # pas encore en vigueur à la date de référence
        self.assertEqual(check(number="91-647", reference="1991-09-01")[0], "TEXT_NOT_IN_FORCE")
        # abrogé : jamais bleu (relevé dans Légifrance le 02/10/2026)
        verdict, why, *_ = check("ORDONNANCE", number="2005-649")
        self.assertEqual(verdict, "TEXT_NOT_IN_FORCE")
        self.assertNotEqual(report.light(verdict), report.CONFIRMED)
        self.assertIn("abrogée le 2016-04-01", why)
        # un décret « portant code » reste en vigueur, le code non : jamais bleu
        verdict, why, *_ = check("DECRET", number="2006-975")
        self.assertEqual(verdict, "DOUBTFUL")
        self.assertIn("texte de codification", why)
        verdict, why, *_ = check(number="91-647", day="1991-07-11")
        self.assertEqual(verdict, "WRONG_DATE")
        self.assertIn("datée du 1991-07-10, pas du 1991-07-11", why)
        verdict, why, *_ = check("DECRET", number="91-647")
        self.assertEqual(verdict, "DOUBTFUL")            # une loi, pas un décret
        self.assertIn("la loi n° 91-647 du 10 juillet 1991 existe", why)
        self.assertEqual(check(number="91-674")[0], "TEXT_NOT_FOUND")
        # par la date seule : un texte, bleu ; plusieurs, on ne choisit pas ; aucun, rouge
        self.assertEqual(check(day="1991-07-10")[0], "TEXT_IN_FORCE")
        self.assertEqual(check(day="1989-07-06")[0], "NOT_TESTED")
        self.assertEqual(check(day="1991-07-12")[0], "TEXT_NOT_FOUND")
        texts["D"] = ("Loi du 29 juillet 1881 sur la liberté de la presse", {})
        self.assertEqual(check(day="1881-07-29")[0], "NOT_TESTED")      # titre sans numéro

    def test_whole_texts_are_found(self):
        from citecheck.countries.france import extract as country_extract
        text = ("Vu la loi n° 91-647 du 10 juillet 1991 relative à l'aide juridique. "
                "L'ordonnance du 26 juin 2023 a fixé la résidence. L'article 22 de la loi "
                "n° 89-462 du 6 juillet 1989 s'applique, dans sa rédaction issue de la loi "
                "n° 2014-366 du 24 mars 2014. La loi n° 91-647 du 10 juillet 1991 encore.")
        found = [(c["court"], text[slice(*c["span"])], len(c.get("repeats", [])))
                 for c in country_extract(text)[0] if c["kind"] == "text"]
        self.assertEqual(found, [
            ("Loi n° 91-647 du 10 juillet 1991", "loi n° 91-647 du 10 juillet 1991", 1),
            ("Loi n° 2014-366 du 24 mars 2014", "loi n° 2014-366 du 24 mars 2014", 0)])

    def test_a_title_that_does_not_read(self):
        """Audit du 02/10/2026 (11) : un texte sans numéro peut être celui que vise la pièce ;
        ni « semble inventé », ni bleu pour l'autre."""
        texts = {"A": ("Loi du 29 juillet 1881 sur la liberté de la presse", {})}
        self.assertEqual(self.check(texts, text_date="1881-07-29")[0], "NOT_TESTED")
        texts = {"A": ("Loi du 6 juillet 1989 x", {}),
                 "B": ("Loi n° 89-462 du 6 juillet 1989 y", {"22": self.V})}
        verdict, why, *_ = self.check(texts, text_date="1989-07-06")
        self.assertEqual(verdict, "DOUBTFUL")
        self.assertIn("dont le titre ne se lit pas", why)

    def test_extraction(self):
        for text, ref in [
                ("Article 22 de la loi n° 89-462 du 6 juillet 1989.", ("LOI", "89-462", "1989-07-06")),
                ("article 14 de la loi du 10 juillet 1965.", ("LOI", None, "1965-07-10")),
                ("Loi n° 89-462 du 6 juillet 1989, art. 22.", ("LOI", "89-462", "1989-07-06")),
                ("article 1er de l'ordonnance n° 2016-131 du 10 février 2016",
                 ("ORDONNANCE", "2016-131", "2016-02-10")),
                ("article 5 du décret n°67-223 du 17 mars 1967", ("DECRET", "67-223", "1967-03-17")),
                ("article 3 de la loi 89-462", ("LOI", "89-462", None)),
                ("article 1er de la loi organique n° 2009-1523 du 10 décembre 2009",
                 ("LOI", "2009-1523", "2009-12-10"))]:
            c = extract(text)[0][0]
            self.assertEqual((c["kind"], c["text_nature"], c["text_number"], c["text_date"]),
                             ("text_article",) + ref, text)
        self.assertEqual(extract("l'article 22 de la loi prévoit")[0], [])
        cits = extract("article 5 du décret n°67-223, puis l'article 6 du même décret, et "
                       "l'article 7 de la même loi.")[0]
        self.assertEqual([(c["text_number"], c["number"]) for c in cits],
                         [("67-223", "5"), ("67-223", "6")])     # « même loi » : pas un décret


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


class Chamber(unittest.TestCase):
    """The chamber of the Cour de cassation: a real decision given to the wrong chamber."""

    def test_reading(self):
        for text, code in [("Cass. soc., 10 juillet 2013, n° 12-18.273.", "soc"),
                           ("Civ. 2e, 5 mars 2019, n° 17-28.268.", "civ2"),
                           ("Cass. 1re civ., 10 avril 2019, n° 17-28.268.", "civ1"),
                           ("Cass., 3e civ., 1er mars 2020, n° 19-11.399.", "civ3"),
                           ("la première chambre civile, le 10 avril 2019, n° 17-28.268", "civ1"),
                           ("Cass. com., 3 mars 2020, n° 19-11.399.", "comm"),
                           ("Cass. crim., 3 mars 2020, n° 19-11.399.", "cr"),
                           ("Cass. ass. plén., 3 mars 2020, n° 19-11.399.", "pl"),
                           ("Ch. mixte, 3 mars 2020, n° 19-11.399.", "mi"),
                           ("Cass. civ., 3 mars 2020, n° 19-11.399.", "civ"),
                           ("Code de la sécurité sociale ; Cass., 3 mars 2020, n° 19-11.399.", None),
                           ("Sur la communication, Cass., 3 mars 2020, n° 19-11.399.", None)]:
            self.assertEqual(extract(text)[0][0]["chamber"], code, text)

    def test_chamber_written_after_the_number(self):
        cits = extract("arrêt du 7 juillet 2022, n° 21-11.484, la deuxième chambre civile a "
                       "jugé.")[0]
        self.assertEqual(cits[0]["chamber"], "civ2")
        cits = extract("Cass., 3 mars 2020, n° 19-11.399, puis Civ. 2e, 5 mars 2019, n° "
                       "18-12.345.")[0]
        self.assertEqual([c["chamber"] for c in cits], [None, "civ2"])
        cits = extract("arrêt du 7 juillet 2022, n° 21-11.484. La chambre sociale a dit.")[0]
        self.assertIsNone(cits[0]["chamber"])

    def test_two_citations_two_chambers(self):
        cits = extract("Cass. soc. 1er mars 2020 n° 19-11.399 et Civ. 2e, n° 18-12.345")[0]
        self.assertEqual([c["chamber"] for c in cits], ["soc", "civ2"])

    def test_verdicts(self):
        record = {"decision_date": "2013-07-10", "chamber": "Chambre sociale", "solution": "x"}
        self.assertEqual(verdict_judicial(record, "2013-07-10", "1987", "soc")[0], "CONFIRMED")
        verdict, why, *_ = verdict_judicial(record, "2013-07-10", "1987", "civ2")
        self.assertEqual(verdict, "WRONG_CHAMBER")
        self.assertIn("pas à la deuxième chambre civile", why)
        verdict, why, *_ = verdict_judicial(record, "2013-07-11", "1987", "civ2")
        self.assertEqual(verdict, "WRONG_DATE")
        self.assertIn("et la chambre aussi", why)
        civ1 = {"decision_date": "2019-04-10", "chamber": "Première chambre civile"}
        self.assertEqual(verdict_judicial(civ1, "2019-04-10", "1987", "civ")[0], "CONFIRMED")
        self.assertEqual(verdict_judicial(record, None, "1987", "comm")[0], "WRONG_CHAMBER")


class Verdicts(unittest.TestCase):
    def test_admin(self):
        self.assertEqual(verdict_admin(0, set(), "2009-06-05")[0], "NOT_PUBLISHED")
        self.assertEqual(verdict_admin(-1, set(), None)[0], "ERROR")
        self.assertEqual(verdict_admin(12, {"2009-06-05"}, "2009-06-05")[0], "CONFIRMED")
        self.assertEqual(verdict_admin(12, {"2009-06-05"}, "2009-06-06")[0], "WRONG_DATE")
        self.assertEqual(verdict_admin(2, set(), "2009-06-05")[0], "DOUBTFUL")

    def test_cited_by_others_is_never_confirmed(self):
        verdict, why, *_ = verdict_admin(40, set(), "2009-06-05")
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


class ReaderLimits(unittest.TestCase):
    """Audit of 30/09/2026, point 2: a crafted file must be refused cleanly, never fill the
    memory or stop the program with a raw error."""

    ODT_NS = ('xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
              'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"')
    BODY = "Voir Cass. soc., 14/12/2017, pourvoi 16-26.694, et la suite du texte."

    def setUp(self):
        import tempfile
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)

    def zipped(self, name, part, xml):
        import os
        import zipfile
        path = os.path.join(self.dir.name, name)
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr(part, xml)
        return path

    def odt(self, inner, doctype=""):
        return self.zipped("x.odt", "content.xml",
                           f'<?xml version="1.0"?>{doctype}<office:document-content '
                           f'{self.ODT_NS}><office:body><office:text><text:p>{self.BODY}'
                           f'{inner}</text:p></office:text></office:body>'
                           f'</office:document-content>')

    def test_a_huge_run_of_spaces_is_capped(self):
        from citecheck import reader
        doc = reader.read(self.odt('<text:s text:c="300000000"/>fin'))
        self.assertLess(len(doc.text), 1000)
        self.assertIn("16-26.694", doc.text)

    def test_a_run_of_spaces_that_is_not_a_number_is_refused(self):
        from citecheck import reader
        for bad in ("abc", "-5", "1e9", "٣"):        # ٣: an Arabic-Indic digit
            with self.subTest(bad=bad), self.assertRaises(reader.Unreadable):
                reader.read(self.odt(f'<text:s text:c="{bad}"/>fin'))

    def test_a_dtd_is_refused_before_its_entities_expand(self):
        from citecheck import reader
        laughs = ('<!DOCTYPE office:document-content [<!ENTITY a "aaaaaaaaaa">'
                  '<!ENTITY b "&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;">]>')
        with self.assertRaises(reader.Unreadable):
            reader.read(self.odt("&b;", laughs))
        w = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
        docx = self.zipped("x.docx", "word/document.xml",
                           '<?xml version="1.0"?><!DOCTYPE d [<!ENTITY x SYSTEM '
                           f'"file:///etc/passwd">]><w:document xmlns:w="{w}"><w:body><w:p>'
                           f'<w:r><w:t>{self.BODY} &x;</w:t></w:r></w:p></w:body></w:document>')
        with self.assertRaises(reader.Unreadable):
            reader.read(docx)

    def test_an_ordinary_odt_still_reads(self):
        from citecheck import reader
        doc = reader.read(self.odt('<text:s text:c="3"/>fin'))
        self.assertIn(self.BODY + "   fin", doc.text)

    def test_a_text_too_long_is_refused(self):
        import os
        from unittest import mock
        from citecheck import reader
        path = os.path.join(self.dir.name, "long.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.BODY * 50)
        with mock.patch.object(reader, "MAX_TEXT", 1000), self.assertRaises(reader.Unreadable):
            reader.read(path)

    def test_pdftotext_does_not_see_the_keys(self):
        import os
        from unittest import mock
        from citecheck import reader
        seen = {}

        def run(cmd, **kw):
            seen.update(kw)
            return mock.Mock(returncode=0, stdout=self.BODY)
        with mock.patch.dict(os.environ, {"PISTE_CLIENT_SECRET": "s3cret"}),                 mock.patch.object(reader.shutil, "which", return_value="/bin/pdftotext"),                 mock.patch.object(reader.subprocess, "run", run):
            reader._pdftotext(reader.Path("x.pdf"))
        self.assertNotIn("PISTE_CLIENT_SECRET", seen["env"])
        self.assertTrue(seen["timeout"])


class WireShape(unittest.TestCase):
    """Audit of 30/09/2026, point 1: whatever the caller (window, --number, --case, a
    script), only a field shaped like the extractor's output reaches a database."""

    def sent(self, citations):
        from unittest import mock
        from citecheck.countries import france
        calls = []

        def record(name):
            def f(*a, **kw):
                calls.append((name, a[0]))
                raise AssertionError("must not be reached")
            return f
        with mock.patch.object(france.sources, "ariane", record("ariane")),                 mock.patch.object(france.sources, "judilibre", record("judilibre")),                 mock.patch.object(france, "selftest_admin", return_value=True),                 mock.patch.object(france, "selftest_judicial", return_value=True),                 mock.patch.object(france, "Courts"):
            results = france.check(citations, {"PISTE_API_KEY": "k"})
        return calls, results

    def test_a_sentence_in_place_of_a_number_is_not_sent(self):
        phrase = "Madame Dupont a été licenciée le 3 mars pour faute grave"
        calls, results = self.sent([
            {"kind": "decision", "order": "administrative", "court": "CE", "number": phrase},
            {"kind": "decision", "order": "judicial", "court": "Cass", "number": phrase},
            {"kind": "decision", "order": "judicial", "court": "Cass", "number": "17-28268 x"},
            {"kind": "decision", "order": "anything", "court": "?", "number": "17-28268"},
            {"kind": "decision", "order": "constitutional", "court": "Cons. const.",
             "number": "2010-1" + "/1" * 30},
            {"kind": "article", "order": "legislation", "court": "Code civil",
             "code": "Code civil", "number": phrase},
            {"kind": "article", "order": "legislation", "court": "x", "code": phrase,
             "number": "1240"},
            {"kind": "convention_article", "order": "legislation", "court": "x",
             "idcc": phrase, "number": "1"},
        ])
        self.assertEqual(calls, [])
        self.assertEqual({r["verdict"] for r in results}, {"NOT_TESTED"})
        self.assertTrue(all("non envoyé" in r["explanation"] for r in results))

    def test_every_real_citation_passes(self):
        import glob
        from citecheck.countries.france import wire
        for f in glob.glob("cases/*.json"):
            with open(f, encoding="utf-8") as fh:
                for c in json.load(fh)["citations"]:
                    with self.subTest(case=f, number=c.get("number")):
                        self.assertIsNone(wire.refusal(c))
        for c in extract(PERIGUEUX + " Voir C. trav., art. L. 1152-1 et CGI, art. 46 "
                         "quater-0 ZZ bis ; loi n° 89-462 du 6 juillet 1989, art. 22 ; "
                         "CAA Nancy, 17NC01414 ; CJUE, C-311/18.")[0]:
            with self.subTest(number=c["number"]):
                self.assertIsNone(wire.refusal(c))


class ResponseCeiling(unittest.TestCase):
    """Audit of 30/09/2026, hardening 5: no reply is read past http.MAX_RESPONSE, and an
    oversized one is "no answer", never a verdict."""

    def opened(self, size):
        import io as _io
        from unittest import mock
        from citecheck import http
        body = _io.BytesIO(b'{"TotalCount": 0, "pad": "' + b"x" * size + b'"}')
        return mock.patch.object(http._opener, "open", return_value=body)

    def test_an_oversized_reply_is_refused_whatever_the_caller_asks(self):
        from unittest import mock
        from citecheck import http
        for n in (-1, None, 10**9):
            with self.subTest(n=n), mock.patch.object(http, "MAX_RESPONSE", 1000),                     self.opened(5000), self.assertRaises(http.TooLarge):
                with http.urlopen("https://example.invalid", timeout=1) as r:
                    while r.read(n):
                        pass

    def test_an_oversized_reply_is_not_a_verdict(self):
        from unittest import mock
        from citecheck import http
        from citecheck.countries.france import sources
        with mock.patch.object(http, "MAX_RESPONSE", 1000), self.opened(5000),                 mock.patch.object(sources.time, "sleep"):
            self.assertEqual(sources.ariane("308850"), (-1, set()))
            self.assertIn("_err", sources.judilibre("17-28268", "k"))

    def test_an_ordinary_reply_is_read_whole(self):
        from citecheck import http
        with self.opened(100):
            with http.urlopen("https://example.invalid", timeout=1) as r:
                self.assertEqual(json.loads(r.read())["TotalCount"], 0)


class LocalBaseAddress(unittest.TestCase):
    """Audit of 30/09/2026, point 3: numbers travel in clear only on this computer, and the
    rule holds for an environment variable too, which the window never sees."""

    def test_addresses(self):
        from citecheck.countries.france.other_courts import local_base_problem
        for url in ("https://decisions.ta.example.fr", "https://10.0.0.5:8443/api",
                    "http://localhost:8080", "http://127.0.0.1:5000", "http://[::1]:5000"):
            with self.subTest(url=url):
                self.assertIsNone(local_base_problem(url))
        for url in ("http://decisions.ta.example.fr", "http://10.0.0.5", "file:///C:/base",
                    "https://user:pass@decisions.example.fr", "https://169.254.169.254",
                    "https://[fe80::1]", "https://host:notaport", "decisions.example.fr",
                    "ftp://decisions.example.fr"):
            with self.subTest(url=url):
                self.assertIsNotNone(local_base_problem(url))

    def test_an_environment_variable_does_not_bypass_the_rule(self):
        import os
        from unittest import mock
        from citecheck import keys
        from citecheck.countries import france
        logs = []
        with mock.patch.dict(os.environ, {france.LOCAL_BASE: "http://base.example.fr"}),                 mock.patch.object(france, "selftest_local") as tested:
            local = france._local_base([{"order": "ta", "number": "2301234"}],
                                       keys, logs.append)
        self.assertIsNone(local)
        tested.assert_not_called()
        self.assertIn("https", " ".join(logs))


class ControlCharacters(unittest.TestCase):
    """Audit of 30/09/2026, hardening 8: a label from a database cannot add a line to the
    report, drive a terminal, or reverse a number on screen."""

    def test_a_label_cannot_forge_a_line_or_drive_a_terminal(self):
        forged = "civ. 2\n  Cass. 99-99.999 : CONFIRMÉE\x1b[2K\x1b]0;titre\x07\u202e"
        cit = {"kind": "decision", "order": "judicial", "court": "Cass", "number": "17-28268",
               "cited_date": None, "verdict": "CONFIRMED", "explanation": forged,
               "actual_date": None}
        r = report.build("doc.pdf", "france", [cit], [])
        text = report.to_text(r)
        self.assertNotIn("\x1b", text)
        self.assertNotIn("\u202e", text)
        self.assertFalse(any(line.lstrip().startswith("Cass. 99-99.999")
                             for line in text.splitlines()))
        self.assertIn("99-99.999", report.to_json(r))       # kept, on the same line


class Links(unittest.TestCase):
    """Each result carries the link of what was found, built on a fixed pattern from an
    identifier the base sent back, and only from one of the expected form."""

    def test_only_well_formed_identifiers_give_a_link(self):
        from citecheck.countries.france import links
        self.assertEqual(links.code_article("LEGIARTI000032041571"),
                         "https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000032041571")
        self.assertEqual(links.judilibre("5fca7e0a7ec5c2c5b5a6d2a3"),
                         "https://www.courdecassation.fr/decision/5fca7e0a7ec5c2c5b5a6d2a3")
        self.assertEqual(links.legifrance_decision("CONSTEXT000022393072"),
                         "https://www.legifrance.gouv.fr/cons/id/CONSTEXT000022393072")
        for bad in (None, "", "LEGIARTI0000320415711", "LEGIARTI00003204157/../x",
                    "javascript:alert(1)", "LEGIARTI000032041571\n"):
            with self.subTest(bad=bad):
                self.assertIsNone(links.code_article(bad))
                self.assertIsNone(links.judilibre(bad))
                self.assertIsNone(links.legifrance_decision(bad))
        self.assertIsNone(links.legifrance_decision("EVILTEXT000022393072"))
        self.assertIsNone(links.arianeweb("298348 ", "2009-10-30"))
        self.assertIsNone(links.eur_lex("62019CJ0561&x=1"))

    def test_dates_found_stay_a_list_and_carry_their_links(self):
        from citecheck.countries.france import links
        found = links.Found({"2021-10-06": "https://a", "2019-01-02": None, None: "x"})
        self.assertEqual(found, ["2019-01-02", "2021-10-06"])
        self.assertEqual(links.link_for(found, "2021-10-06"), "https://a")
        self.assertEqual(links.link_for(found, "2000-01-01"), "https://a")    # the one found
        self.assertIsNone(links.link_for(["2021-10-06"], "2021-10-06"))       # a plain list
        self.assertEqual(links.Found(), [])

    def test_the_verdict_carries_the_link(self):
        from citecheck.countries.france import links, verdict_dates
        ident = "5fca7e0a7ec5c2c5b5a6d2a3"
        record = {"decision_date": "2019-04-10", "chamber": "Chambre sociale", "id": ident}
        self.assertEqual(verdict_judicial(record, "2019-03-21")[3], links.judilibre(ident))
        days = links.Found({"2009-10-30": links.arianeweb("298348", "2009-10-30")})
        self.assertEqual(verdict_admin(5, days, "2009-10-30")[3],
                         "https://www.conseil-etat.fr/fr/arianeweb/CE/decision/2009-10-30/298348")
        self.assertEqual(len(verdict_dates([], "2010-05-12", "L")), 3)     # nothing found

    def test_every_result_has_a_link_key(self):
        from citecheck.countries.france import check
        results = check([{"kind": "decision", "order": "other", "court": "CEDH",
                          "number": "13134/87", "cited_date": None},
                         {"kind": "decision", "order": "judicial", "court": "Cass",
                          "number": "17-28268\n", "cited_date": None}], {})
        self.assertTrue(results[0]["link"].startswith("https://hudoc.echr.coe.int/"))
        self.assertIsNone(results[1]["link"])


class KeyShape(unittest.TestCase):
    def test_a_sentence_is_not_a_key(self):
        from citecheck.keys import looks_like_key
        self.assertTrue(looks_like_key("d1c0d8d0-1234-4abc-9def-0123456789ab"))
        for bad in ("J'ai collé une phrase ici.", "abc", "clé-avec-accent-é", "a" * 300,
                    "0123456789\nabcdef"):
            with self.subTest(bad=bad):
                self.assertFalse(looks_like_key(bad))

    def test_a_malformed_key_counts_as_missing_wherever_it_comes_from(self):
        from unittest import mock
        from citecheck import keys
        crlf = chr(13) + chr(10)
        for value in ("une clé avec des espaces", "0123456789" + crlf + "X-Autre: 1"):
            with mock.patch.dict("os.environ", {"PISTE_API_KEY": value}):
                self.assertIsNone(keys.get("PISTE_API_KEY"))
        with mock.patch.dict("os.environ", {"PISTE_API_KEY": "d1c0d8d0-1234-4abc"}):
            self.assertEqual(keys.get("PISTE_API_KEY"), "d1c0d8d0-1234-4abc")
        with mock.patch.dict("os.environ", {"PISTE_API_KEY": ""}), \
                mock.patch.object(keys, "keyring") as ring:
            ring.get_password.return_value = "J'ai collé une phrase ici."
            self.assertIsNone(keys.get("PISTE_API_KEY"))
            self.assertFalse(keys.save("PISTE_API_KEY", "J'ai collé une phrase ici."))
            ring.set_password.assert_not_called()


class TableReport(unittest.TestCase):
    def report(self):
        cit = {"kind": "decision", "order": "judicial", "court": "Cass", "number": "17-28268",
               "cited_date": "2019-03-21", "verdict": "WRONG_DATE",
               "explanation": "le numéro existe, mais Judilibre date l'arrêt du 2019-04-10 " * 3,
               "actual_date": "2019-04-10",
               "link": "https://www.courdecassation.fr/decision/5fca7e0a7ec5c2c5b5a6d2a3",
               "location": {"page": 2, "page_exact": True, "in_notes": False,
                            "excerpt": "Cass. 2e civ., 21 mars 2019, n° 17-28268",
                            "text": "17-28268", "nth": 0,
                            "repeats": [{"page": 3, "text": "17-28268", "nth": 0}]}}
        return report.build("Dupont c. Martin.pdf", "france", [cit], [])

    def test_a_table_then_the_details(self):
        text = report.to_text(self.report())
        self.assertIn("| N°  | Page    | Citation", text)
        self.assertIn("| 1   | 2       | Cass n° 17-28268, cité au 2019-03-21", text)
        self.assertTrue(text.isascii() or all(ord(ch) < 0x2500 or ord(ch) > 0x257F
                                               for ch in text))    # no box drawing
        self.assertIn("lien : https://www.courdecassation.fr/decision/5fca7e0a7ec5c2c5b5a6d2a3",
                      text)
        for line in text.splitlines():
            if "lien : " not in line:
                with self.subTest(line=line):
                    self.assertLessEqual(len(line), report.WIDTH + 2)

    def test_without_excerpts_nothing_from_the_document_is_left(self):
        r = report.without_excerpts(self.report())
        self.assertEqual(r["citations"][0]["location"],
                         {"page": 2, "page_exact": True, "in_notes": False})
        self.assertNotIn("Dupont", report.to_json(r))
        self.assertIn("courdecassation", report.to_json(r))          # the link stays

    def test_lights(self):
        self.assertEqual(report.light("CONFIRMED"), report.CONFIRMED)
        self.assertEqual(report.light("NOT_PUBLISHED"), report.INVENTED)
        self.assertEqual(report.light("NOT_TESTED"), report.UNCHECKED)
        # Nothing doubtful is ever shown as confirmed.
        for v in ("WRONG_DATE", "WRONG_CHAMBER", "DOUBTFUL", "EXISTS_DATE_UNCHECKED",
                  "ARTICLE_OTHER_VERSION", "QUOTE_NOT_FOUND", "ARTICLE_NOT_IN_FORCE",
                  "DATE_BEFORE_NUMBER"):
            self.assertEqual(report.light(v), report.CHECK, v)


class Repeats(unittest.TestCase):
    def test_a_citation_repeated_is_checked_once_and_placed_twice(self):
        text = ("Voir Cass. soc., 21 mars 2019, n° 17-28268. Et l'article 1240 du Code civil. "
                "Plus loin, déjà cité (Cass. soc., 21 mars 2019, n° 17-28268), et encore "
                "l'article 1240 du Code civil.")
        citations, _ = extract(text)
        self.assertEqual([c["number"] for c in citations], ["17-28268", "1240"])
        for c in citations:
            self.assertEqual(len(c["repeats"]), 1)
            start, end = c["repeats"][0]
            self.assertGreater(start, c["span"][1])
            self.assertEqual(text[start:end], text[slice(*c["span"])])


class AnnotatedPdf(unittest.TestCase):
    """The annotated PDF, on a real PDF written here: a line of Helvetica at a known place."""

    LINE = "Voir Cass. soc., n\xb0 17-28.268, et l'article 1240 du Code civil."
    LINK = "https://www.courdecassation.fr/decision/5fca7e0a7ec5c2c5b5a6d2a3"

    def pdf(self, path, rotate=0):
        from pypdf import PdfWriter
        from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject
        w = PdfWriter()
        page = w.add_blank_page(595, 842)
        font = DictionaryObject({NameObject("/Type"): NameObject("/Font"),
                                 NameObject("/Subtype"): NameObject("/Type1"),
                                 NameObject("/BaseFont"): NameObject("/Helvetica"),
                                 NameObject("/Encoding"): NameObject("/WinAnsiEncoding")})
        page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject(
            {NameObject("/F1"): w._add_object(font)})})
        body = DecodedStreamObject()
        body.set_data(b"BT /F1 12 Tf 72 700 Td (" + self.LINE.encode("cp1252") + b") Tj ET")
        page[NameObject("/Contents")] = w._add_object(body)
        if rotate:
            page.rotate(rotate)
        with open(path, "wb") as f:
            w.write(f)

    def report(self, path, verdict="CONFIRMED", link=LINK):
        from citecheck import annotate, reader
        doc = reader.read(path)
        start = doc.text.index("17-28.268")
        cit = {"kind": "decision", "order": "judicial", "court": "Cass", "number": "17-28268",
               "cited_date": None, "verdict": verdict, "explanation": "x",
               "actual_date": None, "link": link,
               "location": {"page": 1, "page_exact": True, "in_notes": False,
                            "excerpt": "", **annotate.anchor(doc.text, start, start + 9)}}
        lost = {**cit, "location": {**cit["location"], "text": "99-99.999"}}
        return report.build(path.name, "france", [cit, lost], [])

    def annots(self, path):
        """The annotations of the document's page: page 1 is now the notice."""
        from pypdf import PdfReader
        return [a.get_object() for a in PdfReader(path).pages[1].get("/Annots", [])]

    def test_highlighted_linked_and_the_original_untouched(self):
        import tempfile
        from pathlib import Path
        from citecheck import annotate
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "conclusions.pdf"
            self.pdf(src)
            before = src.read_bytes()
            target = annotate.output_name(src)
            self.assertEqual(target.name, "conclusions-citations-verifiees.pdf")
            self.assertEqual(annotate.annotate(src, target, self.report(src)), (1, 1))
            self.assertEqual(src.read_bytes(), before)
            annots = self.annots(target)
            from pypdf import PdfReader
            pages = PdfReader(target).pages
            self.assertEqual(len(pages), 2)                     # the notice, then the page
            notice = pages[0].extract_text()
            self.assertIn("Comment lire ce document", notice)
            self.assertIn("Cmd + clic", notice)
            self.assertIn("compétence pour se prononcer", notice)
        kinds = [a["/Subtype"] for a in annots]
        self.assertEqual(kinds, ["/Highlight", "/Link"])
        highlight, link = annots
        self.assertEqual(link["/A"]["/URI"], self.LINK)
        x0, y0, x1, y1 = [float(v) for v in highlight["/Rect"]]
        # « Voir Cass. soc., n° » is about 105 points of Helvetica 12: the number comes after.
        self.assertTrue(150 < x0 < 200 and 690 < y0 < 702 and x1 - x0 < 70, (x0, y0, x1))
        self.assertEqual([float(v) for v in highlight["/C"]],
                         list(annotate.COLORS[report.CONFIRMED]))
        # One palette: the highlight is the colour shown in the legend and in the report.
        self.assertEqual([round(v * 255) for v in annotate.COLORS[report.CONFIRMED]],
                         list(report.COLORS[report.CONFIRMED]))
        self.assertIn("/AP", highlight)

    def test_a_turned_page_is_marked_at_the_same_place(self):
        import tempfile
        from pathlib import Path
        from citecheck import annotate
        rects = []
        with tempfile.TemporaryDirectory() as tmp:
            for rotate in (0, 90):
                src = Path(tmp) / f"p{rotate}.pdf"
                self.pdf(src, rotate)
                annotate.annotate(src, Path(tmp) / f"out{rotate}.pdf", self.report(src))
                rects.append([round(float(v)) for v in
                              self.annots(Path(tmp) / f"out{rotate}.pdf")[0]["/Rect"]])
        self.assertEqual(rects[0], rects[1])

    def test_unchecked_gets_a_question_mark_and_no_link(self):
        import tempfile
        from pathlib import Path
        from citecheck import annotate
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "c.pdf"
            self.pdf(src)
            annotate.annotate(src, Path(tmp) / "out.pdf",
                              self.report(src, "NOT_TESTED", link=None))
            annots = self.annots(Path(tmp) / "out.pdf")
            self.assertEqual([a["/Subtype"] for a in annots], ["/Highlight"])
            self.assertIn(b"(?) Tj", annots[0]["/AP"]["/N"].get_object().get_data())


    def test_the_copy_leaves_behind_what_acts_or_names(self):
        import tempfile
        from pathlib import Path
        from pypdf import PdfReader, PdfWriter
        from pypdf.generic import (ArrayObject, DictionaryObject, NameObject, NumberObject,
                                   TextStringObject)
        from citecheck import annotate

        def annot(subtype, action):
            return DictionaryObject({
                NameObject("/Type"): NameObject("/Annot"), NameObject("/Subtype"):
                NameObject(subtype), NameObject("/Rect"): ArrayObject([NumberObject(0)] * 4),
                NameObject("/A"): DictionaryObject(action)})
        with tempfile.TemporaryDirectory() as tmp:
            plain, src = Path(tmp) / "plain.pdf", Path(tmp) / "Dupont c. Martin.pdf"
            self.pdf(plain)
            w = PdfWriter(clone_from=str(plain))
            with warnings.catch_warnings():         # add_js : déprécié, mais c'est le but
                warnings.simplefilter("ignore", DeprecationWarning)
                w.add_js("app.alert('ouvert');")
            w.add_attachment("piece-cachee.txt", b"nom-du-client-MARTIN-secret")
            w.add_metadata({"/Author": "Maitre Jean Dupont", "/Title": "Dupont c. Martin"})
            w._root_object[NameObject("/OpenAction")] = DictionaryObject({
                NameObject("/S"): NameObject("/JavaScript"),
                NameObject("/JS"): TextStringObject("app.alert(2)")})
            launch = annot("/Link", {NameObject("/S"): NameObject("/Launch"),
                                     NameObject("/F"): TextStringObject("C:/Windows/notepad.exe")})
            script = annot("/Link", {NameObject("/S"): NameObject("/URI"),
                                     NameObject("/URI"): TextStringObject("javascript:alert(1)")})
            web = annot("/Link", {NameObject("/S"): NameObject("/URI"),
                                  NameObject("/URI"): TextStringObject("https://exemple.fr/")})
            disguised = annot("/Link", {NameObject("/S"): NameObject("/URI"), NameObject(
                "/URI"): TextStringObject("https://www.legifrance.gouv.fr@evil.example/")})
            fake = DictionaryObject({
                NameObject("/Type"): NameObject("/Annot"), NameObject("/Subtype"):
                NameObject("/FreeText"), NameObject("/Rect"): ArrayObject([NumberObject(0)] * 4),
                NameObject("/Contents"): TextStringObject("Verdict-FAUX : confirme")})
            for a in (launch, script, web, disguised, fake):
                w.add_annotation(0, a)
            w.pages[0][NameObject("/AF")] = ArrayObject([TextStringObject("joint-de-page")])
            w.pages[0][NameObject("/PieceInfo")] = DictionaryObject({
                NameObject("/App"): TextStringObject("prive-du-cabinet")})
            with open(src, "wb") as f:
                w.write(f)
            out = Path(tmp) / "out.pdf"
            hostile = self.report(src, link="javascript:alert(3)")
            self.assertEqual(annotate.annotate(src, out, hostile), (1, 1))
            data = out.read_bytes()
            for marker in (b"/JavaScript", b"/Launch", b"/OpenAction", b"/EmbeddedFile",
                           b"alert", b"MARTIN-secret", b"Maitre Jean", b"evil.example",
                           b"exemple.fr", b"Verdict-FAUX", b"joint-de-page",
                           b"prive-du-cabinet"):
                self.assertNotIn(marker, data)
            copy = PdfReader(out)
            self.assertEqual(copy.attachments, {})
            self.assertIsNone(copy.metadata.get("/Author"))
            uris = [a.get_object()["/A"]["/URI"] for a in copy.pages[1]["/Annots"]
                    if "/A" in a.get_object()]
            self.assertEqual(uris, [])      # none of the piece's links, even ordinary ones
            self.assertEqual([a.get_object()["/Subtype"] for a in copy.pages[1]["/Annots"]],
                             ["/Highlight"])                   # only the program's own

    def test_a_pdf_too_heavy_to_reread_writes_nothing(self):
        import tempfile
        from pathlib import Path
        from unittest import mock
        from citecheck import annotate
        with tempfile.TemporaryDirectory() as tmp:
            src, out = Path(tmp) / "c.pdf", Path(tmp) / "out.pdf"
            self.pdf(src)
            for ceiling in ({"MAX_SECONDS": -1}, {"MAX_LETTERS": 5}):
                with mock.patch.multiple(annotate, **ceiling):
                    with self.assertRaises(annotate.TooHeavy):
                        annotate.annotate(src, out, self.report(src))
            self.assertEqual(sorted(p.name for p in Path(tmp).iterdir()), ["c.pdf"])

    def test_only_official_https_links_survive(self):
        for url in ("https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000032041571",
                    "https://www.courdecassation.fr/decision/5fca7e0a7ec5c2c5b5a6d2a3"):
            self.assertTrue(report.safe_link(url))
        for url in ("javascript:alert(1)", "http://www.legifrance.gouv.fr/x",
                    "https://www.legifrance.gouv.fr.exemple.fr/", "https://a@eur-lex.europa.eu/",
                    "https://eur-lex.europa.eu:8443/", "file:///C:/x.pdf", None, 3):
            self.assertFalse(report.safe_link(url), url)


class PdfReport(unittest.TestCase):
    def test_the_pdf_report_says_the_same_with_working_links(self):
        import tempfile
        from pypdf import PdfReader
        from citecheck import report_pdf
        r = TableReport().report()
        with tempfile.TemporaryDirectory() as tmp:
            full, bare = Path(tmp) / "full.pdf", Path(tmp) / "bare.pdf"
            report_pdf.write(r, full)
            report_pdf.write(report.without_excerpts(r), bare)
            texts = {}
            for name in (full, bare):
                pdf = PdfReader(name)
                texts[name] = " ".join(pg.extract_text() for pg in pdf.pages)
                uris = {a.get_object()["/A"]["/URI"] for pg in pdf.pages
                        for a in pg.get("/Annots", []) if "/A" in a.get_object()}
                self.assertEqual(uris, {r["citations"][0]["link"]})
        self.assertIn("EXISTE, MAIS À UNE AUTRE DATE", texts[full])
        self.assertIn("Dupont", texts[full])
        self.assertNotIn("Dupont", texts[bare])
        self.assertNotIn("21 mars 2019", texts[bare])            # the excerpt is gone

    def test_its_name_never_carries_the_document_without_excerpts(self):
        from citecheck import report_pdf
        self.assertEqual(report_pdf.output_name("C:/x/Dupont c. Martin.pdf", False),
                         "Dupont c. Martin-rapport-citations.pdf")
        self.assertEqual(report_pdf.output_name("C:/x/Dupont c. Martin.pdf", True),
                         "rapport-citations.pdf")


class DecisionQuotes(unittest.TestCase):
    """A real number at the right date, with a passage it may not contain: the passage is
    looked for in the decision's full text."""

    TEXT = ("9. Par ailleurs, l'huissier de justice, qui a déposé une copie de l'acte à son "
            "étude, n'a pas laissé sur les lieux de la signification, l'avis de passage prévu "
            "par les articles 655 et 656 du code de procédure civile. "
            # Le reste d'un arrêt : un texte de décision fait plus de MIN_TEXT caractères.
            + "10. Il en résulte que la signification n'a pas été faite régulièrement. " * 8)
    LINK ="https://www.courdecassation.fr/decision/658401878704660008a2970f"

    def check(self, quote, verdict="CONFIRMED", text=None):
        from unittest import mock
        from citecheck.countries.france import decision_quotes
        with mock.patch.object(decision_quotes, "judilibre_text",
                               return_value=self.TEXT if text is None else text) as t:
            out = decision_quotes.check({"quote": quote}, (verdict, "Judilibre date bien "
                                        "l'arrêt", "2023-12-21", self.LINK),
                                        {"PISTE_API_KEY": "k"})
        return out, t

    def test_a_passage_in_the_decision_keeps_it_blue(self):
        (v, why, _, link), _ = self.check("L'huissier de justice, qui a déposé une copie de "
                                          "l'acte à son étude, n'a pas laissé (…) l'avis de "
                                          "passage prévu par les articles 655 et 656")
        self.assertEqual(v, "CONFIRMED")
        self.assertIn("passage cité retrouvé", why)
        self.assertEqual(link, self.LINK)

    def test_a_passage_lent_to_a_real_decision_turns_orange(self):
        (v, why, _, _), _ = self.check("la signification à domicile est nulle de plein droit "
                                       "sans qu'il soit besoin de prouver un grief")
        self.assertEqual(v, "DECISION_QUOTE_NOT_FOUND")
        self.assertEqual(report.light(v), report.CHECK)
        (v, why, _, _), _ = self.check("la signification à domicile est nulle de plein droit "
                                       "sans grief", "WRONG_DATE")
        self.assertEqual(v, "WRONG_DATE")
        self.assertIn("ne se retrouve pas", why)

    def test_nothing_is_fetched_without_a_passage_or_a_decision(self):
        for quote, verdict in (("", "CONFIRMED"), ("trop court", "CONFIRMED"),
                               ("un passage assez long pour compter", "NOT_PUBLISHED")):
            out, fetched = self.check(quote, verdict)
            self.assertEqual(out[0], verdict)
            fetched.assert_not_called()

    def test_a_decision_sent_without_its_text_proves_nothing(self):
        for empty in ("", "   ", " <p></p> "):
            (v, why, _, _), _ = self.check("la signification à domicile est nulle de plein "
                                           "droit sans grief", text=empty)
            self.assertEqual(v, "CONFIRMED")
            self.assertIn("non contrôlé", why)
            self.assertNotIn("paraphrase", why)

    def test_the_passage_after_a_decision_is_attached_to_it(self):
        cits, _ = extract("Cass. 2e civ., 21 décembre 2023, n° 22-18.480 : « L'huissier de "
                          "justice n'a pas laissé l'avis de passage prévu par la loi ».")
        self.assertEqual(cits[0]["quote"], "L'huissier de justice n'a pas laissé l'avis de "
                                           "passage prévu par la loi")


class HostileSizes(unittest.TestCase):
    """A document or a response built to occupy the computer: the time must grow with the
    size, not with its square."""

    def test_a_thousand_times_the_same_citation_is_read_at_once(self):
        import time
        text = "Cass. soc., 21 mars 2019, n° 17-28.268. " * 8000
        began = time.monotonic()
        cits, _ = extract(text)
        self.assertLess(time.monotonic() - began, 5)        # 13 s before, under 1 s now
        self.assertEqual(len(cits), 1)

    def test_tags_are_stripped_in_one_pass(self):
        import time
        from citecheck.countries.france.decision_quotes import _strip
        from citecheck.countries.france.legifrance import _strip_html
        began = time.monotonic()
        _strip("<" * 1_000_000)
        _strip_html("<" * 1_000_000)
        self.assertLess(time.monotonic() - began, 2)        # minutes before
        self.assertEqual(_strip_html("<p>Art. <b>1240</b></p>").split(), ["Art.", "1240"])


class NeverOverTheDocument(unittest.TestCase):
    """The document is a court filing: no report, no annotated copy is ever written over it."""

    def test_reports_refuse_the_document_and_its_other_names(self):
        import os
        import tempfile
        from citecheck import annotate, output, report_pdf
        with tempfile.TemporaryDirectory() as tmp:
            doc = Path(tmp) / "Conclusions.pdf"
            doc.write_bytes(b"%PDF-1.4 la piece")
            other = Path(tmp) / "lien.pdf"
            os.link(doc, other)                                 # a hard link: the same file
            r = report.build(doc.name, "france", [], [])
            for target in (doc, Path(tmp) / "conclusions.PDF", other):
                with self.assertRaises(output.OverDocument):
                    output.write(target, "rapport", document=doc)
                with self.assertRaises(output.OverDocument):
                    report_pdf.write(r, target, document=doc)
                with self.assertRaises(output.OverDocument):
                    annotate.annotate(doc, target, r)
            self.assertEqual(doc.read_bytes(), b"%PDF-1.4 la piece")
            output.write(Path(tmp) / "rapport.txt", "un deux", document=doc)
            self.assertEqual(sorted(p.name for p in Path(tmp).iterdir()),
                             ["Conclusions.pdf", "lien.pdf", "rapport.txt"])  # no .partiel

    def test_the_command_line_stops_before_checking(self):
        import contextlib
        import io
        import tempfile
        from citecheck.__main__ import main
        with tempfile.TemporaryDirectory() as tmp:
            doc = Path(tmp) / "c.txt"
            doc.write_text("Cass. soc., 21 mars 2019, n° 17-28.268.", encoding="utf-8")
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                self.assertEqual(main([str(doc), "-o", str(doc)]), 2)
            self.assertIn("jamais remplacé", err.getvalue())
            self.assertEqual(doc.read_text(encoding="utf-8"),
                             "Cass. soc., 21 mars 2019, n° 17-28.268.")


class PisteCeiling(unittest.TestCase):
    """PISTE gives the keys of Légifrance and Judilibre: a ceiling on the pace, and a full stop
    at its first « too many requests »."""

    def setUp(self):
        from citecheck.countries.france import piste
        piste.reset()
        self.addCleanup(piste.reset)

    def test_requests_are_spaced_by_the_ceiling(self):
        from unittest import mock
        from citecheck.countries.france import piste
        naps = []
        with mock.patch.object(piste, "PER_MINUTE", 30), \
                mock.patch.object(piste.time, "sleep", naps.append), \
                mock.patch.object(piste.time, "monotonic", return_value=1000.0), \
                mock.patch.object(piste, "_next", 0.0):
            piste.wait()
            piste.wait()
            piste.wait()
        self.assertEqual(naps, [2.0, 4.0])      # 30 per minute: one every 2 seconds

    def test_a_refusal_while_waiting_stops_the_request_that_waited(self):
        import threading
        from unittest import mock
        from citecheck.countries.france import piste
        with mock.patch.object(piste, "PER_MINUTE", 600):   # 0,1 s between two requests
            piste.wait()                                    # the next one has to wait
            outcome = []

            def second():
                try:
                    piste.wait()
                    outcome.append("sent")
                except piste.Limited:
                    outcome.append("stopped")
            t = threading.Thread(target=second)
            t.start()
            piste.refused(429)                              # PISTE refuses meanwhile
            t.join(5)
        self.assertEqual(outcome, ["stopped"])

    def test_the_first_429_stops_every_piste_request(self):
        import io, urllib.error
        from unittest import mock
        from citecheck.countries.france import legifrance, piste, sources
        from citecheck.countries.france.legifrance import Client, Unavailable
        refusal = urllib.error.HTTPError("https://api.piste.gouv.fr", 429, "Too Many", {},
                                         io.BytesIO(b""))
        with mock.patch.object(piste, "PER_MINUTE", 60000), \
                mock.patch.object(sources, "urlopen", side_effect=refusal) as judilibre, \
                mock.patch.object(legifrance, "urlopen", side_effect=refusal) as lf:
            self.assertEqual(sources.judilibre("17-28268", "k"), {"_err": piste.LIMITED})
            self.assertTrue(piste.limited())
            with self.assertRaises(Unavailable) as said:
                Client("id", "secret").codes()
            self.assertIn("PISTE a limité", str(said.exception))
            self.assertEqual(judilibre.call_count, 1)
            self.assertEqual(lf.call_count, 0)              # nothing more was sent
        piste.reset()
        self.assertFalse(piste.limited())                    # the next check tries again


class AuditPass3BadAnswers(unittest.TestCase):
    """Audit du 01/10/2026, lot A : une réponse incomplète ou incohérente de la base ne fait
    jamais un feu vert ni un feu rouge, seulement une erreur (gris)."""

    def _client(self, answer):
        from citecheck.countries.france.legifrance import Client

        class Fake(Client):
            def _post(self, route, body):
                return answer(route, body)
        return Fake("id", "secret")

    def test_a_version_without_a_start_date_is_not_in_force(self):
        from citecheck.countries.france.legifrance import Unavailable

        def answer(route, body):
            if route == "/search":
                return {"totalResultNumber": 1, "results": [{
                    "titles": [{"cid": "LEGITEXT1"}], "sections": [{"extracts": [
                        {"num": "1240", "id": "LEGIARTI1", "dateDebut": None}]}]}]}
            return {"article": {"articleVersions": [{"id": "LEGIARTI1", "dateDebut": None,
                                                      "dateFin": None}]}}
        with self.assertRaises(Unavailable):
            self._client(answer).versions("Code civil", "LEGITEXT1", "1240")

    def test_an_absurd_date_is_refused_not_crashed(self):
        from citecheck.countries.france.legifrance import Unavailable, _day, dated
        self.assertEqual(_day(-10 ** 20), "?")
        self.assertEqual(_day(0), "1970-01-01")
        with self.assertRaises(Unavailable):
            dated([{"debut": _day(-10 ** 20), "fin": ""}], "1")
        with self.assertRaises(Unavailable):
            dated([{"debut": "0001-01-01", "fin": ""}], "1")
        ok = [{"debut": "1804-03-21", "fin": "2999-01-01"}, {"debut": "2016-10-01", "fin": ""}]
        self.assertEqual(dated(ok, "1"), ok)

    def test_a_search_without_a_sound_total_concludes_nothing(self):
        from citecheck.countries.france.legifrance import Unavailable
        other = [{"titles": [{"cid": "LEGITEXT1"}], "sections": [{"extracts": [
            {"num": "9999", "id": "LEGIARTI9"}]}]}]
        for total in (0, None, "0", -1):
            with self.subTest(total=total), self.assertRaises(Unavailable):
                self._client(lambda r, b: {"totalResultNumber": total, "results": other}
                             )._search_versions("Code civil", "LEGITEXT1", "1240")
        # Le cas sain : rien sous ce numéro, et la base le dit.
        self.assertEqual(self._client(lambda r, b: {"totalResultNumber": 0, "results": []}
                                      )._search_versions("Code civil", "LEGITEXT1", "1240"), [])

    def test_an_idcc_in_error_is_not_remembered_as_unknown(self):
        from citecheck.countries.france.legifrance import Unavailable
        asked = []

        def answer(route, body):
            asked.append(body["id"])
            if body["id"] == "1979":
                return {"titre": "HCR", "texteBaseId": ["KALITEXT1"]}
            raise Unavailable("HTTP 500", 500)
        client = self._client(answer)
        self.assertIsNone(client.convention("3043"))
        self.assertIsNone(client.convention("3043"))
        self.assertEqual(asked.count("3043"), 4)             # asked again, not remembered

    def test_a_cellar_record_without_a_date_is_not_unpublished(self):
        import io, urllib.error
        from unittest import mock
        from citecheck.countries.france import other_courts
        from citecheck.countries.france.legifrance import Unavailable
        redirect = urllib.error.HTTPError(
            "https://publications.europa.eu", 303, "See Other",
            {"Location": "https://publications.europa.eu/resource/cellar/abc"}, io.BytesIO(b""))
        record = (b"<NOTICE><WORK><RESOURCE_LEGAL_ID_CELEX><VALUE>62019CJ0561</VALUE>"
                  b"</RESOURCE_LEGAL_ID_CELEX></WORK></NOTICE>")
        with mock.patch.object(other_courts, "_get", side_effect=[redirect, record]):
            with self.assertRaises(Unavailable):
                other_courts._celex_dates("62019CJ0561")


class AuditPass3Reading(unittest.TestCase):
    """Audit du 01/10/2026, lot B : une phrase mal lue ne doit pas faire vérifier un autre
    article, une autre date, ni une « décision » que le texte ne cite pas."""

    def _seen(self, text):
        citations, remarks = extract(text)
        return [(c["court"], c["number"], c.get("cited_date"), c.get("idcc"))
                for c in citations], remarks

    def test_a_suffix_followed_by_a_dot_is_kept(self):
        for text, number in [("article 199 undecies B. du code général des impôts", "199 undecies B"),
                             ("article 238 bis-0 I. du code général des impôts", "238 bis-0 I"),
                             ("article 46 quater-0 ZZ. du CGI", "46 quater-0 ZZ"),
                             ("art. 199 undecies B. du CGI", "199 undecies B")]:
            with self.subTest(text=text):
                self.assertEqual(self._seen(text)[0][0][1], number)
        # « C. civ. » reste un nom de code, pas un suffixe.
        self.assertEqual(self._seen("art. 1240 C. civ.")[0],
                         [("Code civil", "1240", None, None)])

    def test_the_code_is_not_taken_from_the_next_sentence(self):
        seen, remarks = self._seen("L'article 1240. Cette solution ne figure pas au code de "
                                   "commerce, article L. 110-1 du code de commerce.")
        self.assertEqual(seen, [("Code de commerce", "L110-1", None, None)])
        self.assertTrue(any("1240" in r for r in remarks))
        seen, _ = self._seen("article L. 111-1. Le code de la consommation rappelle la règle.")
        self.assertEqual(seen, [])
        seen, _ = self._seen("article L. 110-1 du code de commerce. L'article 1240 du même code.")
        self.assertEqual([n for _, n, _, _ in seen], ["L110-1", "1240"])

    def test_a_number_without_a_court_is_not_a_decision(self):
        for text in ("La pièce n° 308850 a été signée le 5 juin 2009 par le client Dupont.",
                     "Référence 17-28.268 communiquée le 21 mars 2019 au client."):
            with self.subTest(text=text):
                seen, remarks = self._seen(text)
                self.assertEqual(seen, [])
                self.assertTrue(any("sans juridiction nommée" in r for r in remarks))
        # Une juridiction, une chambre, « pourvoi » ou « arrêt » suffisent.
        for text in ("CE, 5 juin 2009, n° 308850.", "Soc. 21 mars 2019, n° 17-28.268.",
                     "pourvoi n° 17-28.268 rejeté le 21 mars 2019.",
                     "arrêt du 7 juillet 2022, n° 21-11.484, la deuxième chambre civile a jugé."):
            with self.subTest(text=text):
                self.assertEqual(len(self._seen(text)[0]), 1)

    def test_two_dates_for_one_number_check_neither(self):
        seen, _ = self._seen("Cass. soc., arrêt du 1er janvier 1900 (et non du 21 mars 2019), "
                             "n° 17-28.268.")
        self.assertEqual(seen, [("Cass", "17-28.268", None, None)])
        # La date d'une loi n'est pas en concurrence avec celle de l'arrêt.
        seen, _ = self._seen("Cass. soc., 21 mars 2019, n° 17-28.268, appliquant la loi du "
                             "8 août 2016.")
        self.assertEqual(seen, [("Cass", "17-28.268", "2019-03-21", None)])

    def test_an_idcc_is_not_lent_to_the_next_convention(self):
        seen, _ = self._seen("article 5 de la convention collective (IDCC 1979) et article 99 "
                             "de la convention collective nationale.")
        self.assertEqual([i for *_, i in seen], ["1979", None])
        seen, _ = self._seen("article 5 de la convention collective (IDCC 1979) et article 99 "
                             "de la même convention.")
        self.assertEqual([i for *_, i in seen], ["1979", "1979"])


class AuditPass3Writing(unittest.TestCase):
    """Audit du 01/10/2026, lot C : le fichier écrit d'abord à côté a un nom imprévisible,
    et ne réutilise jamais un fichier déjà là."""

    def test_a_hard_link_waiting_under_the_old_name_is_untouched(self):
        import os
        import tempfile
        from pathlib import Path
        from citecheck import output
        with tempfile.TemporaryDirectory() as tmp:
            piece = Path(tmp) / "conclusions.pdf"
            piece.write_bytes(b"la piece")
            os.link(piece, Path(tmp) / "rapport.txt.partiel")    # l'ancien nom prévisible
            output.write(Path(tmp) / "rapport.txt", "le rapport", document=piece)
            self.assertEqual(piece.read_bytes(), b"la piece")
            self.assertEqual((Path(tmp) / "rapport.txt").read_text("utf-8"), "le rapport")

    def test_a_piece_named_like_the_old_temporary_is_untouched(self):
        import tempfile
        from pathlib import Path
        from citecheck import output
        with tempfile.TemporaryDirectory() as tmp:
            piece = Path(tmp) / "conclusions.pdf.partiel"
            piece.write_bytes(b"la piece")
            output.write(Path(tmp) / "conclusions.pdf", b"le rapport",
                         document=Path(tmp) / "autre.pdf")
            self.assertEqual(piece.read_bytes(), b"la piece")

    def test_nothing_is_left_beside_after_a_failure(self):
        import tempfile
        from pathlib import Path
        from citecheck import output
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "dossier").mkdir()
            with self.assertRaises(OSError):
                output.write(Path(tmp) / "dossier", b"x")          # la cible est un dossier
            self.assertEqual([p.name for p in Path(tmp).iterdir()], ["dossier"])


class AuditPass3Small(unittest.TestCase):
    """Audit du 01/10/2026, lot D : petits durcissements."""

    def test_a_base_label_stays_on_one_short_line(self):
        record = {"decision_date": "2019-03-21", "chamber": "soc\nCitation exacte.",
                  "solution": "x" * 500, "id": "0" * 24}
        v, why, *_ = verdict_judicial(record, "2019-03-21")
        self.assertNotIn("\n", why)
        self.assertLess(len(why), 250)

    def test_line_separators_are_cleaned_everywhere(self):
        sep = chr(0x2028)
        cit = {"kind": "article", "code": "Code civil", "number": "1240", "court": "Code civil",
               "verdict": "ARTICLE_IN_FORCE", "explanation": "ok" + sep + "FAUX confirme",
               "link": "https://www.legifrance.gouv.fr/a" + sep + "/x"}
        r = report.build("doc.pdf", "france", [cit], ["remarque" + chr(0x2029) + "FAUX"])
        text = report.to_text(r)
        self.assertNotIn(sep, text)
        self.assertNotIn(chr(0x2029), text)
        self.assertIsNone(r["citations"][0].get("link"))
        self.assertFalse(report.safe_link("https://www.legifrance.gouv.fr/a" + sep))

    def test_a_learned_code_title_must_look_like_one(self):
        before = list(codes.TITLES)
        try:
            new = learn(["de", "Code de\nla fraude", "Code des mines sous-marines"])
            self.assertEqual(new, ["Code des mines sous-marines"])
        finally:
            codes.TITLES[:] = before
            codes._build()

    def test_a_cited_date_that_is_not_a_date_is_not_sent(self):
        from citecheck.countries.france import wire
        cit = {"kind": "decision", "order": "lower", "jurisdiction": "tcom",
               "number": "2025F00234", "cited_date": "le client Dupont"}
        self.assertIsNotNone(wire.refusal(cit))
        self.assertIsNotNone(wire.refusal({**cit, "cited_date": "2025-02-30"}))
        self.assertIsNone(wire.refusal({**cit, "cited_date": "2025-03-12"}))

    def test_a_short_answer_is_not_a_decision_text(self):
        from unittest import mock
        from citecheck.countries.france import decision_quotes
        notice = "Document temporairement indisponible. " * 4          # 150 caractères
        with mock.patch.object(decision_quotes, "judilibre_text", return_value=notice):
            v, why, *_ = decision_quotes.check(
                {"quote": "la signification à domicile est nulle de plein droit"},
                ("CONFIRMED", "ok", "2023-12-21", DecisionQuotes.LINK), {"PISTE_API_KEY": "k"})
        self.assertEqual(v, "CONFIRMED")
        self.assertIn("non contrôlé", why)

    def test_a_page_that_reads_too_slowly_stops_the_reading(self):
        import tempfile
        from pathlib import Path
        from unittest import mock
        from pypdf import PageObject
        from citecheck import reader
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "lent.pdf"
            AnnotatedPdf.pdf(AnnotatedPdf(), src)
            clock = iter([0, 0, 31, 31, 31])       # début, avant la page, après : 31 s
            with mock.patch.object(reader.time, "monotonic", lambda: next(clock)):
                with self.assertRaises(reader.Unreadable) as said:
                    reader.text_of(src)
            self.assertIn("lente", str(said.exception))

class ArticleAndItsCode(unittest.TestCase):
    """Le PDF annoté surligne l'article et ce à quoi il est rattaché d'un seul tenant : le
    lecteur voit sur la page quel code, quelle loi, quelle convention a été retenu."""

    def spans(self, text):
        return [text[slice(*c["span"])] for c in extract(text)[0]]

    def test_one_block_for_the_article_and_its_code(self):
        self.assertEqual(self.spans("Selon l'article 1240 du Code civil, tout fait."),
                         ["article 1240 du Code civil"])
        self.assertEqual(self.spans("C. trav., art. L. 1152-1."), ["C. trav., art. L. 1152-1"])
        self.assertEqual(self.spans("article 22 de la loi n° 89-462 du 6 juillet 1989."),
                         ["article 22 de la loi n° 89-462 du 6 juillet 1989"])
        self.assertEqual(self.spans("article L. 110-1 du code de commerce. L'article 1240 du "
                                    "même code."),
                         ["article L. 110-1 du code de commerce", "article 1240 du même code"])
        self.assertEqual(self.spans("article 5 de la convention collective (IDCC 1979)."),
                         ["article 5 de la convention collective (IDCC 1979"])

    def test_one_block_for_the_court_the_date_and_the_number(self):
        self.assertEqual(self.spans("(CE, 30 novembre 2018, n° 402517)."),
                         ["CE, 30 novembre 2018, n° 402517"])
        self.assertEqual(self.spans("(Cass. soc., 14 décembre 2017, n° 16-26694)."),
                         ["Cass. soc., 14 décembre 2017, n° 16-26694"])
        self.assertEqual(self.spans("(CJUE, 6 octobre 2021, C-561/19)."),
                         ["CJUE, 6 octobre 2021, C-561/19"])
        self.assertEqual(self.spans("le Conseil constitutionnel (Cons. const., 12 mai 2010, "
                                    "n° 2010-605 DC)."),
                         ["Cons. const., 12 mai 2010, n° 2010-605 DC"])

    def test_a_block_never_takes_what_belongs_to_the_previous_one(self):
        self.assertEqual(self.spans("CE n° 308850 du 5 juin 2009 et n° 402517."),
                         ["CE n° 308850 du 5 juin 2009", "n° 402517"])

    def test_the_article_alone_when_the_block_is_not_on_the_page(self):
        import tempfile
        from pathlib import Path
        from citecheck import annotate, reader
        helper = AnnotatedPdf()
        with tempfile.TemporaryDirectory() as tmp:
            src, out = Path(tmp) / "c.pdf", Path(tmp) / "out.pdf"
            helper.pdf(src)
            doc = reader.read(src)
            start = doc.text.index("article 1240")
            cit = {"kind": "article", "code": "Code civil", "number": "1240",
                   "court": "Code civil", "verdict": "ARTICLE_IN_FORCE", "explanation": "x",
                   "location": {"page": 1, "page_exact": True, "in_notes": False,
                                "excerpt": "", "text": "article 1240 introuvable", "nth": 0,
                                "core": annotate.anchor(doc.text, start, start + 12)}}
            placed, missed = annotate.annotate(src, out, report.build("c.pdf", "france",
                                                                      [cit], []))
            self.assertEqual((placed, missed), (1, 0))

class CleanBlocks(unittest.TestCase):
    """Audit du 01/10/2026 (4) : un bloc surligné ne couvre que ce qui a été retenu. Sinon,
    le numéro seul. Et l'étendue surlignée ne change jamais la citation extraite."""

    def seen(self, text):
        return [(c["court"], c["number"], c.get("cited_date"), c.get("chamber"),
                 text[slice(*c["span"])]) for c in extract(text)[0]]

    def test_a_number_next_to_another_court_is_not_an_appeal(self):
        self.assertEqual(self.seen("La Cour de cassation et la CEDH, n° 16-26694."), [])
        # La mention écartée n'avale pas la suivante, ni sa chambre.
        self.assertEqual(
            self.seen("La Cour de cassation et la CEDH, n° 16-26694 du 14 décembre 2017. "
                      "Cass. soc., n° 16-26694 du 14 décembre 2017."),
            [("Cass", "16-26694", "2017-12-14", "soc",
              "Cass. soc., n° 16-26694 du 14 décembre 2017")])

    def test_a_block_never_covers_another_citation(self):
        seen = self.seen("IDCC 1979, Cass. soc., 14 décembre 2017, n° 16-26694, article 5 de "
                         "la convention collective.")
        self.assertEqual([s[-1] for s in seen],     # l'IDCC écrit avant n'est pas repris
                         ["Cass. soc., 14 décembre 2017, n° 16-26694",
                          "article 5 de la convention collective"])
        seen = self.seen("article 5 de la convention collective et article 12 de la "
                         "convention collective (IDCC 1979).")
        self.assertEqual(seen[0][-1], "article 5 de la convention collective")    # pas le 12
        seen = self.seen("article 1240, CE 5 juin 2009 n° 402517, du Code civil.")
        self.assertEqual([s[-1] for s in seen], ["CE 5 juin 2009 n° 402517"])
        seen = self.seen("CE, n° 402517, article 1240 du Code civil, 5 juin 2009.")
        self.assertEqual([s[-1] for s in seen], ["n° 402517", "article 1240 du Code civil"])

    def test_a_block_never_covers_what_was_not_kept(self):
        # « Cass. soc. » n'est pas la juridiction retenue.
        self.assertEqual(self.seen("CE, n° 402517, Cass. soc. du 14 décembre 2017.")[0][-1],
                         "n° 402517")
        # Deux dates qui se contredisent : aucune n'est retenue, aucune n'est peinte.
        self.assertEqual(self.seen("Cass., arrêt du 1er janvier 2010 (et non du 21 mars 2019), "
                                   "n° 16-26694.")[0][-1], "16-26694")

    def test_the_kept_chamber_is_in_the_block(self):
        self.assertEqual(self.seen("La chambre sociale de la Cour de cassation, 14 décembre "
                                   "2017, n° 16-26694.")[0][-1],
                         "chambre sociale de la Cour de cassation, 14 décembre 2017, "
                         "n° 16-26694")
        self.assertEqual(self.seen("Cass., n° 16-26694, la deuxième chambre civile a jugé "
                                   "cela.")[0][-1],
                         "Cass., n° 16-26694, la deuxième chambre civile")
        self.assertEqual(self.seen("Cass. soc., 14 décembre 2017, pourvoi n° 16-26.694.")[0][-1],
                         "Cass. soc., 14 décembre 2017, pourvoi n° 16-26.694")

    def test_a_block_never_crosses_a_page(self):
        seen = self.seen("article 1240 du Code civil. C. trav.,\farticle 1240.")
        self.assertEqual([(s[0], s[-1]) for s in seen],
                         [("Code civil", "article 1240 du Code civil"),
                          ("Code du travail", "article 1240")])

    def test_the_report_follows_the_numbers_not_the_blocks(self):
        seen = self.seen("IDCC 1979, Cass. soc., 14 décembre 2017, n° 16-26694, article 5 de "
                         "la convention collective (IDCC 1979).")
        self.assertEqual([s[1] for s in seen], ["16-26694", "5"])

    def test_the_piece_is_not_kept_after_an_error(self):
        import importlib
        from unittest import mock
        ex = importlib.import_module("citecheck.countries.france.extract")
        with mock.patch.object(ex, "_cited_chamber", side_effect=RuntimeError):
            with self.assertRaises(RuntimeError):
                ex.extract("PIECE_SECRETE Cass. soc., 14 décembre 2017, n° 16-26694.")
        self.assertIsNone(ex._ENDS[0])

    def test_the_second_page_gets_its_own_highlight(self):
        import tempfile
        from pathlib import Path
        from pypdf import PdfWriter
        from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject
        from citecheck import annotate, reader
        from citecheck.engine import COUNTRIES
        with tempfile.TemporaryDirectory() as tmp:
            src, out = Path(tmp) / "deux.pdf", Path(tmp) / "out.pdf"
            w = PdfWriter()
            font = w._add_object(DictionaryObject({
                NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"):
                NameObject("/Type1"), NameObject("/BaseFont"): NameObject("/Helvetica")}))
            for line in (b"article 1240 du Code civil. C. trav.,", b"article 1240."):
                page = w.add_blank_page(595, 842)
                page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"):
                                                                   DictionaryObject({NameObject("/F1"): font})})
                body = DecodedStreamObject()
                body.set_data(b"BT /F1 12 Tf 72 700 Td (" + line + b") Tj ET")
                page[NameObject("/Contents")] = w._add_object(body)
            with open(src, "wb") as f:
                w.write(f)
            doc = reader.read(src)
            citations, _ = extract(doc.text)
            results = []
            for c, verdict in zip(citations, ("ARTICLE_IN_FORCE", "ARTICLE_NOT_FOUND")):
                start, end = c.pop("span")
                core = c.pop("core", None)
                loc = {"page": doc.locate(start)[0], "page_exact": True, "in_notes": False,
                       "excerpt": "", **annotate.anchor(doc.text, start, end)}
                if core:
                    loc["core"] = annotate.anchor(doc.text, *core)
                results.append({**c, "verdict": verdict, "explanation": "x", "location": loc})
            self.assertEqual([r["location"]["page"] for r in results], [1, 2])
            self.assertEqual(annotate.annotate(src, out, report.build("deux.pdf", "france",
                                                                      results, [])), (2, 0))
            from pypdf import PdfReader
            pages = PdfReader(out).pages        # la page 0 est la notice
            self.assertEqual(len(pages[1].get("/Annots", [])), 1)
            self.assertEqual(len(pages[2].get("/Annots", [])), 1)

class BlockTemplates(unittest.TestCase):
    """Audit du 01/10/2026 (5) : un bloc n'est gardé que s'il suit un modèle autorisé, fait des
    seuls morceaux retenus et de mots de liaison. Tout le reste : le numéro seul."""

    def blocks(self, text):
        return [text[slice(*c["span"])] for c in extract(text)[0]]

    def test_several_articles_each_their_own_number(self):
        self.assertEqual(self.blocks("articles 1240 et 1241 du Code civil."), ["1240", "1241"])
        self.assertEqual(self.blocks("articles 5 et 12 de la convention collective (IDCC 1979)."),
                         ["5", "12"])

    def test_nothing_between_an_article_and_its_code_but_link_words(self):
        self.assertEqual(self.blocks("article 1240, CE 5 juin 2009, du Code civil."),
                         ["CE 5 juin 2009"])       # le 1240 n'est pas sûr : non vérifié
        self.assertEqual(self.blocks("article 5 de la convention collective, CE, 5 juin 2009, "
                                     "(IDCC 1979)."),
                         ["article 5 de la convention collective", "CE, 5 juin 2009"])
        self.assertEqual(self.blocks("article 1240, alinéa 2, du Code civil."),
                         ["article 1240, alinéa 2, du Code civil"])

    def test_no_stray_number_or_court_in_a_decision_block(self):
        for text in ("CE, T-12/15, 5 juin 2009, n° 402517.", "CE, C3911, 5 juin 2009, n° 402517.",
                     "CE, 2025J05588, 5 juin 2009, n° 402517.",
                     "CE, 2010-14 L, 5 juin 2009, n° 402517."):
            with self.subTest(text=text):
                self.assertEqual(self.blocks(text), ["n° 402517"])
        for text in ("Cass. soc., IDCC 1979, 14 décembre 2017, n° 16-26694.",
                     "Cass. soc., loi n° 89-462, 14 décembre 2017, n° 16-26694.",
                     "Crim., Soc., 14 décembre 2017, n° 16-26694.",
                     "Cass. soc., cour d'assises, 14 décembre 2017, n° 16-26694.",
                     "La CEDH, pourvoi n° 16-26694."):
            with self.subTest(text=text):
                self.assertEqual(self.blocks(text), ["16-26694"])
        self.assertEqual(self.blocks("CEDH, Cass. soc., 14 décembre 2017, n° 16-26694."),
                         ["Cass. soc., 14 décembre 2017, n° 16-26694"])
        self.assertEqual(self.blocks("TA, CE, 5 juin 2009, n° 402517."),
                         ["CE, 5 juin 2009, n° 402517"])
        self.assertEqual(self.blocks("CE, TA, 5 juin 2009, n° 402517."),
                         ["TA, 5 juin 2009, n° 402517"])
        self.assertEqual(self.blocks("CAA de Nancy CE, 12 avril 2018, n° 17NC01414."),
                         ["12 avril 2018, n° 17NC01414"])

    def test_ordinary_citations_stay_whole(self):
        for text in ("Cass. soc., 14 décembre 2017, pourvoi n° 16-26.694",
                     "Cass. soc., arrêt du 14 décembre 2017, n° 16-26694",
                     "Civ. 2e, 5 mars 2019, pourvoi n° 18-12.345",
                     "Conseil d'État du 5 juin 2009, n° 308850",
                     "CA Aix-en-Provence, 5 juin 2009, RG n° 11/18803",
                     "T. com. Paris, 12 mars 2025, n° 2025F00234",
                     "CAA de Châlons-en-Champagne, 12 avril 2018, n° 17NC01414",
                     "Cons. const., décision n° 2010-605 DC du 12 mai 2010",
                     "CJUE, 8 septembre 2015, C-561/19"):
            with self.subTest(text=text):
                self.assertEqual(self.blocks(text + "."), [text])

    def test_a_repeat_shows_its_chamber_only_if_it_is_the_verdicts(self):
        c = extract("Voir Civ. 2e, 21 mars 2019, n° 17-28268. Plus loin (Soc., 21 mars 2019, "
                    "n° 17-28268).")[0][0]
        text = ("Voir Civ. 2e, 21 mars 2019, n° 17-28268. Plus loin (Soc., 21 mars 2019, "
                "n° 17-28268).")
        self.assertEqual([text[a:b] for a, b in c["repeats"]], ["17-28268"])

    def test_two_articles_on_one_line_two_rectangles(self):
        import tempfile
        from pathlib import Path
        from pypdf import PdfReader
        from citecheck import annotate, reader
        helper = AnnotatedPdf()
        with tempfile.TemporaryDirectory() as tmp:
            src, out = Path(tmp) / "a.pdf", Path(tmp) / "out.pdf"
            helper.LINE = "articles 1240 et 9999 du Code civil."
            helper.pdf(src)
            doc = reader.read(src)
            results = []
            for c, verdict in zip(extract(doc.text)[0], ("ARTICLE_IN_FORCE",
                                                          "ARTICLE_NOT_FOUND")):
                start, end = c.pop("span")
                c.pop("core", None)
                results.append({**c, "verdict": verdict, "explanation": "x", "location": {
                    "page": 1, "page_exact": True, "in_notes": False, "excerpt": "",
                    **annotate.anchor(doc.text, start, end)}})
            self.assertEqual(annotate.annotate(src, out, report.build("a.pdf", "france",
                                                                      results, [])), (2, 0))
            rects = [tuple(float(x) for x in a.get_object()["/Rect"])
                     for a in PdfReader(out).pages[1]["/Annots"]
                     if a.get_object()["/Subtype"] == "/Highlight"]
            self.assertEqual(len(rects), 2)
            self.assertLessEqual(rects[0][2], rects[1][0])      # côte à côte, jamais l'un sur l'autre


class AuditPass6(unittest.TestCase):
    """Audit du 01/10/2026 (6) : un code ou une loi n'est pas pris à l'article d'à côté, et
    aucun mot ne porte deux couleurs."""

    def read(self, text):
        return [(c["number"], c["court"], text[slice(*c["span"])]) for c in extract(text)[0]]

    def test_code_written_before_belongs_to_the_next_article(self):
        self.assertEqual(self.read("C. civ., art. 1240, C. trav., art. L. 1152-1."),
                         [("1240", "Code civil", "C. civ., art. 1240"),
                          ("L1152-1", "Code du travail", "C. trav., art. L. 1152-1")])
        self.assertEqual(self.read("C. com., art. L. 110-1, C. civ., art. 1240.")[0][:2],
                         ("L110-1", "Code de commerce"))
        self.assertEqual(
            [r[:2] for r in self.read("Voir C. trav., art. L. 1152-1 et CGI, art. 46 quater-0 "
                                      "ZZ bis ; loi n° 89-462 du 6 juillet 1989, art. 22.")],
            [("L1152-1", "Code du travail"), ("46 quater-0 ZZ bis", "Code général des impôts"),
             ("22", "Loi n° 89-462 du 6 juillet 1989")])
        # Sans code écrit avant, le code qui suit reste celui de l'article.
        self.assertEqual(self.read("art. L. 1152-1 C. trav., article 1240 du Code civil.")[0][:2],
                         ("L1152-1", "Code du travail"))

    def test_a_law_already_taken_is_not_taken_again(self):
        self.assertEqual(
            self.read("article 22 de la loi n° 89-462 du 6 juillet 1989, article 1240 du Code "
                      "civil."),
            [("22", "Loi n° 89-462 du 6 juillet 1989",
              "article 22 de la loi n° 89-462 du 6 juillet 1989"),
             ("1240", "Code civil", "article 1240 du Code civil")])
        # La loi de l'article 22 est sans doute celle du 23, mais rien ne le dit : non vérifié.
        text = "article 22 de la loi n° 89-462 du 6 juillet 1989, article 23."
        self.assertEqual([r[0] for r in self.read(text)], ["22"])
        self.assertIn("pas certain : 23", " ".join(extract(text)[1]))

    def test_no_word_under_two_colours(self):
        for text in ("C. civ., art. 1240, C. trav., art. L. 1152-1, art. 1241.",
                     "article 1240 du Code civil, art. 1241.",
                     "article 22 de la loi n° 89-462 du 6 juillet 1989, article 23.",
                     "Cass. soc., 14 décembre 2017, n° 16-26694, article 1240 du Code civil.",
                     "article 5 de la convention collective (IDCC 1979), Cass. soc., "
                     "14 décembre 2017, n° 16-26694. Plus loin, Cass. soc., 14 décembre 2017, "
                     "n° 16-26694."):
            with self.subTest(text=text):
                cs = extract(text)[0]
                spans = sorted([tuple(c["span"]) for c in cs]
                               + [tuple(s) for c in cs for s in c.get("repeats", [])])
                for (_, b), (a, _) in zip(spans, spans[1:]):
                    self.assertLessEqual(b, a)

    def test_a_convention_name_is_a_name(self):
        for text in ("article 5 de la convention collective « le salarié a droit au paiement "
                     "du salaire » (IDCC 1979).",
                     "article 5 de la convention collective : les salariés ont droit à un "
                     "délai (IDCC 1979).",
                     "article 5 de la convention collective, ce que le salarié conteste "
                     "(IDCC 1979).",
                     "article 5 de la convention collective applicable (IDCC 1979).",
                     "article 5 de la convention collective des salariés contestent le "
                     "licenciement (IDCC 1979).",
                     "article 5 de la convention collective nationale des hôtels, cafés, "
                     "restaurants (IDCC 1979)."):
            with self.subTest(text=text):
                self.assertEqual(self.read(text),
                                 [("5", "IDCC 1979", "article 5 de la convention collective")])
        for text in ("article 5 de la convention collective (IDCC 1979).",
                     "article 5 de la convention collective nationale (IDCC 1979)."):
            self.assertEqual(self.read(text)[0][2], text[:-2])

    def test_a_chain_of_codes_written_after(self):
        """Audit du 01/10/2026 (7) : le code écrit derrière l'article précédent n'est pas
        celui de l'article suivant."""
        self.assertEqual(
            [r[:2] for r in self.read("art. 1240 C. civ., art. L. 1152-1 C. trav., "
                                      "art. L. 110-1 C. com.")],
            [("1240", "Code civil"), ("L1152-1", "Code du travail"),
             ("L110-1", "Code de commerce")])
        self.assertEqual(
            [r[:2] for r in self.read("art. 1240 C. civ., art. 222 C. pén., art. L. 1152-1 "
                                      "C. trav., art. L. 110-1 C. com.")],
            [("1240", "Code civil"), ("222", "Code pénal"), ("L1152-1", "Code du travail"),
             ("L110-1", "Code de commerce")])
        self.assertEqual(
            [r[:2] for r in self.read("article 1240 du Code civil, art. L. 1152-1 C. trav., "
                                      "art. 1241 C. pén.")],
            [("1240", "Code civil"), ("L1152-1", "Code du travail"), ("1241", "Code pénal")])
        self.assertEqual(
            [r[:2] for r in self.read("C. civ., art. 1240, C. trav., art. L. 1152-1, "
                                      "C. com., art. L. 110-1.")],
            [("1240", "Code civil"), ("L1152-1", "Code du travail"),
             ("L110-1", "Code de commerce")])
        self.assertEqual(
            [r[:2] for r in self.read("C. civ., art. 1240 et/ou C. trav., art. L. 1152-1.")],
            [("1240", "Code civil"), ("L1152-1", "Code du travail")])

    def test_only_du_ties_a_following_code(self):
        """Audit du 01/10/2026 (8) : un article qui a déjà son code ou sa loi devant lui ne
        prend le code qui suit que si « du », « de la »... l'y rattachent."""
        for text in ("C. civ., art. 1240, al. 2, C. trav., art. L. 1152-1.",
                     "C. civ., art. 1240, ainsi que C. trav., art. L. 1152-1.",
                     "C. civ., art. 1240, notamment C. trav., art. L. 1152-1.",
                     "C. civ., art. 1240 - C. trav., art. L. 1152-1.",
                     "C. civ., art. 1240 (C. trav., art. L. 1152-1)."):
            with self.subTest(text=text):
                self.assertEqual([r[:2] for r in self.read(text)],
                                 [("1240", "Code civil"), ("L1152-1", "Code du travail")])
        # « de » en suspens devant le code suivant (audit 10) : non vérifié.
        self.assertEqual(self.read("C. civ., art. 1240, au visa de C. trav., art. L. 1152-1."), [])
        self.assertEqual(self.read("décret n° 2016-334 du 21 mars 2016, article 1, au visa du "
                                   "C. civ., art. 1240."), [])
        for text, label in [("loi n° 89-462 du 6 juillet 1989, article 22, ainsi que C. civ., "
                             "art. 1240.", "Loi n° 89-462 du 6 juillet 1989"),
                            ("ordonnance n° 2020-306 du 25 mars 2020, article 2, voir C. trav., "
                             "art. L. 1152-1.", "Ordonnance n° 2020-306 du 25 mars 2020")]:
            with self.subTest(text=text):
                self.assertEqual(self.read(text)[0][1], label)
        # Deux codes qui se contredisent : non vérifié.
        self.assertEqual(self.read("C. civ., art. 1240, alinéa 2 du Code du travail."), [])

    def test_same_code_wins_over_the_next_one(self):
        for text in ("C. civ., art. 1240, art. 1241 du même code, C. trav., art. L. 1152-1.",
                     "art. 1240 C. civ., art. 1241 dudit code, C. pén., art. 222-33.",
                     "article 1240 du Code civil, article 1241 du même code, C. trav., "
                     "art. L. 1152-1."):
            with self.subTest(text=text):
                self.assertEqual(self.read(text)[1][:2], ("1241", "Code civil"))
        self.assertEqual(
            [r[:2] for r in self.read("art. 1240 du Code civil. L'article L. 1152-1 du Code du "
                                      "travail s'applique.")],
            [("1240", "Code civil"), ("L1152-1", "Code du travail")])
        self.assertEqual(self.read("art. 1240 C. civ., art. 1241 du code précité.")[1][2],
                         "art. 1241 du code précité")
        self.assertEqual([r[2] for r in self.read("art. 1240 (C. civ.), art. L. 1152-1 "
                                                  "(C. trav.).")],
                         ["art. 1240 (C. civ.)", "art. L. 1152-1 (C. trav.)"])

    def test_audit_9(self):
        """Audit du 02/10/2026 (9)."""
        law = "Loi n° 89-462 du 6 juillet 1989"
        cases = [
            # un nom de code derrière « de ce », « dudit », « du même » est lu...
            ("article 222-33 de ce code du travail.", [("222-33", "Code du travail")]),
            ("article 111-1 du même code du travail.", [("111-1", "Code du travail")]),
            # ... mais s'il contredit le code ou la loi écrit devant : non vérifié
            ("C. pén., article 222-33 de ce code du travail.", []),
            ("loi n° 89-462 du 6 juillet 1989, article 22 dudit code civil.", []),
            ("art. 1240, C. trav., art. L. 1152-1.", []),
            ("art. 1240, al. 2, C. civ., art. L. 1152-1, al. 1, C. trav.", []),
            ("art. 1240, C. civ., art. L. 1152-1, C. trav., art. L. 110-1.", []),
            ("article 1240 du Code civil, art. 1241.", [("1240", "Code civil")]),
            # « (du », un point, un saut de page, une virgule ne rattachent pas
            ("loi n° 89-462 du 6 juillet 1989, article 22 (du code civil).", []),
            # un « du » en suspens : le code qui suit peut être de l'un ou de l'autre
            ("C. civ., art. 1240. du Code du travail, art. L. 1152-1.", []),
            # « du » rattache le Code du travail au 1240 : le L. 1152-1 n'a plus de code sûr
            ("C. civ., art. 1240 du\fCode du travail, art. L. 1152-1.", []),
            ("C. civ., art. 1240 au C. trav., art. L. 1152-1.", []),
            ("art. 1240, C. civ.", [("1240", "Code civil")]),
            ("article 2 de la loi n° 2014-626 du 18 juin 2014, dite loi Pinel.",
             [("2", "Loi n° 2014-626 du 18 juin 2014")]),
            ("article 22 de la loi n° 89-462 du 6 juillet 1989 modifiée par la loi n° 2014-366 "
             "du 24 mars 2014.", [("22", law)]),
            ("article 22 de la loi n° 89-462 du 6 juillet 1989 ou de la loi n° 2014-366 du "
             "24 mars 2014.", []),
            ("article 22 de la loi du 6 juillet 1989 ou du 24 mars 2014.", []),
            ("article 5 de la convention collective (IDCC 1979 ou IDCC 1486).", []),
            ("C. pén. et C. trav., art. L. 1152-1. L'article 222-33 du même code.", []),
            ("Le Code civil et le Code pénal s'appliquent. L'article 222-33 du même code.", []),
            ("L'article 1240, et non le Code pénal, fonde l'action.", []),
            ("article 22 du Code civil ou de la loi n° 89-462 du 6 juillet 1989.", []),
            ("C. pén., article 222-33 (Code du travail).", []),
            ("Code civil, art. 1240, du Code du travail, art. L. 1152-1.", []),
            # « modifiée », « dite » gardent la loi
            ("loi n° 89-462 du 6 juillet 1989 modifiée, article 22, C. civ., art. 1240.",
             [("22", law), ("1240", "Code civil")]),
            ("loi n° 89-462 du 6 juillet 1989, dite loi Mermaz, article 22, C. civ., art. 1240.",
             [("22", law), ("1240", "Code civil")]),
            # « du code » seul ne reprend pas un code quand un complément suit
            ("article 1240 du Code civil. L'article 6 du code de déontologie des avocats "
             "s'applique.", [("1240", "Code civil")]),
            ("article 1240 du Code civil. Le Code du travail est applicable. L'article "
             "L. 1152-1 du même code prévoit le harcèlement.", [("1240", "Code civil")]),
            ("article 1241 du même code, C. trav., art. L. 1152-1.",
             [("L1152-1", "Code du travail")]),
            ("article L. 1152-1 du Code du travail. C. civ., art. 1240 du même code.",
             [("L1152-1", "Code du travail")]),
            # une convention citée après une virgule ne prend pas l'article qui a son code
            ("C. civ., art. 1240, convention collective (IDCC 1979), art. L. 1152-1 C. trav.",
             []),
            # l'ancien code civil n'est pas celui d'aujourd'hui
            ("loi n° 89-462 du 6 juillet 1989, article 1382 de l'ancien code civil.", []),
            ("article 1 du Code de la Légion d'honneur, de la Médaille militaire et de l'ordre "
             "national du Mérite.",
             [("1", "Code de la Légion d'honneur, de la Médaille militaire et de l'ordre "
                    "national du Mérite")]),
        ]
        for text, want in cases:
            with self.subTest(text=text):
                self.assertEqual([r[:2] for r in self.read(text)], want)

    def test_a_law_written_before_is_kept(self):
        law = "Loi n° 89-462 du 6 juillet 1989"
        for text, second in [("loi n° 89-462 du 6 juillet 1989, article 22, C. civ., art. 1240.",
                               ("1240", "Code civil")),
                              ("loi n° 89-462 du 6 juillet 1989, article 22 et C. civ., "
                               "art. 1240.", ("1240", "Code civil"))]:
            with self.subTest(text=text):
                self.assertEqual([r[:2] for r in self.read(text)], [("22", law), second])
        self.assertEqual(
            [r[:2] for r in self.read("loi n° 89-462 du 6 juillet 1989, article 20, décret "
                                      "n° 2016-334 du 21 mars 2016, article 31.")],
            [("20", law), ("31", "Décret n° 2016-334 du 21 mars 2016")])
        self.assertEqual(
            [r[:2] for r in self.read("C. civ., art. 1240, article 31 du décret n° 2016-334 du "
                                      "21 mars 2016.")],
            [("1240", "Code civil"), ("31", "Décret n° 2016-334 du 21 mars 2016")])
        # Une loi déjà prise par l'article d'avant ne l'emporte pas sur le code qui suit,
        # comme dans « art. 1240 C. civ., art. L. 1152-1 C. trav. ».
        self.assertEqual(
            [r[:2] for r in self.read("article 20 de la loi n° 89-462 du 6 juillet 1989, "
                                      "art. L. 1152-1 C. trav., art. L. 110-1 C. com.")],
            [("20", law), ("L1152-1", "Code du travail"), ("L110-1", "Code de commerce")])
        self.assertEqual(self.read("décret n° 2016-334 du 21 mars 2016, article 1, C. civ., "
                                   "art. 1240.")[0][1][:6], "Décret")

    def test_one_place_after_the_court(self):
        self.assertEqual(self.read("CA Paris Dupont, 5 juin 2009, RG n° 11/18803.")[0][2],
                         "RG n° 11/18803")
        self.assertEqual(self.read("CAA de Paris Le Conseil, 12 avril 2018, n° 17NC01414.")[0][2],
                         "17NC01414")
        self.assertEqual(self.read("TJ Le Mans, 5 juin 2009, RG n° 11/18803.")[0][2],
                         "TJ Le Mans, 5 juin 2009, RG n° 11/18803")

    def test_court_and_tribunal_of_the_union_apart(self):
        self.assertEqual(self.read("Trib. UE, 8 septembre 2015, C-561/19.")[0][2],
                         "8 septembre 2015, C-561/19")
        self.assertEqual(self.read("CJUE, 8 septembre 2015, T-12/15.")[0][2],
                         "8 septembre 2015, T-12/15")
        self.assertEqual(self.read("Trib. UE, 8 septembre 2015, T-12/15.")[0][2],
                         "Trib. UE, 8 septembre 2015, T-12/15")

    def test_a_small_paragraph_number_only(self):
        self.assertEqual(self.read("article 1240, alinéa 1241, du Code civil."), [])

    def test_audit_11(self):
        """Audit du 02/10/2026 (11) : des modèles autorisés qui laissaient passer un doute."""
        civ, trav, law = "Code civil", "Code du travail", "Loi n° 89-462 du 6 juillet 1989"
        cases = [
            # « du même code » : nommé tout près, et seul autour
            ("Le Code pénal s'applique. " + "Texte sans article. " * 80
             + "L'article 222-33 du même code.", []),
            # celui de l'article d'avant, tout près, si aucun autre n'est nommé depuis
            ("Le Code pénal pose le principe. L'article 1240 du Code civil s'applique. "
             "L'article 6 du même code.", [("1240", civ), ("6", civ)]),
            ("La loi n° 2014-366 du 24 mars 2014 s'applique. L'article 22 de la loi n° 89-462 "
             "du 6 juillet 1989 est cité. L'article 2 de la même loi.", [("22", law), ("2", law)]),
            ("article 1240 du Code civil. Le Code du travail est applicable. L'article "
             "L. 1152-1 du même code.", [("1240", civ)]),
            ("article 1240 du Code civil, voir le Code pénal, article 1241 du même code.",
             [("1240", civ)]),
            ("selon l'article 1719 du code civil, le bailleur délivre la chose, et l'article "
             "1720 du même code met à sa charge les réparations.", [("1719", civ), ("1720", civ)]),
            ("Le logement relève de la loi n° 89-462 du 6 juillet 1989 : l'article 6 de cette "
             "loi impose un logement décent.", [("6", law)]),
            # formes courantes (document exemples/cas-courants.pdf)
            ("Le bail est régi par les articles L. 145-1 et suivants du code de commerce.",
             [("L145-1", "Code de commerce")]),
            ("V. art. 1240 et s. C. civ.", [("1240", civ)]),
            ("Vu l'article L. 1235-3 du code du travail, dans sa rédaction issue de la loi "
             "n° 2018-217 du 29 mars 2018 :", [("L1235-3", trav)]),
            ("Dans sa rédaction issue de l'ordonnance n° 2017-1387 du 22 septembre 2017, "
             "l'article L. 1235-3-1 du code du travail écarte le barème.", [("L1235-3-1", trav)]),
            ("la rupture relève de l'article L. 442-1, II, du code de commerce.",
             [("L442-1", "Code de commerce")]),
            ("Le Code du travail est applicable. L'article L. 1152-1 du même code.",
             [("L1152-1", trav)]),
            ("article 1240 du Code civil, article 1241 du même code.",
             [("1240", civ), ("1241", civ)]),
            ("art. 1240 C. civ., art. 1241 dudit code.", [("1240", civ), ("1241", civ)]),
            # un autre texte, même sans « de » : CEDH, RGPD, Charte, TFUE, CJUE, règlement
            ("article 8 du Code civil ou CEDH.", []),
            ("article 6 du Code civil ou RGPD.", []),
            ("article 8 du Code civil ou la Charte.", []),
            ("article 1240 du Code civil ou le TFUE.", []),
            ("article 1240 du Code civil ou le règlement général.", []),
            ("article L. 1152-1 du Code du travail, à la lumière du RGPD.", []),
            # un sigle, en minuscules aussi, est un mot entier
            ("article L. 2315-1 de la cssct.", []),
            ("article 700 cpcx.", []),
            ("article 700 du cpce.", [("700", "Code des procédures civiles d'exécution")]),
            # l'espace, comme la virgule, quand un autre article suit sans son code
            ("art. 1240 C. trav., art. L. 1152-1.", []),
            ("art. 1240 C. trav. art. L. 1152-1.", []),
            ("art. 222-33 C. pén., art. 1240 C. civ.",
             [("222-33", "Code pénal"), ("1240", civ)]),
            ("art. 1240 C. civ. et article 31 du décret n° 2016-334 du 21 mars 2016.",
             [("1240", civ), ("31", "Décret n° 2016-334 du 21 mars 2016")]),
            # deux IDCC dans la phrase, ou un IDCC écarté
            ("IDCC 1979 ou IDCC 1486, article 5 de la convention collective.", []),
            ("article 5 de la convention collective, et non l'IDCC 1979.", []),
            ("IDCC 1979, Cass. soc., 14 décembre 2017, n° 16-26694, article 5 de la convention "
             "collective (IDCC 1979).", [("16-26694", "Cass"), ("5", "IDCC 1979")]),
            # le CGI et une annexe écrits tous les deux
            ("article 46 du CGI (annexe III).", []),
            ("art. 46 du CGI, annexe III.", []),
            ("article 46 de l'annexe III au CGI.", [("46", "Code général des impôts, annexe III")]),
            ("CGI, ann. III, art. 46.", [("46", "Code général des impôts, annexe III")]),
            # un numéro nu et un numéro en L. sous un seul code
            ("articles 1240 et L. 1152-1 du Code du travail.", []),
            ("articles 1 ou L. 1152-1 du Code du travail.", []),
            ("articles L. 1152-1 et R. 1152-2 du Code du travail.",
             [("L1152-1", trav), ("R1152-2", trav)]),
        ]
        for text, want in cases:
            self.assertEqual([c[:2] for c in self.read(text)], want, text)

    def test_what_is_not_checked_is_shown(self):
        """Ce qui est relevé sans être vérifié sort en gris sur la page, jamais envoyé."""
        from citecheck.countries.france import check, extract as country_extract
        text = ("art. 1240, C. trav., art. L. 1152-1. L'article 6 de la Convention. "
                "(CPH Bordeaux, 6 octobre 2022, RG n° 21/01458).")
        self.assertEqual(extract(text)[0], [])          # pas pour l'extraction seule
        found = country_extract(text)[0]
        self.assertEqual([(c["kind"], c["number"], text[slice(*c["span"])]) for c in found],
                         [("unverified", "1240", "art. 1240"),
                          ("unverified", "L1152-1", "art. L. 1152-1"),
                          ("unverified", "6", "article 6"),
                          ("unverified", "21/01458", "RG n° 21/01458")])
        results = check(found, {})
        self.assertEqual({r["verdict"] for r in results}, {"NOT_TESTED"})
        self.assertIn("prud'hommes", results[-1]["explanation"])

    def test_visual_pass(self):
        """Relecture des documents cas-*.pdf (02/10/2026)."""
        civ, cja = "Code civil", "Code de justice administrative"
        ceseda = "Code de l'entrée et du séjour des étrangers et du droit d'asile"
        cases = [
            # « CE » de la Communauté européenne : pas une décision du Conseil d'État
            ("l'article 6 de la directive 2008/115/CE du 16 décembre 2008.", []),
            ("Le règlement (CE) du 22 décembre 2000 dispose.", []),
            # le dispositif du jugement : pas une citation ; « Article 1240 : » en est une
            ("annulé. Article 2 : Il est enjoint au préfet.", []),
            # « et aux articles » annonce l'article suivant
            ("l'article 388-1 du code civil et aux articles 338-1 et suivants du code de "
             "procédure civile.", [("388-1", civ), ("338-1", "Code de procédure civile")]),
            ("l'article 388-1 du code civil et au code pénal.", []),
            # « du même code » jusqu'à trois phrases ; un article sans code ne coupe pas le lien
            ("article 1240 du Code civil. (anciennement article 1382). L'article 1241 du même "
             "code.", [("1240", civ), ("1241", civ)]),
            ("article 1240 du Code civil. Le Code pénal réprime. (anciennement article 1382). "
             "L'article 1241 du même code.", [("1240", civ)]),
            # « du code précité » : le code avec lequel ce même article a déjà été cité
            ("article L. 423-23 du CESEDA. Vu le code de justice administrative. Vu le code "
             "civil. L'article L. 423-23 du code précité.", [("L423-23", ceseda)]),
            ("article 1240 du Code civil et article 1240 du Code pénal. Plus loin, l'article "
             "1240 du code précité.", [("1240", civ), ("1240", "Code pénal")]),
            # la formule des frais d'avocat devant le juge administratif
            ("des articles L. 761-1 du code de justice administrative et 37, alinéa 2, de la "
             "loi n° 91-647 du 10 juillet 1991.",
             [("L761-1", cja), ("37", "Loi n° 91-647 du 10 juillet 1991")]),
        ]
        for text, want in cases:
            self.assertEqual([c[:2] for c in self.read(text)], want, text)
        unverified = extract("Article 1240 : « Tout fait ».", unverified=True)[0]
        self.assertEqual([(c["kind"], c["number"]) for c in unverified], [("unverified", "1240")])

    def test_real_decisions(self):
        """Dix vraies décisions Judilibre (02/10/2026) : formules qui ne nomment aucun autre
        texte, listes d'articles, intervalles."""
        cpc, pen, cpp = "Code de procédure civile", "Code pénal", "Code de procédure pénale"
        cases = [
            # l'en-tête de chaque arrêt de la Cour de cassation
            ("composée, en application de l'article R. 431-5 du code de l'organisation "
             "judiciaire, du président et des conseillers précités, après en avoir délibéré "
             "conformément à la loi, a rendu le présent arrêt.",
             [("R431-5", "Code de l'organisation judiciaire")]),
            ("méconnu le principe d'interprétation stricte de la loi pénale, ainsi que les "
             "articles 111-4, 111-5 et 432-14 du code pénal, 591 et 593 du code de procédure "
             "pénale ; 2°/ que", [("111-4", pen), ("111-5", pen), ("432-14", pen),
                                  ("591", cpp), ("593", cpp)]),
            ("au titre de l'article 700 du code de procédure civile et aux entiers dépens ; - "
             "Ordonner l'exécution provisoire.", [("700", cpc)]),
            ("Vu l'article 700 du Code de procédure civile, Vu le Décret n°2015-1437 du 5 "
             "novembre 2015, Vu les pièces.", [("700", cpc)]),
            ("avisées conformément à l'article 450 al 2 du CPC. Signé par Mme X.",
             [("450", cpc)]),
            ("prévues par les articles 620, alinéa 1, et 1015 du code de procédure civile, "
             "l'arrêt", [("620", cpc), ("1015", cpc)]),
            ("Vu les articles L. 2315-27, alinéas 1 et 2, et L. 2315-38 du code du travail.",
             [("L2315-27", "Code du travail"), ("L2315-38", "Code du travail")]),
            ("l'article 2 du décret numéro 2016-382 du 30 mars 2016, fixant",
             [("2", "Décret n° 2016-382 du 30 mars 2016")]),
            ("la convention relative aux droits de l'enfant du 20 novembre 1989. 2°/ que "
             "seuls peuvent, dans les conditions prévues aux articles 26 et suivants du code "
             "civil, réclamer, selon des caractères déterminés par un décret en Conseil d'État "
             "; que", [("26", "Code civil")]),
            # mais « un autre texte » reste un doute
            ("l'article 1240 du code civil et la loi n° 89-462 du 6 juillet 1989.", []),
            ("l'article 1240 du code civil, au sens du décret en Conseil d'État n° 2016-382.",
             []),
            # un intervalle : ses bornes ne disent rien des articles entre elles
            ("articles 131-6 à 131-11 du code pénal et l'article 1240 du code civil.",
             [("1240", "Code civil")]),
        ]
        for text, want in cases:
            self.assertEqual([c[:2] for c in self.read(text)], want, text)
        grey = [(c["number"], c["court"], c["what"]) for c in extract(
            "les articles 131-4-1 à 131-11 et 132-25 à 132-70 du code pénal.",
            unverified=True)[0]]
        self.assertEqual(grey, [("131-4-1 à 131-11", pen, "range"),
                                ("132-25 à 132-70", pen, "range")])
        # Dix vraies décisions administratives d'ArianeWeb (02/10/2026).
        cja = "Code de justice administrative"
        ceseda = "Code de l'entrée et du séjour des étrangers et du droit d'asile"
        cases = [
            ("En vertu de l'article L. 522-3 du code de justice administrative, le juge des "
             "référés peut, par une ordonnance motivée, rejeter une requête.",
             [("L522-3", cja)]),
            ("dans l'hypothèse d'un règlement au fond de l'affaire, de mettre à sa charge la "
             "somme de 3 500 euros au titre de l'article L. 761-1 du code de justice "
             "administrative.", [("L761-1", cja)]),
            ("l'article 1er de la loi n° 68-1250 du 31 décembre 1968 : « sous réserve des "
             "dispositions de la présente loi, toutes créances qui n'ont pas été payées, à "
             "charge du règlement ; ».", [("1", "Loi n° 68-1250 du 31 décembre 1968")]),
            ("le premier alinéa de l'article 37-17 du décret n° 87-602 du 30 juillet 1987, dans "
             "sa rédaction issue du\ndécret n° 2019-301 du 10 avril 2019, dispose.",
             [("37-17", "Décret n° 87-602 du 30 juillet 1987")]),
            ("garanti par l'article 41 de la Charte des droits fondamentaux de l'Union "
             "européenne ; - elle méconnaît les dispositions de l'article L. 435-1 du code de "
             "l'entrée et du séjour des étrangers et du droit d'asile ;", [("L435-1", ceseda)]),
            ("les conditions posées par l'article 23-4 de l'ordonnance n° 58-1067 du 7 novembre "
             "1958 portant loi organique ne sont pas remplies. 2° Sous le n° 518021, Mme S. "
             "conteste la loi n° 2024-42.",
             [("23-4", "Ordonnance n° 58-1067 du 7 novembre 1958")]),
            ("au sens des dispositions du II de l'article 150 U du code général des impôts, "
             "que les autres constructions et aménagements annexes implantés sur la propriété.",
             [("150 U", "Code général des impôts")]),
            ("en application de l'article R. 611-7 du code de justice administrative, que la "
             "cour était susceptible de relever le moyen tiré du champ d'application de la loi.",
             [("R611-7", cja)]),
            # désignés, ils restent d'autres textes
            ("l'article L. 522-3 du code de justice administrative et l'ordonnance n° 2020-305.",
             []),
            ("l'article 1240 du code civil et le règlement (UE) 2016/679.", []),
            ("l'article 1240 du code civil et son annexe III.", []),
        ]
        for text, want in cases:
            self.assertEqual([c[:2] for c in self.read(text)], want, text)
        # Les décisions des tribunaux administratifs : la juridiction écrite après le numéro,
        # selon le modèle des visas, l'emporte sur celle d'une autre procédure nommée avant.
        for text, want in [
                ("conclusions de la demande. Par une ordonnance n° 2602422 du 5 mai 2026, le "
                 "juge des référés du tribunal administratif de Nice a suspendu l'exécution du "
                 "titre émis le 29 janvier 2026.", [("ta", "TA", "2602422", "2026-05-05")]),
                ("sa requête présentée devant la cour administrative d'appel de Paris tendant à "
                 "l'annulation de l'ordonnance n° 2508419 du 6 mai 2026 par laquelle la "
                 "présidente du tribunal administratif de Melun a rejeté sa demande.",
                 [("ta", "TA", "2508419", "2026-05-06")]),
                ("Par une ordonnance n° 2520445 du 16 juillet 2026, enregistrée le 21 juillet "
                 "2026 au secrétariat du contentieux du Conseil d'Etat, la présidente de la "
                 "12ème chambre du tribunal administratif de Cergy-Pontoise a décidé.",
                 [("ta", "TA", "2520445", "2026-07-16")]),
                ("Par un jugement n° 1908677/4 du 25 novembre 2022, le tribunal administratif "
                 "de Montreuil a annulé la décision du 11 juin 2019 du maire.",
                 [("ta", "TA", "1908677", "2022-11-25")]),
                # sans le modèle, rien n'est deviné
                ("1° Sous le n° 517495, M. U..., à l'appui de sa requête présentée devant la "
                 "cour administrative d'appel de Paris.", []),
                # pas des décisions : une date sans rapport derrière une juridiction
                ("a transmis au Conseil d'Etat un courrier du 21 juillet 2026.", []),
                ("la cour administrative d'appel de Paris, sur appel de M. L..., a annulé la "
                 "décision du 11 juin 2019 du maire.", [])]:
            got = [(c["order"], c["court"], c["number"], c["cited_date"])
                   for c in extract(text)[0] if c["kind"] == "decision"]
            self.assertEqual(got, want, text)
        rg = [(c["court"], c["cited_date"]) for c in extract(
            "contre un arrêt n° RG 23/07760 rendu le 28 novembre 2024 par la cour d'appel de "
            "Lyon (3e chambre A).")[0] if c["kind"] == "decision"]
        self.assertEqual(rg, [("CA Lyon", "2024-11-28")])

    def test_decision_dates_as_doctrine_writes_them(self):
        for text, day, block in [
                ("Cass. 2e civ., 7 avr. 2022, n° 20-19.977 rappelle", "2022-04-07",
                 "Cass. 2e civ., 7 avr. 2022, n° 20-19.977"),
                ("(Cass. ass. plén., avis, 17 juill. 2019, n° 19-70.010)", "2019-07-17",
                 "Cass. ass. plén., avis, 17 juill. 2019, n° 19-70.010"),
                ("(CE, sect., 19 juillet 2017, n° 403928)", "2017-07-19",
                 "CE, sect., 19 juillet 2017, n° 403928"),
                ("Les demandes antérieures au 9 juin 2018 sont prescrites (Cass. soc., 30 juin "
                 "2021, n° 19-10.161).", "2021-06-30", "Cass. soc., 30 juin 2021, n° 19-10.161"),
                ("arrêt du 1er janvier 1900 (et non du 21 mars 2019), n° 17-28.268.", None,
                 "17-28.268")]:
            c = extract(text)[0][0]
            self.assertEqual((c["cited_date"], text[slice(*c["span"])]), (day, block), text)


class GrokReview(unittest.TestCase):
    """Les vingt vraies décisions relues par Grok (02/10/2026) : les citations qui n'étaient
    pas relevées."""

    def read(self, text):
        return [(c["kind"], c["number"], c["court"], c.get("cited_date"))
                for c in extract(text, unverified=True, whole_texts=True)[0]]

    def test_articles(self):
        cpp, civ, trav = "Code de procédure pénale", "Code civil", "Code du travail"
        for text, want in [
                # le tiret coupé par une espace, au passage à la ligne
                ("en application de l'article R 4624 -31 du code du travail.",
                 [("article", "R4624-31", trav, None)]),
                ("au titre de l'article L. 761- 1 du code de justice administrative.",
                 [("article", "L761-1", "Code de justice administrative", None)]),
                # une liste qui passe par un autre texte
                ("a méconnu les articles 6 de la convention européenne des droits de l'homme, "
                 "préliminaire, 495-14, 591 et 593 du code de procédure pénale.",
                 [("unverified", "6", None, None),
                  ("unverified", None, "Convention européenne des droits de l'homme", None),
                  ("unverified", "Préliminaire", None, None),
                  ("article", "495-14", cpp, None), ("article", "591", cpp, None),
                  ("article", "593", cpp, None)]),
                ("Vu les articles 1134, alinéa 1er, dans sa rédaction antérieure à celle issue de "
                 "l'ordonnance n° 2016-131 du 10 février 2016, et 1869 du code civil :",
                 [("unverified", "1134", None, None),
                  ("text", "2016-131", "Ordonnance n° 2016-131 du 10 février 2016", None),
                  ("article", "1869", civ, None)]),
                # l'ordonnance d'une formule de version, citée par sa seule date
                ("au regard de l'article 1134 du code civil dans sa rédaction antérieure à "
                 "l'ordonnance du 24 février 2016.",
                 [("article", "1134", civ, None),
                  ("text", None, "Ordonnance du 24 février 2016", None)]),
                # mais pas la suite d'une liste que rien ne rattache à un texte
                ("les articles 5 de la convention, et 12 des locataires.",
                 [("unverified", "5", None, None)])]:
            self.assertEqual(self.read(text), want, text)

    def test_decisions_named_after_their_date(self):
        for text, want in [
                ("contre l'arrêt rendu le 31 janvier 2025 par la cour d'appel de Lyon "
                 "(chambre sociale C).", [("decision", None, "CA", "2025-01-31")]),
                ("Selon l'arrêt attaqué (Lyon, 31 janvier 2025), M. X a été engagé.",
                 [("decision", None, "CA", "2025-01-31")]),
                ("Par jugement en date du 10 septembre 2015, rendu en formation de départage, "
                 "le Conseil de Prudhommes a fait droit.",
                 [("decision", None, "CPH", "2015-09-10")]),
                ("Confirmer le jugement rendu par le conseil des prud'hommes de Basse-Terre le "
                 "12 décembre 2024.", [("decision", None, "CPH", "2024-12-12")]),
                # une saisine, une décision sans juridiction : rien
                ("Mme [G] a saisi le Conseil de prudhommes de BESANCON le 31 mars 2014.", []),
                ("Par jugement du 5 juillet 2019, la dissolution de la SCI a été prononcée.", []),
                # la date collée devant le pourvoi, à la manière des recueils
                ("Selon l'arrêt attaqué (Lyon, 28 novembre 2024), rendu sur renvoi après "
                 "cassation (Com., 4 octobre 2023, pourvoi n° 22-18.358), la société.",
                 [("decision", None, "CA", "2024-11-28"),
                  ("decision", "22-18.358", "Cass", "2023-10-04")]),
                ("( Cass. Soc, 6 mai 2009 numéro 07 44 485)",
                 [("decision", "07-44.485", "Cass", "2009-05-06")]),
                ("(CEDH, arrêt du 15 novembre 2016, Dubská et Krejzová, n° 28859/11 et "
                 "28473/12, §§ 174-178)", [("decision", "28859/11", "CEDH", "2016-11-15"),
                                          ("decision", "28473/12", "CEDH", "2016-11-15")]),
                # « ce tribunal » : le tribunal administratif nommé juste avant
                ("M. B... a demandé au tribunal administratif de Nice la décharge. Par un "
                 "jugement n° 2200015 du 18 juillet 2024, ce tribunal a rejeté sa demande.",
                 [("decision", "2200015", "TA", "2024-07-18")]),
                ("Par une ordonnance n° 2416353 du 2 mai 2025, le premier vice-président du "
                 "tribunal administratif de Montreuil a rejeté sa demande.",
                 [("decision", "2416353", "TA", "2025-05-02")])]:
            self.assertEqual(self.read(text), want, text)

    def test_other_texts_are_grey(self):
        got = self.read("Vu : - la Constitution ; - le règlement (UE) 2017/1001 du Parlement "
                        "européen et du Conseil du 14 juin 2017 ; - l'arrêté du 4 août 2004 "
                        "relatif aux commissions de réforme ; - la délibération n° 139/CP du 26 "
                        "mars 2004 ; - le code de justice administrative.")
        self.assertEqual(got, [("unverified", None, t, None) for t in [
            "Constitution du 4 octobre 1958", "Règlement (UE) 2017/1001",
            "Arrêté du 4 août 2004", "Délibération n° 139/CP",
            "Code de justice administrative"]])
        # le code d'un article n'est pas un code cité seul, ni « la constitution d'une société »
        self.assertEqual(self.read("l'article 1134 ancien du code civil ; la constitution d'une "
                                   "société."), [("unverified", "1134", None, None)])
        self.assertEqual(self.read("la méconnaissance des articles UC 1, 2 et 13 du règlement "
                                   "du plan local d'urbanisme."),
                         [("unverified", None, "Plan local d'urbanisme, articles UC 1, UC 2, "
                           "UC 13", None)])
        self.assertEqual(self.read("la Constitution, notamment son Préambule et son article 61-1."
                                   " Le Préambule du contrat."),
                         [("unverified", None, "Constitution du 4 octobre 1958", None),
                          ("unverified", None, "Préambule de la Constitution", None),
                          ("unverified", "61-1", None, None)])


class GrokSecondReview(unittest.TestCase):
    """Les deuxième et troisième passages de Grok sur les vingt vraies décisions (03/10/2026)."""

    def read(self, text):
        return [(c["kind"], c["number"], c["court"], c.get("cited_date"),
                 text[slice(*c["span"])])
                for c in extract(text, unverified=True, whole_texts=True)[0]]

    def test_the_date_of_another_decision(self):
        # Le pourvoi n'a pas la date de l'arrêt qu'il attaque, ni le RG celle du jugement déféré.
        self.assertEqual(self.read(
            "a formé le pourvoi n° A 24-17.185 contre l'arrêt rendu le 14 mai 2024 par la cour "
            "d'appel de Pau (2e chambre, section 1), dans le litige."),
            [("decision", "24-17.185", "Cass", None, "24-17.185"),
             ("decision", None, "CA", "2024-05-14",
              "arrêt rendu le 14 mai 2024 par la cour d'appel de Pau (2e chambre, section 1)")])
        self.assertEqual(self.read(
            "AFFAIRE N° : N° RG 25/00171\nDécision déférée à la Cour : Jugement du Conseil de "
            "Prud'hommes de Basse-Terre - section commerce - du 12 Décembre 2024.")[0][:4],
            ("unverified", "25/00171", None, None))

    def test_court_after_the_date(self):
        for text, want in [
                ("a confirmé le jugement du 29 juin 1999 du tribunal administratif de Nice "
                 "rejetant la demande.",
                 ("TA", "1999-06-29", "jugement du 29 juin 1999 du tribunal administratif de "
                  "Nice")),
                ("confirmer le jugement rendu par le juge aux affaires familiales de [Localité 1] "
                 "le 15 décembre 2023.",
                 ("TJ", "2023-12-15", "juge aux affaires familiales de [Localité 1] le 15 "
                  "décembre 2023")),
                ("Par jugement du 8 juillet 2021, le tribunal de Lisieux a débouté M. [D].",
                 ("Tribunal", "2021-07-08", "jugement du 8 juillet 2021, le tribunal de "
                  "Lisieux"))]:
            self.assertEqual(self.read(text), [("decision", None) + want], text)

    def test_the_whole_citation_is_highlighted(self):
        for text, want in [
                ("Par un jugement n° 1908677/4 du 25 novembre 2022, le tribunal administratif de "
                 "Montreuil a annulé.",
                 "n° 1908677/4 du 25 novembre 2022, le tribunal administratif de Montreuil"),
                ("Article 1er : Le jugement du tribunal administratif de Toulon n° 2103189 du 28 "
                 "juin 2024 est annulé.",
                 "tribunal administratif de Toulon n° 2103189 du 28 juin 2024"),
                ("( Cass. Soc, 6 mai 2009 numéro 07 44 485)",
                 "Cass. Soc, 6 mai 2009 numéro 07 44 485"),
                ("(CEDH, arrêt du 15 mars 2012, Solomakhin c. Ukraine, n° 24429/03, § 33)",
                 "CEDH, arrêt du 15 mars 2012, Solomakhin c. Ukraine, n° 24429/03"),
                ("(CEDH, arrêt du 15 novembre 2016, Dubská et Krejzová, n° 28859/11, § 174)",
                 "CEDH, arrêt du 15 novembre 2016, Dubská et Krejzová, n° 28859/11"),
                # la formation coupée par un saut de ligne
                ("Mme X a formé un pourvoi contre l'arrêt rendu le 14 mai 2024 par la cour "
                 "d'appel de Pau (2e\nchambre, section 1), dans le litige.",
                 "arrêt rendu le 14 mai 2024 par la cour d'appel de Pau (2e\nchambre, section 1)"),
                # la cour écrite après le RG et sa date
                ("La société a formé un pourvoi contre un arrêt n° RG 23/07760 rendu le 28 "
                 "novembre 2024 par la cour d'appel de\nLyon (3e chambre A), dans le litige.",
                 "RG 23/07760 rendu le 28 novembre 2024 par la cour d'appel de\nLyon (3e "
                 "chambre A)")]:
            self.assertEqual(self.read(text)[0][4], want, text)

    def test_a_dated_repeat_of_a_numbered_decision(self):
        # Même cour, même ville, même date : une reprise. Une autre ville : rien, comme avant.
        text = ("La société a formé un pourvoi contre un arrêt n° RG 23/07760 rendu le 28 "
                "novembre 2024 par la cour d'appel de Lyon. Selon l'arrêt attaqué (Lyon, 28 "
                "novembre 2024), rendu sur renvoi. Selon l'arrêt attaqué (Paris, 28 novembre "
                "2024), rien.")
        found = extract(text, unverified=True, whole_texts=True)[0]
        self.assertEqual(len(found), 1)
        self.assertEqual([text[a:b] for a, b in found[0]["repeats"]],
                         ["arrêt attaqué (Lyon, 28 novembre 2024)"])

    def test_a_dated_local_plan_is_grey(self):
        self.assertEqual(self.read("les dispositions du plan local d'urbanisme approuvé le 10 "
                                   "avril 2015 s'opposaient.")[0][:3],
                         ("unverified", None, "Plan local d'urbanisme approuvé le 10 avril 2015"))

    def test_a_paragraph_between_article_and_law(self):
        self.assertEqual(self.read("Il résulte de l'article 14, I, B, de la loi n° 2021-1040 du "
                                   "5 août 2021.")[0][:3],
                         ("text_article", "14", "Loi n° 2021-1040 du 5 août 2021"))


if __name__ == "__main__":
    unittest.main()
