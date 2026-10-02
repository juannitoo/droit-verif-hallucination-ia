"""France : jurisprudence administrative (ArianeWeb) et judiciaire (Judilibre : Cour de
cassation, cours d'appel, tribunaux judiciaires), Conseil constitutionnel et Tribunal des
conflits (Légifrance), Cour de justice et Tribunal de l'Union européenne (CELLAR), articles
des codes et des conventions collectives (Légifrance). La CEDH n'autorise pas la recherche
par un programme : ses décisions sont signalées, avec le lien de la recherche.

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
import re
from datetime import date

from . import codes, decision_quotes, links, other_courts, piste, sources, wire
from .articles import check_articles
from .texts import check_text_articles, check_texts
from .conventions import check_convention_articles
from .lower_courts import Courts, check_lower_courts
from . import extract as _extract
from .legifrance import Client, Unavailable
from .scope import not_checked_summary, scope
from ... import ISSUES_URL
from ...locales import t

NAME = "France"
KEYS = {"PISTE_API_KEY": "Clé API PISTE (Judilibre)",
        "PISTE_CLIENT_ID": "Identifiant OAuth PISTE (Légifrance)",
        "PISTE_CLIENT_SECRET": "Secret OAuth PISTE (Légifrance)"}
KEY_HELP_URL = "https://piste.gouv.fr/"
# Réglages facultatifs, qui ne sont pas des clés : affichés en clair, rangés au même endroit.
LOCAL_BASE = "ADMIN_LOCAL_BASE_URL"
SETTINGS = {LOCAL_BASE: "Base locale des décisions administratives (facultatif)"}
SETTINGS_HELP = {LOCAL_BASE: (
    "Les tribunaux administratifs ne sont interrogeables par aucune base en ligne : leurs "
    "décisions ne sont publiées qu'en archives, sur opendata.justice-administrative.fr. Si "
    "une base locale a été installée à partir de ces archives, donnez ici son adresse "
    "(https://..., ou http://localhost:... si elle tourne sur cet ordinateur) : les "
    "décisions des TA, et celles des CAA absentes de Légifrance, y seront cherchées. Le "
    "format attendu est décrit dans la notice du programme. Avant chaque vérification, elle "
    "est essayée sur des décisions connues : cela montre qu'elle fonctionne, pas qu'elle dit "
    "vrai sur les autres. Ses réponses valent ce que vaut celui qui l'a installée.")}
SETTINGS_CHECK = {LOCAL_BASE: other_courts.local_base_problem}
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
# Tribunaux de commerce : un numéro à lettre (trouvé en listant le jour) et un tout en
# chiffres (trouvé aussi par la recherche) ; et des numéros inventés, le même jour.
TCOM_REAL = [("0101", "2025J05588", "2026-09-18"), ("6201", "2026004078", "2026-09-18")]
TCOM_FAKE = [("0101", "2025J99999", "2026-09-18"), ("6201", "2026009999", "2026-09-18")]
# (code, numéro, nombre minimal de versions) : des articles dont l'histoire est connue.
# L'article 1 du Code civil a 40 homonymes dans les autres codes : c'est lui qui trahit une
# recherche qui ne lit pas tout.
LEGI_REAL = [("Code du travail", "L3121-2", 2), ("Code civil", "1240", 2),
             ("Code du travail", "L122-14-4", 7), ("Code civil", "1", 2)]
LEGI_FAKE = [("Code du travail", "L9999-99"), ("Code civil", "9999")]
# (IDCC, numéro, nombre minimal de versions) : HCR, article 21 remplacé le 13/07/2004.
KALI_REAL = [("1979", "21", 2)]
KALI_FAKE = ["9998"]
# (numéro du texte, article, nombre minimal de versions) : loi de 1989 sur les baux, loi de
# 1965 sur la copropriété ; un article et un texte inventés.
LODA_REAL = [("89-462", "22", 4), ("65-557", "14", 3)]
LODA_FAKE = [("65-557", "999"), ("89-9999", "1")]
# (numéro, date) : décisions connues, et numéros inventés (vérifiés vides le 29/09/2026).
CONSTIT_REAL = [("2010-605", "2010-05-12"), ("2010-14/22", "2010-07-30")]
CONSTIT_FAKE = ["2010-9999", "2019-9999"]
# 00012 : Blanco, dont le numéro est aussi celui d'une décision du Conseil d'État de 1977.
CONFLICTS_REAL = [("C3911", "2013-06-17"), ("00012", "1873-02-08")]
CONFLICTS_FAKE = ["C9999", "C9998"]
CAA_REAL = [("17NC01414", "2018-04-12"), ("23MA02610", "2023-12-29")]
CAA_FAKE = ["17NC99999", "23MA99999"]
# Base locale : des CAA de décembre 2023, dans la période des archives (CAA depuis 03/2022).
LOCAL_REAL = [("CAA", "23MA02610", "2023-12-29"), ("CAA", "23PA00439", "2023-12-29")]
LOCAL_FAKE = [("CAA", "23MA99999"), ("TA", "2399999")]
EU_REAL = [("C-561/19", "2021-10-06"), ("C-311/18", "2020-07-16")]
EU_FAKE = ["C-999/19", "C-998/19"]
# Pour chaque juridiction : (nom de la base, recherche, témoins réels, témoins inventés,
# besoin des identifiants Légifrance).
OTHER_BASES = {
    "caa": ("Légifrance", other_courts.administrative_appeal, CAA_REAL, CAA_FAKE, True),
    "constitutional": ("Légifrance", other_courts.constitutional, CONSTIT_REAL, CONSTIT_FAKE,
                       True),
    "conflicts": ("Légifrance", other_courts.conflicts, CONFLICTS_REAL, CONFLICTS_FAKE, True),
    "eu": ("CELLAR (Office des publications de l'UE)",
           lambda client, number: other_courts.european_union(number), EU_REAL, EU_FAKE,
           False),
}

__all__ = ["NAME", "KEYS", "KEY_HELP_URL", "SETTINGS", "SETTINGS_HELP", "prepare", "extract", "check", "scope",
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
        link = links.link_for(dates, cited_date)
        if not cited_date:
            return ("EXISTS_DATE_UNCHECKED", f"existe, rendue le {actual} ; aucune date citée",
                    actual, link)
        if cited_date in dates:
            return "CONFIRMED", f"ArianeWeb a bien la décision du {cited_date}", cited_date, link
        return ("WRONG_DATE",
                f"le numéro existe, mais ArianeWeb date la décision du {actual}, pas du {cited_date}",
                actual, link)
    if count <= NOISE_MAX:
        return "DOUBTFUL", f"{count} occurrence(s) seulement, à regarder à la main", None
    return ("EXISTS_DATE_UNCHECKED", f"{count} décisions citent ce numéro, mais la décision "
            "elle-même n'est pas dans ArianeWeb : date NON contrôlée", None)


# Taxonomie « chamber » de Judilibre pour la Cour de cassation (relevée le 30/09/2026).
CHAMBERS = {"pl": "Assemblée plénière", "mi": "Chambre mixte", "civ1": "Première chambre civile",
            "civ2": "Deuxième chambre civile", "civ3": "Troisième chambre civile",
            "comm": "Chambre commerciale financière et économique", "soc": "Chambre sociale",
            "cr": "Chambre criminelle", "creun": "Chambres réunies"}
CHAMBER_CODES = {label.lower(): code for code, label in CHAMBERS.items()}


def chamber_mismatch(cited, record):
    """(chambre citée, chambre de Judilibre) si elles diffèrent, sinon None. « civ » (une
    chambre civile sans numéro) s'accorde avec n'importe laquelle des trois."""
    actual = CHAMBER_CODES.get((record.get("chamber") or "").strip().lower())
    if not cited or not actual or cited == actual:
        return None
    if cited == "civ" and actual.startswith("civ"):
        return None
    name = CHAMBERS[cited]
    said = "une chambre civile" if cited == "civ" else f"la {name[0].lower()}{name[1:]}"
    return said, record["chamber"]


def verdict_judicial(record, cited_date, first_complete=None, cited_chamber=None):
    """Voir plus bas ; puis la chambre : une vraie décision attribuée à la mauvaise chambre
    est une erreur typique d'une IA."""
    result = _verdict_judicial(record, cited_date, first_complete)
    if not record or "_err" in record:
        return result
    wrong = chamber_mismatch(cited_chamber, record)
    if not wrong:
        return result
    said, actual = wrong
    if result[0] == "WRONG_DATE":
        return (result[0], f"{result[1]} ; et la chambre aussi : {actual}, pas {said}",
                result[2], *result[3:])
    return ("WRONG_CHAMBER", f"existe, mais Judilibre l'attribue à la {actual.lower()}, pas à "
            f"{said}" + ("" if result[0] == "CONFIRMED" else " ; aucune date citée"),
            result[2], *result[3:])


def _verdict_judicial(record, cited_date, first_complete=None):
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
    ident = f"{_label(record.get('chamber'))}, {_label(record.get('solution'))}"
    link = links.judilibre(record.get("id"))
    if not cited_date:
        return ("EXISTS_DATE_UNCHECKED", f"existe, rendu le {actual} ({ident}) ; aucune date "
                "citée", actual, link)
    if actual == cited_date:
        return "CONFIRMED", f"Judilibre date bien l'arrêt du {actual} ({ident})", actual, link
    return ("WRONG_DATE",
            f"le numéro existe, mais Judilibre date l'arrêt du {actual}, pas du {cited_date} "
            f"({ident})", actual, link)


# Bases qui ne publient qu'une partie des décisions : une absence n'y prouve rien.
PARTIAL = {"caa": "introuvable dans Légifrance, qui ne publie qu'environ la moitié des "
                  "décisions des cours administratives d'appel : l'absence ne prouve rien ; "
                  "à vérifier"}


def verdict_dates(days, cited_date, base):
    """Traduit la liste des dates d'une base qui publie toutes ses décisions (Conseil
    constitutionnel, Tribunal des conflits, Union européenne). Si `days` porte des liens
    (links.Found), le verdict donne celui de la décision."""
    if not days:
        return ("NOT_PUBLISHED", f"aucune décision de ce numéro dans {base} : la décision ne "
                "semble pas publiée ; à vérifier", None)
    actual = ", ".join(days)
    link = links.link_for(days, cited_date)
    if not cited_date:
        return ("EXISTS_DATE_UNCHECKED", f"existe, rendue le {actual} ; aucune date citée",
                actual, link)
    if cited_date in days:
        return "CONFIRMED", f"{base} date bien la décision du {cited_date}", cited_date, link
    return ("WRONG_DATE", f"le numéro existe, mais {base} date la décision du {actual}, pas du "
            f"{cited_date}", actual, link)


# Juridictions repérées mais pas vérifiées, numéro ou non : la vraie raison, pour chacune.
NOT_YET = {
    "CAA": "décision d'une cour administrative d'appel citée sans son numéro (de la forme "
           "« 21BX01234 ») : aucune base n'a été interrogée",
    "TA": "décision d'un tribunal administratif : aucune base en ligne ne permet à un "
          "programme de les interroger (elles ne sont publiées qu'en archives à télécharger, "
          "sur opendata.justice-administrative.fr). Une base locale construite à partir de ces "
          "archives peut être déclarée dans l'onglet « Clés d'accès »",
    "CPH": "décision d'un conseil de prud'hommes : Judilibre ne les publie pas, aucune base "
           "n'a été interrogée",
}


def verdict_other(citation):
    """Une décision qu'aucune base interrogeable ne couvre : on la montre, on ne la juge pas.
    L'envoyer dans ArianeWeb donnerait un verdict sur une autre décision."""
    court, number = citation["court"], citation["number"]
    if court in NOT_YET:
        return "MANUAL_CHECK", NOT_YET[court], None
    if citation.get("order") == "unnumbered":
        return ("MANUAL_CHECK", "décision citée sans numéro. Ce programme ne cherche une "
                "décision que par son numéro : il n'envoie jamais le nom des parties, qui vient "
                "de votre document", None)
    if court == "CEDH" or "/" in number:
        what = ("décision de la CEDH" if court == "CEDH" else
                f"numéro au format « {number} », qui n'est pas celui du Conseil d'État mais "
                "celui des requêtes CEDH")
        return ("MANUAL_CHECK", f"{what}. La Cour européenne des droits de l'homme "
                "n'autorise pas la recherche dans sa base HUDOC par un programme : à vérifier "
                "dans votre navigateur, avec le lien de la recherche", None,
                other_courts.hudoc_link(number))
    return ("MANUAL_CHECK", f"décision de la juridiction « {court} » citée sous une forme que "
            "ce programme ne sait pas lire ; aucune base n'a été interrogée", None)


def _line(ok, text):
    return f"  {'OK   ' if ok else 'ÉCHEC'} {text}"


def _checked(base, selftest, log):
    """Les contrôles d'une base, sur ses références témoins, sans les afficher un par un :
    l'utilisateur n'a besoin que de savoir si la base fonctionne. Une seule ligne, et, en
    cas d'échec, le contrôle qui a échoué. `selftest` reçoit la fonction où écrire."""
    lines = []
    ok = selftest(lines.append)
    if ok:
        log(f"{base} : fonctionne correctement.")
        return True
    errors = [line.strip() for line in lines if line.startswith("        ")]
    failed = [re.sub(r"^.*?doit (?:pas )?(?:trouver|dire) ", "", line.split("ÉCHEC", 1)[1].strip())
              for line in lines if "ÉCHEC" in line]
    why = (f"ne répond pas ({errors[0]})" if errors
           else f"n'a pas fonctionné correctement pour {failed[0]}" if failed
           else "ne fonctionne pas correctement")
    log(f"{base} : {why} ; ses citations ne sont pas vérifiées.")
    return False


# La base interrogée pour chaque sorte de citation, pour dire laquelle a flanché en cours de
# route.
def _base_of(c):
    if c.get("kind") in LEGISLATION or c.get("order") in ("caa", "constitutional", "conflicts"):
        return "Légifrance"
    return {"judicial": "Judilibre", "lower": "Judilibre", "administrative": "ArianeWeb",
            "eu": "CELLAR", "ta": "La base locale"}.get(c.get("order"), "La base")


def selftest_other(base, search, real, fake, client, log):
    """Les témoins d'une base : ses décisions connues, à leur date, et des numéros inventés
    qui ne doivent rien donner."""
    ok = True
    try:
        for number, day in real:
            good = day in search(client, number)
            ok &= good
            log(_line(good, f"{base} doit trouver {number} du {day}"))
        for number in fake:
            good = search(client, number) == []
            ok &= good
            log(_line(good, f"{base} ne doit pas trouver {number}"))
    except Unavailable as e:
        log(f"        {e}")
        return False
    return ok


def selftest_local(local, log):
    ok = True
    try:
        for court in ("CAA", "TA"):
            good = local.coverage(court) is not None
            ok &= good
            log(_line(good, f"La base locale doit dire depuis quand elle couvre les {court}"))
        for court, number, day in LOCAL_REAL:
            good = day in local.decisions(court, number)
            ok &= good
            log(_line(good, f"La base locale doit trouver {court} n° {number} du {day}"))
        for court, number in LOCAL_FAKE:
            good = local.decisions(court, number) == []
            ok &= good
            log(_line(good, f"La base locale ne doit pas trouver {court} n° {number}"))
    except Unavailable as e:
        log(f"        {e}")
        return False
    return ok


def verdict_local(local, court, citation, fallback):
    """Une décision de CAA absente de Légifrance, ou de TA, cherchée dans la base locale.
    `fallback` : le verdict si la base locale ne permet pas de conclure."""
    number, cited = citation["number"], citation.get("cited_date")
    try:
        days = local.decisions(court, number)
        start = local.coverage(court)
    except Unavailable as e:
        return "ERROR", f"la base locale n'a pas répondu ({e})", None
    if days:
        return verdict_dates(days, cited, "la base locale")
    recent = cited and (date.today() - date.fromisoformat(cited)).days < 183
    if cited and start and cited >= start and not recent:
        return ("NOT_PUBLISHED", f"aucune décision sous ce numéro dans la base locale, qui "
                f"couvre les {court} depuis le {start} : la décision ne semble pas publiée ; "
                "à vérifier", None)
    why = (f"la base locale ne couvre les {court} que depuis le {start}" if start and cited
           and cited < start else "la décision a moins de six mois" if recent
           else "aucune date citée")
    return ("UNVERIFIABLE_PERIOD", f"{fallback[1]} ; absente aussi de la base locale, mais "
            f"{why} : l'absence ne prouve rien", None)


def _local_base(citations, keys, log):
    """La base locale, si l'utilisateur en a déclaré une ET qu'elle a passé ses témoins."""
    url = keys.get(LOCAL_BASE)
    if not url or not any(c.get("order") in ("caa", "ta") for c in citations):
        return None
    try:
        local = other_courts.LocalBase(url)
    except Unavailable as e:
        log(f"Base locale ignorée : {e}")
        return None
    ok = _checked("La base locale", lambda out: selftest_local(local, out), log)
    return local if ok else None


def _check_other(citations, keys, log):
    """Résultats pour le Conseil constitutionnel, le Tribunal des conflits et l'Union
    européenne, dans l'ordre. Les bases sont contrôlées tout de suite ; les citations se
    vérifient à la demande, une à une."""
    ready, client = {}, None       # juridiction -> (base, recherche), ou pourquoi pas
    for order in OTHER_BASES:
        mine = [c for c in citations if c["order"] == order]
        if not mine:
            continue
        base, search, real, fake, needs_keys = OTHER_BASES[order]
        if needs_keys:
            cid, secret = keys.get("PISTE_CLIENT_ID"), keys.get("PISTE_CLIENT_SECRET")
            if not (cid and secret):
                ready[order] = ("identifiant ou secret PISTE absent : Légifrance n'a pas été "
                                "interrogé")
                continue
            client = client or Client(cid, secret)
        name = f"{base.split(' (')[0]} ({mine[0]['court']})"   # « CELLAR (CJUE) »
        if _checked(name, lambda out: selftest_other(base, search, real, fake, client, out),
                    log):
            ready[order] = (base, search)
        else:
            ready[order] = f"{base} n'a pas passé ses contrôles : aucun verdict possible"

    def one(c):
        state = ready[c["order"]]
        if isinstance(state, str):
            return "NOT_TESTED", state, None
        base, search = state
        try:
            days = search(client, c["number"])
        except Unavailable as e:
            return "ERROR", f"{base} n'a pas répondu ({e})", None
        if c["order"] in PARTIAL and not days:
            return "UNVERIFIABLE_PERIOD", PARTIAL[c["order"]], None
        return verdict_dates(days, c.get("cited_date"), base)
    return (one(c) for c in citations)


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
    if "tcom" in jurisdictions:
        for location, number, day in TCOM_REAL:
            good = sources.judilibre_on_day(number, "tcom", location, day, key) == [day]
            ok &= good
            log(_line(good, f"Judilibre doit trouver le tribunal de commerce {location}, "
                            f"n° {number} du {day}"))
        for location, number, day in TCOM_FAKE:
            good = sources.judilibre_on_day(number, "tcom", location, day, key) == []
            ok &= good
            log(_line(good, f"Judilibre ne doit pas trouver le tribunal de commerce "
                            f"{location}, n° {number}"))
    return ok


def selftest_legifrance(client, log, with_codes, with_conventions, with_texts=False):
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
        if with_texts:
            for text_number, number, minimum in LODA_REAL:
                found = client.texts_by_number(text_number)
                good = (len(found) == 1 and len(client.text_article_versions(
                    text_number, found[0][0], number)) >= minimum)
                ok &= good
                log(_line(good, f"Légifrance doit trouver l'article {number} du texte n° "
                                f"{text_number}"))
            for text_number, number in LODA_FAKE:
                found = client.texts_by_number(text_number)
                good = not found or client.text_article_versions(
                    text_number, found[0][0], number) == []
                ok &= good
                log(_line(good, f"Légifrance ne doit pas trouver l'article {number} du texte "
                                f"n° {text_number}"))
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


LEGISLATION = ("article", "convention_article", "text_article", "text")


def _check_legislation(citations, keys, day, idcc, log):
    """Résultats (verdict, explication, date[, lien]) pour les articles de codes, de lois et
    de conventions, dans l'ordre."""
    if not citations:
        return []
    cid, secret = keys.get("PISTE_CLIENT_ID"), keys.get("PISTE_CLIENT_SECRET")
    if not (cid and secret):
        log("Légifrance non interrogé : identifiant ou secret PISTE absent.")
        why = "identifiant ou secret PISTE absent : Légifrance n'a pas été interrogé"
        return [("NOT_TESTED", why, None)] * len(citations)
    client = Client(cid, secret)
    kinds = {c["kind"] for c in citations}
    if not _checked("Légifrance", lambda out: selftest_legifrance(
            client, out, "article" in kinds, "convention_article" in kinds,
            bool(kinds & {"text_article", "text"})), log):
        why = "Légifrance n'a pas passé ses contrôles : aucun verdict possible"
        return [("NOT_TESTED", why, None)] * len(citations)
    codes = iter(check_articles([c for c in citations if c["kind"] == "article"],
                                client, day, log))
    conventions = iter(check_convention_articles(
        [c for c in citations if c["kind"] == "convention_article"], client, day, idcc))
    laws = iter(check_text_articles(
        [c for c in citations if c["kind"] == "text_article"], client, day))
    whole = iter(check_texts([c for c in citations if c["kind"] == "text"], client, day))
    kinds = {"article": codes, "convention_article": conventions, "text_article": laws,
             "text": whole}
    # Les contrôles sont faits ; les citations, elles, se vérifient à la demande.
    return (next(kinds[c["kind"]]) for c in citations)


def _label(value, limit=60):
    """Un libellé renvoyé par une base (chambre, solution), tel qu'il entre dans une
    explication : une ligne, courte. Plus long, ou sur plusieurs lignes, ce n'est plus un
    libellé, et il pourrait passer pour une ligne du rapport (audit du 01/10/2026)."""
    text = " ".join(str(value or "?").split())
    return text if len(text) <= limit else text[:limit] + "..."


def prepare(keys, log=lambda s: None):
    """Avant l'extraction : complète la liste des codes par celle de Légifrance, pour qu'un
    code créé après cette version soit repéré dans le texte. Sans identifiants ou si
    Légifrance ne répond pas, on garde la liste embarquée, sans rien bloquer.

    Renvoie les remarques du rapport. Personne n'assure la veille de ce programme gratuit :
    c'est l'utilisateur qui voit le nouveau code, c'est donc lui qu'on invite à le signaler."""
    cid, secret = keys.get("PISTE_CLIENT_ID"), keys.get("PISTE_CLIENT_SECRET")
    if not (cid and secret):
        return []
    try:
        new = codes.learn(Client(cid, secret).codes())
    except Exception:           # Unavailable, ou une réponse d'une forme inattendue
        return []
    if not new:
        return []
    log(f"{len(new)} code(s) ajouté(s) depuis Légifrance : {', '.join(new)}")
    return [f"Légifrance connaît {len(new)} code(s) que cette version du programme ne "
            f"connaissait pas : {', '.join(new)}. Ils sont reconnus sous leur titre complet, "
            "pas encore sous leur abréviation. Ce programme est gratuit et personne n'en "
            f"assure la veille : merci de le signaler sur {ISSUES_URL}, ou de proposer la "
            "correction (pull request)."]


def extract(text):
    """Les citations du document, avec ce qui est relevé sans pouvoir être vérifié : le
    rapport et le PDF annoté le montrent en gris."""
    return _extract.extract(text, unverified=True, whole_texts=True)


def check(citations, keys, log=lambda s: None, options=None):
    """Vérifie chaque citation. Renvoie un résultat par citation, dans l'ordre.

    Une citation dont un champ n'a pas la forme que l'extracteur produit n'est envoyée à
    aucune base : elle sort NOT_TESTED, avec la raison (wire.py).

    `options` :
      reference_date  AAAA-MM-JJ, la date à laquelle les articles sont lus (défaut : jour)
      idcc            l'IDCC à utiliser pour une convention citée sans IDCC"""
    piste.reset()
    # Relevé sans être vérifiable (code incertain, RG sans juridiction) : rien n'est envoyé.
    refused = [c.get("reason") or "non vérifié" if c.get("kind") == "unverified"
               else wire.refusal(c) for c in citations]
    checked = iter(_check([c for c, why in zip(citations, refused) if not why], keys, log,
                          options))
    results = []
    for c, why in zip(citations, refused):
        if why:
            if c.get("kind") != "unverified":
                log(f"  {str(c.get('number'))[:40]!r} : {why}")
            results.append({**c, "verdict": "NOT_TESTED", "explanation": why,
                            "actual_date": None, "link": None})
        else:
            results.append(next(checked))
    return results


def _check(citations, keys, log, options):
    options = options or {}
    if options.get("idcc") is not None and not re.fullmatch(r"\d{1,4}", str(options["idcc"])):
        options = {**options, "idcc": None}     # pas un IDCC : rien n'est envoyé à sa place
    day = options.get("reference_date") or date.today().isoformat()
    legislation = iter(_check_legislation(
        [c for c in citations if c.get("kind") in LEGISLATION], keys, day,
        options.get("idcc"), log))
    others = [c for c in citations if c.get("order") in OTHER_BASES]
    other_results = iter(_check_other(others, keys, log))
    local = _local_base(citations, keys, log)
    orders = {c["order"] for c in citations if c.get("kind") not in LEGISLATION}
    admin_ok = judicial_ok = False
    admin_why = judicial_why = None
    lower_results = iter(())
    cc_first = None

    if "administrative" in orders:
        admin_ok = _checked("ArianeWeb (Conseil d'État)", selftest_admin, log)
        if not admin_ok:
            admin_why = "ArianeWeb n'a pas passé ses contrôles : aucun verdict possible"
    if "judicial" in orders:
        key = keys.get("PISTE_API_KEY")
        if not key:
            judicial_why = "clé PISTE absente : Judilibre n'a pas été interrogé"
            log("Judilibre non interrogé : aucune clé PISTE.")
        else:
            judicial_ok = _checked("Judilibre (Cour de cassation)",
                                   lambda out: selftest_judicial(key, out), log)
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
            if _checked("Judilibre (cours d'appel, tribunaux)", lambda out: selftest_lower(
                    key, {c["jurisdiction"] for c in lower}, out), log):
                lower_results = iter(check_lower_courts(lower, Courts(key)))
            else:
                why = "Judilibre n'a pas passé ses contrôles : aucun verdict possible"
                lower_results = iter([("NOT_TESTED", why, None)] * len(lower))

    # Pour lire le texte des décisions de Légifrance cité entre guillemets.
    cid, secret = keys.get("PISTE_CLIENT_ID"), keys.get("PISTE_CLIENT_SECRET")
    legifrance = Client(cid, secret) if cid and secret else None
    results = []
    log("Vérification des citations :")
    stopped = False                 # « PISTE a limité les requêtes » : dit une seule fois
    for n, c in enumerate(citations, 1):
        # Un verdict : (verdict, explication, date réelle), et le lien de ce qui a été
        # trouvé quand il y en a un.
        if c.get("kind") in LEGISLATION:
            found = next(legislation)
        elif c["order"] in OTHER_BASES:
            found = next(other_results)
            if c["order"] == "caa" and found[0] == "UNVERIFIABLE_PERIOD" and local:
                found = verdict_local(local, "CAA", c, found[:2])
        elif c["order"] == "ta" and local:
            found = verdict_local(local, "TA", c, (
                "UNVERIFIABLE_PERIOD", "décision d'un tribunal administratif"))
        elif c["order"] == "ta":
            found = verdict_other(c)
        elif c["order"] in ("other", "unnumbered"):
            found = verdict_other(c)
        elif c["order"] == "lower":
            found = next(lower_results)
        elif c["order"] == "administrative":
            if admin_ok:
                found = verdict_admin(*sources.ariane(c["number"]), c.get("cited_date"))
            else:
                found = "NOT_TESTED", admin_why, None
        elif judicial_ok:
            found = verdict_judicial(
                sources.judilibre(c["number"], keys["PISTE_API_KEY"]), c.get("cited_date"),
                cc_first, c.get("chamber"))
        else:
            found = "NOT_TESTED", judicial_why, None
        if c.get("kind") not in LEGISLATION:
            found = decision_quotes.check(c, found, keys, legifrance)
        v, why, actual, *link = found
        if v == "ERROR" and piste.limited() and _base_of(c) in ("Légifrance", "Judilibre"):
            if not stopped:
                log(f"{piste.LIMITED} : les citations suivantes de Légifrance et de Judilibre "
                    "ne sont pas vérifiées.")
                stopped = True
        elif v == "ERROR":
            # La base a répondu à ses contrôles, puis a flanché sur cette citation.
            from ...report import citation_label
            log(f"{_base_of(c)} : n'a pas fonctionné correctement pour "
                f"{citation_label(c)}.")
        results.append({**c, "verdict": v, "explanation": why, "actual_date": actual,
                        "link": link[0] if link else None})
        step = f"  [{n}/{len(citations)}]"
        if c.get("kind") == "text":
            log(f"{step} {c['court']} : {t.VERDICTS[v]}")
        elif c.get("number") is None:
            log(f"{step} {c['court']}, {c.get('cited_date')}, sans numéro : {t.VERDICTS[v]}")
        else:
            log(f"{step} {c['court']} {'art.' if c.get('kind') in LEGISLATION else 'n°'} "
                f"{c['number']} : {t.VERDICTS[v]}")
    return results
