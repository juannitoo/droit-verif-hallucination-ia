"""France : jurisprudence administrative (ArianeWeb) et judiciaire (Judilibre : Cour de
cassation, cours d'appel, tribunaux judiciaires), articles
des codes et des conventions collectives (Légifrance).

LES TROIS RÈGLES
  1. Chaque base se prouve avant de juger. Des numéros réels doivent être trouvés, des
     numéros inventés ne doivent rien donner. Si une base rate ses contrôles, ses citations
     sortent en NOT_TESTED : aucun verdict.
  2. Jamais « introuvable ». ArianeWeb ne contient qu'une sélection de décisions : zéro
     résultat veut dire « non publiée ou non indexée ». C'est aussi la formule des
     tribunaux (« ne semblent pas correspondre à des décisions publiées »).
  3. Une base qu'on n'a pas pu interroger ne donne jamais un verdict négatif. Sinon un trou
     dans nos accès passerait pour une erreur de l'auteur du texte.

CE QU'ELLE NE VÉRIFIE PAS
  Que la décision dise ce qu'on lui fait dire. Aucune base ne le sait.
"""
from datetime import date

from . import sources
from .articles import check_articles
from .conventions import check_convention_articles
from .lower_courts import Courts, check_lower_courts
from .extract import extract
from .legifrance import Client, Unavailable
from .scope import not_checked_summary, scope
from ...locales import t

NAME = "France"
KEYS = {"PISTE_API_KEY": "Clé API PISTE (Judilibre)",
        "PISTE_CLIENT_ID": "Identifiant OAuth PISTE (Légifrance)",
        "PISTE_CLIENT_SECRET": "Secret OAuth PISTE (Légifrance)"}
KEY_HELP_URL = "https://piste.gouv.fr/"
NOISE_MAX = 3        # au-delà, un témoin négatif d'ArianeWeb est du bruit anormal

ADMIN_REAL = [("298348", "CE Ass. 30/10/2009 Perreux"),
              ("322326", "CE Ass. 11/04/2012 GISTI"),
              ("368082", "CE 21/03/2016 Sté Fairvesta")]
ADMIN_FAKE = [("999999", "numéro hors plage"),
              ("308851", "voisin d'un numéro réel"),
              ("308849", "voisin d'un numéro réel")]
JUDICIAL_REAL = [("13-11.789", "Cass. soc. 08/10/2014"),
                 ("12-18.273", "Cass. soc. 10/07/2013")]
# Pas de « 00-00.000 » : Judilibre a une vraie fiche sous ce numéro de remplissage.
JUDICIAL_FAKE = [("99-99.999", "pourvoi inventé"),
                 ("98-99.998", "pourvoi inventé")]
# (code Judilibre, RG, date) : décisions connues ; et des RG inventés.
LOWER_REAL = [("ca", "ca_paris", "11/18803", "2013-10-02"),
              ("tj", "tj24322", "25/00578", "2026-02-23")]
LOWER_FAKE = [("ca", "ca_paris", "99/99999"), ("tj", "tj24322", "99/99999")]
# (code, numéro, nombre minimal de versions) : des articles dont l'histoire est connue.
LEGI_REAL = [("Code du travail", "L3121-2", 2), ("Code civil", "1240", 2),
             ("Code du travail", "L122-14-4", 7)]
LEGI_FAKE = [("Code du travail", "L9999-99"), ("Code civil", "9999")]
# (IDCC, numéro, nombre minimal de versions) : HCR, article 21 remplacé le 13/07/2004.
KALI_REAL = [("1979", "21", 2)]
KALI_FAKE = ["9998"]

__all__ = ["NAME", "KEYS", "KEY_HELP_URL", "extract", "check", "scope",
           "not_checked_summary"]


def verdict_admin(count, dates, cited_date):
    """Traduit la réponse d'ArianeWeb. La date n'est dite conforme que si ArianeWeb a la
    décision ELLE-MÊME à cette date, pas seulement des décisions qui la citent."""
    if count < 0:
        return "ERROR", "ArianeWeb n'a pas répondu", None
    if count == 0:
        return ("NOT_PUBLISHED", "aucune occurrence dans ArianeWeb : non publiée, non indexée, "
                "ou inexistante ; à vérifier", None)
    if dates:
        actual = ", ".join(sorted(dates))
        if not cited_date:
            return "EXISTS_DATE_UNCHECKED", f"existe, rendue le {actual} ; aucune date citée", actual
        if cited_date in dates:
            return "CONFIRMED", "existe, à la date citée", cited_date
        return ("WRONG_DATE",
                f"le numéro existe, mais ArianeWeb date la décision du {actual}, pas du {cited_date}",
                actual)
    if count <= NOISE_MAX:
        return "DOUBTFUL", f"{count} occurrence(s) seulement, à regarder à la main", None
    return ("EXISTS_DATE_UNCHECKED", f"{count} décisions citent ce numéro, mais la décision "
            "elle-même n'est pas dans ArianeWeb : date NON contrôlée", None)


def verdict_judicial(record, cited_date, first_complete=None):
    """`first_complete` : première année où Judilibre publie largement la Cour de cassation
    (mesurée : 1987 au 29/09/2026 ; avant, 2 000 décisions par an contre 13 000 après)."""
    if record is None:
        if not cited_date or not first_complete or cited_date[:4] < first_complete:
            if not first_complete:
                period = "la couverture de Judilibre n'a pas pu être mesurée"
            elif not cited_date:
                period = "sans date citée, impossible de savoir si la période est couverte"
            else:
                period = (f"les arrêts de {cited_date[:4]} ne sont publiés qu'en partie "
                          f"(publication large depuis {first_complete})")
            return ("UNVERIFIABLE_PERIOD", f"aucun pourvoi de ce numéro dans Judilibre, mais "
                    f"{period} : l'absence ne prouve rien", None)
        return ("NOT_PUBLISHED", "aucun pourvoi de ce numéro dans Judilibre : la décision ne "
                "semble pas publiée ; à vérifier", None)
    if "_err" in record:
        return "ERROR", f"Judilibre n'a pas répondu ({record['_err']})", None
    actual = (record.get("decision_date") or "")[:10]
    ident = f"{record.get('chamber', '?')}, {record.get('solution', '?')}"
    if not cited_date:
        return "EXISTS_DATE_UNCHECKED", f"existe, rendu le {actual} ({ident}) ; aucune date citée", actual
    if actual == cited_date:
        return "CONFIRMED", f"existe, à la date citée ({ident})", actual
    return ("WRONG_DATE",
            f"le numéro existe, mais Judilibre date l'arrêt du {actual}, pas du {cited_date} "
            f"({ident})", actual)


def _line(ok, text):
    return f"  {'OK   ' if ok else 'ÉCHEC'} {text}"


def selftest_admin(log):
    ok = True
    for number, what in ADMIN_REAL:
        good = sources.ariane(number)[0] > NOISE_MAX
        ok &= good
        log(_line(good, f"ArianeWeb doit trouver {number} ({what})"))
    for number, what in ADMIN_FAKE:
        good = 0 <= sources.ariane(number)[0] <= NOISE_MAX
        ok &= good
        log(_line(good, f"ArianeWeb ne doit pas trouver {number} ({what})"))
    return ok


def selftest_judicial(key, log):
    ok = True
    for number, what in JUDICIAL_REAL:
        record = sources.judilibre(number, key)
        good = bool(record) and "_err" not in record
        ok &= good
        log(_line(good, f"Judilibre doit trouver {number} ({what})"))
        if record and "_err" in record:
            log(f"        {record['_err']}")
            return False
    for number, what in JUDICIAL_FAKE:
        good = sources.judilibre(number, key) is None
        ok &= good
        log(_line(good, f"Judilibre ne doit pas trouver {number} ({what})"))
    return ok


def selftest_lower(key, jurisdictions, log):
    ok = True
    for jurisdiction, location, number, day in LOWER_REAL:
        if jurisdiction not in jurisdictions:
            continue
        dates = sources.judilibre_rg(number, jurisdiction, location, key)
        good = isinstance(dates, list) and day in dates
        ok &= good
        log(_line(good, f"Judilibre doit trouver {location} RG {number} du {day}"))
    for jurisdiction, location, number in LOWER_FAKE:
        if jurisdiction not in jurisdictions:
            continue
        good = sources.judilibre_rg(number, jurisdiction, location, key) == []
        ok &= good
        log(_line(good, f"Judilibre ne doit pas trouver {location} RG {number}"))
    return ok


def selftest_legifrance(client, log, with_codes, with_conventions):
    ok = True
    try:
        if with_codes:
            codes = client.codes()
            for code, number, minimum in LEGI_REAL:
                good = (code in codes
                        and len(client.versions(code, codes[code], number)) >= minimum)
                ok &= good
                log(_line(good, f"Légifrance doit trouver {code}, article {number}"))
            for code, number in LEGI_FAKE:
                good = code in codes and client.versions(code, codes[code], number) == []
                ok &= good
                log(_line(good, f"Légifrance ne doit pas trouver {code}, article {number}"))
        if with_conventions:
            for idcc, number, minimum in KALI_REAL:
                conv = client.convention(idcc)
                found = [a for a in client.convention_articles(conv[1])
                         if a["num"] == number] if conv else []
                good = len(found) >= minimum
                ok &= good
                log(_line(good, f"Légifrance doit trouver IDCC {idcc}, article {number}"))
            for idcc in KALI_FAKE:
                good = client.convention(idcc) is None
                ok &= good
                log(_line(good, f"Légifrance ne doit pas trouver l'IDCC {idcc}"))
    except Unavailable as e:
        log(f"        {e}")
        return False
    return ok


LEGISLATION = ("article", "convention_article")


def _check_legislation(citations, keys, day, idcc, log):
    """Résultats (verdict, explication, date) pour les articles de codes et de conventions,
    dans l'ordre."""
    if not citations:
        return []
    cid, secret = keys.get("PISTE_CLIENT_ID"), keys.get("PISTE_CLIENT_SECRET")
    if not (cid and secret):
        log("Légifrance non interrogé : identifiant ou secret PISTE absent.")
        why = "identifiant ou secret PISTE absent : Légifrance n'a pas été interrogé"
        return [("NOT_TESTED", why, None)] * len(citations)
    client = Client(cid, secret)
    kinds = {c["kind"] for c in citations}
    log("Contrôle de Légifrance avant de juger :")
    if not selftest_legifrance(client, log, "article" in kinds, "convention_article" in kinds):
        why = "Légifrance n'a pas passé ses contrôles : aucun verdict possible"
        return [("NOT_TESTED", why, None)] * len(citations)
    codes = iter(check_articles([c for c in citations if c["kind"] == "article"],
                                client, day, log))
    conventions = iter(check_convention_articles(
        [c for c in citations if c["kind"] == "convention_article"], client, day, idcc))
    return [next(codes) if c["kind"] == "article" else next(conventions) for c in citations]


def check(citations, keys, log=lambda s: None, options=None):
    """Vérifie chaque citation. Renvoie un résultat par citation, dans l'ordre.

    `options` :
      reference_date  AAAA-MM-JJ, la date à laquelle les articles sont lus (défaut : jour)
      idcc            l'IDCC à utiliser pour une convention citée sans IDCC"""
    options = options or {}
    day = options.get("reference_date") or date.today().isoformat()
    legislation = iter(_check_legislation(
        [c for c in citations if c.get("kind") in LEGISLATION], keys, day,
        options.get("idcc"), log))
    orders = {c["order"] for c in citations if c.get("kind") not in LEGISLATION}
    admin_ok = judicial_ok = False
    admin_why = judicial_why = None
    lower_results = iter(())
    cc_first = None

    if "administrative" in orders:
        log("Contrôle d'ArianeWeb (Conseil d'État) avant de juger :")
        admin_ok = selftest_admin(log)
        if not admin_ok:
            admin_why = "ArianeWeb n'a pas passé ses contrôles : aucun verdict possible"
    if "judicial" in orders:
        key = keys.get("PISTE_API_KEY")
        if not key:
            judicial_why = "clé PISTE absente : Judilibre n'a pas été interrogé"
            log("Judilibre non interrogé : aucune clé PISTE.")
        else:
            log("Contrôle de Judilibre (Cour de cassation) avant de juger :")
            judicial_ok = selftest_judicial(key, log)
            if not judicial_ok:
                judicial_why = "Judilibre n'a pas passé ses contrôles : aucun verdict possible"
            else:
                try:
                    cc_first = Courts(key).first_complete_year("cc", None)[0]
                except Exception:
                    cc_first = None         # couverture non mesurée : « non vérifiable »
    if "lower" in orders:
        lower = [c for c in citations if c.get("order") == "lower"]
        key = keys.get("PISTE_API_KEY")
        if not key:
            log("Judilibre non interrogé : aucune clé PISTE.")
            why = "clé PISTE absente : Judilibre n'a pas été interrogé"
            lower_results = iter([("NOT_TESTED", why, None)] * len(lower))
        else:
            log("Contrôle de Judilibre (cours d'appel, tribunaux) avant de juger :")
            if selftest_lower(key, {c["jurisdiction"] for c in lower}, log):
                lower_results = iter(check_lower_courts(lower, Courts(key)))
            else:
                why = "Judilibre n'a pas passé ses contrôles : aucun verdict possible"
                lower_results = iter([("NOT_TESTED", why, None)] * len(lower))

    results = []
    log("Vérification des citations :")
    for c in citations:
        if c.get("kind") in LEGISLATION:
            v, why, actual = next(legislation)
        elif c["order"] == "lower":
            v, why, actual = next(lower_results)
        elif c["order"] == "administrative":
            if admin_ok:
                v, why, actual = verdict_admin(*sources.ariane(c["number"]), c.get("cited_date"))
            else:
                v, why, actual = "NOT_TESTED", admin_why, None
        elif judicial_ok:
            v, why, actual = verdict_judicial(
                sources.judilibre(c["number"], keys["PISTE_API_KEY"]), c.get("cited_date"),
                cc_first)
        else:
            v, why, actual = "NOT_TESTED", judicial_why, None
        results.append({**c, "verdict": v, "explanation": why, "actual_date": actual})
        log(f"  {c['court']} {'art.' if c.get('kind') in LEGISLATION else 'n°'} "
            f"{c['number']} : {t.VERDICTS[v]}")
    return results
