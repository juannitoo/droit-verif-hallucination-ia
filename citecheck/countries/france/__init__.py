"""France : jurisprudence administrative (ArianeWeb) et judiciaire (Judilibre).

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
from . import sources
from .extract import extract
from ...locales import t

NAME = "France"
KEYS = {"PISTE_API_KEY": "Clé API PISTE (Judilibre)"}
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

__all__ = ["NAME", "KEYS", "KEY_HELP_URL", "extract", "check"]


def verdict_admin(count, dates, cited_date):
    """Traduit la réponse d'ArianeWeb. La date n'est dite conforme que si ArianeWeb a la
    décision ELLE-MÊME à cette date, pas seulement des décisions qui la citent."""
    if count < 0:
        return "ERROR", "ArianeWeb n'a pas répondu", None
    if count == 0:
        return "NOT_PUBLISHED", "aucune occurrence dans ArianeWeb : non publiée ou non indexée", None
    if dates:
        actual = ", ".join(sorted(dates))
        if not cited_date:
            return "EXISTS_DATE_UNCHECKED", f"existe, rendue le {actual} ; aucune date citée", actual
        if cited_date in dates:
            return "CONFIRMED", "existe, date conforme", cited_date
        return ("WRONG_DATE",
                f"le numéro EXISTE mais la décision est du {actual}, pas du {cited_date}", actual)
    if count <= NOISE_MAX:
        return "DOUBTFUL", f"{count} occurrence(s) seulement, à regarder à la main", None
    return ("EXISTS_DATE_UNCHECKED", f"{count} décisions citent ce numéro, mais la décision "
            "elle-même n'est pas dans ArianeWeb : date NON contrôlée", None)


def verdict_judicial(record, cited_date):
    if record is None:
        return "NOT_PUBLISHED", "aucun pourvoi de ce numéro dans Judilibre", None
    if "_err" in record:
        return "ERROR", f"Judilibre n'a pas répondu ({record['_err']})", None
    actual = (record.get("decision_date") or "")[:10]
    ident = f"{record.get('chamber', '?')}, {record.get('solution', '?')}"
    if not cited_date:
        return "EXISTS_DATE_UNCHECKED", f"existe, rendu le {actual} ({ident}) ; aucune date citée", actual
    if actual == cited_date:
        return "CONFIRMED", f"existe, date conforme ({ident})", actual
    return ("WRONG_DATE",
            f"le numéro EXISTE mais l'arrêt est du {actual}, pas du {cited_date} ({ident})", actual)


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


def check(citations, keys, log=lambda s: None):
    """Vérifie chaque citation. Renvoie un résultat par citation, dans l'ordre."""
    orders = {c["order"] for c in citations}
    admin_ok = judicial_ok = False
    admin_why = judicial_why = None

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

    results = []
    log("Vérification des citations :")
    for c in citations:
        if c["order"] == "administrative":
            if admin_ok:
                v, why, actual = verdict_admin(*sources.ariane(c["number"]), c.get("cited_date"))
            else:
                v, why, actual = "NOT_TESTED", admin_why, None
        elif judicial_ok:
            v, why, actual = verdict_judicial(
                sources.judilibre(c["number"], keys["PISTE_API_KEY"]), c.get("cited_date"))
        else:
            v, why, actual = "NOT_TESTED", judicial_why, None
        results.append({**c, "verdict": v, "explanation": why, "actual_date": actual})
        log(f"  {c['court']} n° {c['number']} : {t.VERDICTS[v]}")
    return results
