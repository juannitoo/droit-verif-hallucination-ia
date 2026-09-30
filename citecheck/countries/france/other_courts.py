"""Cours administratives d'appel, Conseil constitutionnel et Tribunal des conflits
(Légifrance), Cour de justice et
Tribunal de l'Union européenne (CELLAR), et la CEDH, qu'on ne peut pas interroger.

CE QU'ON A APPRIS (sonde du 29/09/2026 au soir, numéros réels et inventés)
  - Conseil constitutionnel : Légifrance, fonds CONSTIT, champ NUM_DEC, numéro sans son
    suffixe (« 2010-605 », « 2010-14/22 »). Le titre porte le numéro et la date.
  - Tribunal des conflits : Légifrance, fonds CETAT, le même que le Conseil d'État. Le
    numéro de Blanco, 00012, y désigne AUSSI une décision du Conseil d'État de 1977 : on ne
    garde que les titres qui commencent par « Tribunal des conflits ». Les numéros récents
    s'écrivent « C3911 » ; « 3911 » seul ne trouve rien, on cherche donc les deux formes.
  - Cours administratives d'appel : Légifrance, fonds CETAT, champ NUM_DEC (« 17NC01414 »).
    Légifrance n'en publie qu'une PARTIE : 13 000 à 17 000 décisions par an depuis 2008 au
    moins, environ la moitié de ce que rendent les CAA. Une décision trouvée se vérifie ;
    une absence ne prouve rien. Les titres commencent par « CAA de » depuis 2014-2016, par
    « Cour administrative d'appel » avant.
  - Tribunaux administratifs : AUCUN dans Légifrance. Toutes leurs décisions (et celles des
    CAA) sont sur opendata.justice-administrative.fr depuis 2022, mais en archives ZIP
    mensuelles seulement : ses conditions d'utilisation disent « Le site de données ouvertes
    ne comporte pas d'API » (article XI). La page de recherche du site a une interface
    interne : s'en servir serait contourner ce choix. On ne le fait pas.
  - Union européenne : CELLAR, le dépôt de l'Office des publications de l'UE, public et
    fait pour les programmes, sans clé. On y cherche le numéro CELEX : « C-561/19 »
    devient 62019CJ0561 (CJ arrêt, CO ordonnance, CV avis ; TJ et TO pour le Tribunal).
    Par son API REST : /resource/celex/<numéro> répond 404 si le numéro n'existe pas, et
    sinon renvoie (303) vers la fiche de la décision, qui porte sa date. 0,1 à 2 secondes.
    PAS par son point d'accès SPARQL : mesuré le 29/09/2026, le même numéro y répond en
    0,1 s, puis en 44 s, puis pas du tout en 120 s, ou en erreur 504. Deux bancs d'essai
    sur cinq tombaient en « non vérifié ».
  - CEDH : HUDOC est derrière un défi Cloudflare (HTTP 403, « cf-mitigated: challenge »),
    sur sa recherche comme sur son robots.txt. La Cour n'autorise donc pas la recherche par
    un programme, et on ne la contourne pas. On donne à l'avocat le lien de la recherche,
    qu'il ouvre dans son navigateur.

Seul le numéro de la décision part sur le réseau. Jamais le texte du document.
"""
import ipaddress
import json
import re
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

from ...reader import Suspicious, parse_xml
from .extract import RE_DATE_DIGITS, RE_DATE_WORDS, _iso
from .legifrance import USER_AGENT, Unavailable
from ...http import urlopen

CELLAR = "https://publications.europa.eu"
MAX_NOTICE = 5_000_000      # une fiche d'arrêt pèse 130 à 200 Ko
HUDOC = "https://hudoc.echr.coe.int/fre#"
TIMEOUT = 40
EU_KINDS = {"C": ("CJ", "CO", "CV"), "T": ("TJ", "TO")}


def _title_date(title):
    m = RE_DATE_WORDS.search(title)
    if m:
        return _iso(m)
    m = RE_DATE_DIGITS.search(title)
    return _iso(m, False) if m else None


def constitutional(client, number):
    """Les dates des décisions du Conseil constitutionnel portant ce numéro (sans suffixe),
    triées ; liste vide si aucune. Lève Unavailable si Légifrance ne répond pas."""
    pattern = re.compile(rf"^Décision {re.escape(number)}\s", re.I)
    return sorted({_title_date(t) for t in client.decision_titles("CONSTIT", number)
                   if pattern.match(t)} - {None})


def conflicts(client, number):
    """Les dates des décisions du Tribunal des conflits portant ce numéro. « 4112 » est
    cherché aussi sous « C4112 », la forme de Légifrance pour les numéros récents."""
    number = number.replace(" ", "").upper()
    forms = [number] + ([f"C{number}"] if re.fullmatch(r"\d{4}", number) else [])
    days = set()
    for form in forms:
        pattern = re.compile(rf",\s*{re.escape(form)}\s*,")
        for title in client.decision_titles("CETAT", form):
            if title.lower().startswith("tribunal des conflits") and pattern.search(title):
                days.add(_title_date(title))
    return sorted(days - {None})


def administrative_appeal(client, number):
    """Les dates des décisions de cour administrative d'appel portant ce numéro."""
    pattern = re.compile(rf",\s*{re.escape(number)}\s*(?:,|$)")
    return sorted({_title_date(t) for t in client.decision_titles("CETAT", number)
                   if re.match(r"(?:CAA|Cour administrative d'appel)\b", t, re.I)
                   and pattern.search(t)} - {None})


class LocalBase:
    """Une base locale des décisions administratives, installée par l'utilisateur à partir
    des archives de opendata.justice-administrative.fr (CAA depuis 03/2022, TA depuis
    06/2022). Aucun logiciel standard ne le fait : ce programme fixe le contrat, que la base
    doit respecter (détail dans la notice) :

      GET <adresse>/coverage
          -> {"CAA": "2022-03-01", "TA": "2022-06-01"}   première date couverte en entier
      GET <adresse>/decisions?court=TA&number=2301234
          -> {"decisions": [{"number": "2301234", "date": "2023-05-12"}]}

    Seuls partent le type de juridiction et le numéro, jamais le texte du document. Comme
    toute base, elle passe ses témoins avant de juger."""

    def __init__(self, url):
        url = (url or "").strip().rstrip("/")
        problem = local_base_problem(url)
        if problem:
            raise Unavailable(f"adresse de la base locale refusée : {problem}")
        self.url = url
        self._coverage = None

    def _get(self, route, params=None):
        query = "?" + urllib.parse.urlencode(params) if params else ""
        req = urllib.request.Request(f"{self.url}/{route}{query}", headers={
            "User-Agent": USER_AGENT, "Accept": "application/json"})
        try:
            with urlopen(req, timeout=TIMEOUT) as r:
                return json.loads(r.read(MAX_NOTICE).decode("utf-8", "replace"))
        except urllib.error.HTTPError as e:
            raise Unavailable(f"base locale : HTTP {e.code}", e.code)
        except Exception as e:
            raise Unavailable(f"base locale : {type(e).__name__}")

    def coverage(self, court):
        """Première date couverte en entier pour ce type de juridiction, ou None."""
        if self._coverage is None:
            data = self._get("coverage")
            self._coverage = data if isinstance(data, dict) else {}
        day = str(self._coverage.get(court) or "")[:10]
        return day if re.fullmatch(r"\d{4}-\d{2}-\d{2}", day) else None

    def decisions(self, court, number):
        data = self._get("decisions", {"court": court, "number": number})
        found = data.get("decisions") if isinstance(data, dict) else None
        if not isinstance(found, list):
            raise Unavailable("base locale : réponse d'une forme inattendue")
        return sorted({str(d.get("date") or "")[:10] for d in found
                       if isinstance(d, dict) and str(d.get("number")) == number
                       and re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(d.get("date") or "")[:10])})


def celex_numbers(number):
    """« C-561/19 » -> les numéros CELEX possibles : arrêt, ordonnance, avis."""
    m = re.fullmatch(r"([CT])-(\d{1,4})/(\d{2})", number)
    if not m:
        return []
    court, n, yy = m.group(1), int(m.group(2)), int(m.group(3))
    year = 1900 + yy if yy >= 50 else 2000 + yy
    return [f"6{year}{kind}{n:04d}" for kind in EU_KINDS[court]]


def european_union(number):
    """Les dates des décisions de la Cour de justice ou du Tribunal de l'UE portant ce
    numéro (« C-561/19 »), triées ; liste vide si aucune."""
    days = set()
    for celex in celex_numbers(number):
        days |= _celex_dates(celex)
    return sorted(days)


def local_base_problem(url):
    """None si l'adresse de la base locale est acceptable ; sinon, pourquoi.

    Vérifié à l'enregistrement ET à chaque lecture : une variable d'environnement gagne sur
    le trousseau et ne passe pas par la fenêtre (audit du 30/09/2026, point 3). Les numéros
    des requêtes ne circulent en clair que sur cet ordinateur ; ailleurs, https. Pas
    d'identifiant dans l'adresse, où il finirait dans les journaux, et pas d'adresse
    lien-local (169.254.x.x : les métadonnées des machines de cloud)."""
    try:
        u = urllib.parse.urlsplit((url or "").strip())
        u.port                                       # un port illisible lève ValueError
    except ValueError:
        return "adresse illisible"
    host = u.hostname or ""
    if u.scheme not in ("http", "https") or not host:
        return "l'adresse doit commencer par https://"
    if u.username or u.password:
        return "pas d'identifiant ni de mot de passe dans l'adresse"
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        ip = None
    if host.lower() == "localhost" or (ip and ip.is_loopback):
        return None
    if u.scheme != "https":
        return ("hors de cet ordinateur, l'adresse doit être en https:// : en http, les "
                "numéros des requêtes circuleraient en clair sur le réseau")
    if ip and (ip.is_link_local or ip.is_multicast or ip.is_unspecified or ip.is_reserved):
        return "adresse réseau réservée, refusée"
    return None


def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT,
                                               "Accept": "application/xml;notice=object"})
    with urlopen(req, timeout=TIMEOUT) as r:
        return r.read(MAX_NOTICE + 1)


def _celex_dates(celex):
    """La date de la décision CELEX, dans un ensemble ; vide si le numéro n'existe pas."""
    try:
        _get(f"{CELLAR}/resource/celex/{celex}")
        raise Unavailable("CELLAR n'a pas renvoyé vers la fiche")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return set()
        if e.code != 303:
            raise Unavailable(f"HTTP {e.code}", e.code)
        location = e.headers.get("Location") or ""
    except Unavailable:
        raise
    except Exception as e:
        raise Unavailable(type(e).__name__)
    # La redirection est suivie à la main, et seulement vers une fiche du même dépôt, en
    # https : http.py refuse toute redirection, par principe.
    path = urllib.parse.urlsplit(location)
    if path.hostname != "publications.europa.eu" or not path.path.startswith("/resource/cellar/"):
        raise Unavailable(f"redirection inattendue de CELLAR : {location[:80]}")
    try:
        body = _get(CELLAR + path.path + ("?" + path.query if path.query else ""))
    except urllib.error.HTTPError as e:
        raise Unavailable(f"HTTP {e.code}", e.code)
    except Exception as e:
        raise Unavailable(type(e).__name__)
    if len(body) > MAX_NOTICE:
        raise Unavailable("fiche CELLAR anormalement grande")
    try:
        work = parse_xml(body).find("WORK")
    except (ET.ParseError, Suspicious):
        raise Unavailable("fiche CELLAR illisible")
    if work is None:
        raise Unavailable("fiche CELLAR sans décision")
    if celex not in {e.findtext("VALUE") for e in work.findall("RESOURCE_LEGAL_ID_CELEX")}:
        raise Unavailable(f"la fiche CELLAR ne porte pas le numéro {celex}")
    day = (work.findtext("WORK_DATE_DOCUMENT/VALUE") or "")[:10]
    return {day} if day else set()


def hudoc_link(number):
    """La recherche HUDOC de ce numéro de requête, à ouvrir dans un navigateur."""
    query = json.dumps({"appno": [number]}, separators=(",", ":"))
    return HUDOC + urllib.parse.quote(query, safe="")
