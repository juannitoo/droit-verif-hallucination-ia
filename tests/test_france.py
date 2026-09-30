"""Offline tests: extraction, verdicts, report. The network is tested with
`python -m citecheck --case cases/perigueux.json`."""
import json
import unittest
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


class AmbiguousCode(unittest.TestCase):
    V = [{"id": "x", "etat": "VIGUEUR", "debut": "2011-03-01", "fin": "2999-01-01"}]

    def check(self, new, old):
        client = FakeLegifrance({"Code minier (nouveau)": new, "Code minier": old})
        return check_article(client, {"code": "Code minier", "number": "L111-1"},
                             "2026-09-30", {})

    def test_found_in_one_says_which(self):
        verdict, why, *_ = self.check({"L111-1": self.V}, {})
        self.assertEqual(verdict, "ARTICLE_IN_FORCE")
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
        self.assertEqual(verdict, "ARTICLE_IN_FORCE")
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
            self.assertEqual(target.name, "conclusions-citations-vérifiées.pdf")
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
            "par les articles 655 et 656 du code de procédure civile.")
    LINK = "https://www.courdecassation.fr/decision/658401878704660008a2970f"

    def check(self, quote, verdict="CONFIRMED"):
        from unittest import mock
        from citecheck.countries.france import decision_quotes
        with mock.patch.object(decision_quotes, "judilibre_text", return_value=self.TEXT) as t:
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

    def test_the_passage_after_a_decision_is_attached_to_it(self):
        cits, _ = extract("Cass. 2e civ., 21 décembre 2023, n° 22-18.480 : « L'huissier de "
                          "justice n'a pas laissé l'avis de passage prévu par la loi ».")
        self.assertEqual(cits[0]["quote"], "L'huissier de justice n'a pas laissé l'avis de "
                                           "passage prévu par la loi")


if __name__ == "__main__":
    unittest.main()
