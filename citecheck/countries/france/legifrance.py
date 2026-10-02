"""Légifrance, via le portail PISTE : les codes (fonds LEGI) et les conventions collectives
(fonds KALI).

AUTHENTIFICATION
  OAuth2 « client_credentials » : l'identifiant et le secret de l'application PISTE de
  l'utilisateur donnent un jeton valable environ une heure. Ce n'est pas la même clé que
  Judilibre, même si c'est la même application PISTE.

CE QU'ON A APPRIS DE L'API (sondée le 29/09/2026)
  - /consult/getArticleWithIdAndNum ne connaît que les articles EN VIGUEUR aujourd'hui. Un
    article abrogé ou pas encore en vigueur y répond `null` : inutilisable pour dire
    « n'existe pas ».
  - /search sur le fonds CODE_ETAT trouve un numéro d'article même abrogé ou pas encore en
    vigueur. MAIS il TRONQUE la liste des versions à une dizaine, et pas toujours les mêmes
    d'un appel à l'autre : L. 242-1 du Code de la sécurité sociale, 37 versions, en montrait
    3, et le programme le déclarait « abrogé » (audit du 29/09/2026). On ne s'en sert donc
    que pour trouver UNE version ; la liste complète vient de la fiche de cette version
    (/consult/getArticle, champ articleVersions).
  - Le filtre NOM_CODE ne filtre presque rien : « article 1 » du Code civil ramène les 41
    « article 1 » de tous les codes. On trie donc nous-mêmes sur l'identifiant du code
    (LEGITEXT...). Et l'ordre des pages CHANGE d'un appel à l'autre : lu par pages de 10 en
    s'arrêtant tôt, l'article 1 du Code civil sortait 0, 2 puis 2 versions en trois appels,
    donc « ne semble pas exister » une fois sur trois (audit du 30/09/2026). On lit TOUS les
    résultats, par pages de 100 ; si on n'a pas pu tout lire, on ne conclut rien.
  - Décisions (sondé le 29/09/2026 au soir) : /search avec le champ NUM_DEC, sur le fonds
    CONSTIT (Conseil constitutionnel) ou CETAT (Conseil d'État, CAA, et Tribunal des
    conflits). Le numéro s'écrit SANS suffixe : « 2010-605 » trouve la décision,
    « 2010-605 DC » ne trouve rien. La date n'est que dans le titre. Et le champ
    NUM_AFFAIRE, sur CETAT, IGNORE le critère : 571 555 résultats pour n'importe quel
    numéro. Ne jamais s'en servir.
  - Lois, ordonnances, décrets non codifiés (sondé le 30/09/2026), fonds LODA_ETAT :
    le champ NUM (« 89-462 ») désigne UN texte ; NUM + NUM_ARTICLE donne les versions de
    l'article, abrogées comprises ; la fiche d'une version (/consult/getArticle) porte la
    liste complète. Sans numéro, « loi du 6 juillet 1989 » désigne NEUF lois : on les
    retrouve par leur date dans le titre (champ TITLE) et le filtre NATURE (LOI, qui couvre
    aussi les lois organiques, ORDONNANCE, DECRET). Le filtre DATE_SIGNATURE, lui, est
    ignoré par l'API : il renvoie toutes les lois.
  - /consult/kaliContIdcc donne la convention d'un IDCC et l'identifiant de son texte de
    base ; /consult/kaliText renvoie en un appel tous les articles de ce texte, toutes leurs
    versions et leur contenu. Un IDCC inexistant y provoque une erreur 500, pas une réponse
    vide.

Seuls le numéro d'article et le nom du code partent sur le réseau. Jamais le texte du
document.
"""
import json
import re
import urllib.error
import urllib.parse
import urllib.request

from ... import NAME, __version__
from . import piste
from ...http import urlopen

OAUTH = "https://oauth.piste.gouv.fr/api/oauth/token"
API = "https://api.piste.gouv.fr/dila/legifrance/lf-engine-app"
USER_AGENT = f"{NAME}/{__version__}"
TIMEOUT = 40
PAGE_SIZE = 100
MAX_PAGES = 5         # 500 résultats ; mesuré le 30/09 : 41 « 1 », 44 « L111-1 »
KNOWN_IDCC = "1979"     # convention HCR : sert à distinguer « IDCC inconnu » d'une panne


class Unavailable(Exception):
    """Légifrance n'a pas répondu, ou a refusé les identifiants."""

    def __init__(self, message, status=None):
        super().__init__(message)
        self.status = status


class Client:
    def __init__(self, client_id, client_secret):
        self._id, self._secret = client_id, client_secret
        self._token = None
        self._codes = None
        self._conventions = {}
        self._kali_texts = {}

    def _get_token(self):
        body = urllib.parse.urlencode({"grant_type": "client_credentials",
                                       "client_id": self._id,
                                       "client_secret": self._secret,
                                       "scope": "openid"}).encode()
        req = urllib.request.Request(OAUTH, data=body, headers={
            "Content-Type": "application/x-www-form-urlencoded", "User-Agent": USER_AGENT})
        try:
            piste.wait()
            with urlopen(req, timeout=TIMEOUT) as r:
                token = json.loads(r.read().decode()).get("access_token")
        except piste.Limited as e:
            raise Unavailable(str(e), 429)
        except urllib.error.HTTPError as e:
            if piste.refused(e.code):
                raise Unavailable(piste.LIMITED, 429)
            raise Unavailable(f"HTTP {e.code} sur l'authentification"
                              + (" (identifiants refusés)" if e.code in (400, 401) else ""))
        except Exception as e:
            raise Unavailable(type(e).__name__)
        if not token:
            raise Unavailable("pas de jeton")
        return token

    def _post(self, route, body):
        if not self._token:
            self._token = self._get_token()
        req = urllib.request.Request(API + route, data=json.dumps(body).encode(), headers={
            "Authorization": f"Bearer {self._token}", "Content-Type": "application/json",
            "Accept": "application/json", "User-Agent": USER_AGENT})
        try:
            piste.wait()
            with urlopen(req, timeout=TIMEOUT) as r:
                return json.loads(r.read().decode("utf-8", "replace"))
        except piste.Limited as e:
            raise Unavailable(str(e), 429)
        except urllib.error.HTTPError as e:
            if piste.refused(e.code):
                raise Unavailable(piste.LIMITED, 429)
            raise Unavailable(f"HTTP {e.code}" + (" (accès refusé : l'application PISTE "
                              "est-elle abonnée à Légifrance ?)" if e.code == 403 else ""),
                              e.code)
        except Exception as e:
            raise Unavailable(type(e).__name__)

    def codes(self):
        """{titre exact: identifiant LEGITEXT} de tous les codes, en vigueur ET abrogés (108
        au 29/09/2026) : un article d'un code abrogé doit sortir « abrogé », pas « code
        inconnu »."""
        if self._codes is None:
            data = self._post("/list/code", {"pageSize": 200, "pageNumber": 1,
                                             "states": ["VIGUEUR", "ABROGE"]})
            self._codes = {c["titre"]: c["cid"] for c in data.get("results") or []}
        return self._codes

    def versions(self, code_title, code_id, number):
        """Toutes les versions de l'article `number` dans ce code, triées par date de début.

        Chaque version : {id, etat, debut, fin} (dates AAAA-MM-JJ). Liste vide si aucun
        article de ce numéro n'a jamais existé dans ce code."""
        found = self._search_versions(code_title, code_id, number)
        if not found:
            return []
        # La fiche d'une version porte la liste complète ; la recherche, non.
        article = self._post("/consult/getArticle", {"id": found[0]["id"]}).get("article") or {}
        complete = [{"id": v.get("id"), "etat": v.get("etat"), "debut": _day(v.get("dateDebut")),
                     "fin": _day(v.get("dateFin"))}
                    for v in article.get("articleVersions") or [] if v.get("id")]
        if len(complete) < len(found):
            raise Unavailable(f"liste des versions de {number} incohérente "
                              f"({len(complete)} dans la fiche, {len(found)} dans la recherche)")
        return sorted(dated(complete, number), key=lambda v: v["debut"])

    def _search_versions(self, code_title, code_id, number):
        """Les versions que la recherche veut bien montrer : incomplet, voir plus haut."""
        found, read = {}, 0
        for page in range(1, MAX_PAGES + 1):
            data = self._post("/search", {"fond": "CODE_ETAT", "recherche": {
                "champs": [{"typeChamp": "NUM_ARTICLE", "operateur": "ET", "criteres": [
                    {"typeRecherche": "EXACTE", "valeur": number, "operateur": "ET"}]}],
                "filtres": [{"facette": "NOM_CODE", "valeurs": [code_title]}],
                "pageNumber": page, "pageSize": PAGE_SIZE, "operateur": "ET",
                "sort": "PERTINENCE", "typePagination": "ARTICLE"}})
            results = data.get("results") or []
            total = _total(data)
            read += len(results)
            for res in results:
                if not any(t.get("cid") == code_id for t in res.get("titles") or []):
                    continue
                for section in res.get("sections") or []:
                    for ext in section.get("extracts") or []:
                        if ext.get("num") == number and ext.get("id"):
                            found[ext["id"]] = {
                                "id": ext["id"], "etat": ext.get("legalStatus"),
                                "debut": (ext.get("dateDebut") or "")[:10],
                                "fin": (ext.get("dateFin") or "")[:10]}
            if _complete(read, total):
                return sorted(found.values(), key=lambda v: v["debut"])
            if not results:
                break
        # Tout n'a pas été lu : une absence ici ne prouverait rien.
        raise Unavailable(f"recherche de l'article {number} incomplète ({read} résultats lus "
                          f"sur {total})")

    def text(self, article_id):
        """Le texte d'une version d'article."""
        data = self._post("/consult/getArticle", {"id": article_id})
        return ((data.get("article") or {}).get("texte") or "").strip()

    def decisions(self, fond, number):
        """[(titre, identifiant)] des décisions portant ce numéro dans ce fonds (CONSTIT,
        CETAT). Liste vide si aucune. Tout est lu, ou rien n'est conclu."""
        titles, read = [], 0
        for page in range(1, MAX_PAGES + 1):
            data = self._post("/search", {"fond": fond, "recherche": {
                "champs": [{"typeChamp": "NUM_DEC", "operateur": "ET", "criteres": [
                    {"typeRecherche": "EXACTE", "valeur": number, "operateur": "ET"}]}],
                "pageNumber": page, "pageSize": PAGE_SIZE, "operateur": "ET",
                "sort": "PERTINENCE", "typePagination": "DEFAUT"}})
            results = data.get("results") or []
            total = _total(data)
            read += len(results)
            titles += [(t.get("title") or "", t.get("id") or "")
                       for r in results for t in (r.get("titles") or [])[:1]]
            if _complete(read, total):
                return titles
            if not results:
                break
        raise Unavailable(f"recherche de la décision {number} incomplète ({read} résultats "
                          f"lus sur {total})")

    def _text_search(self, champs, filtres=(), pagination="DEFAUT"):
        """Tous les résultats d'une recherche dans LODA_ETAT, ou Unavailable."""
        results, read = [], 0
        for page in range(1, MAX_PAGES + 1):
            data = self._post("/search", {"fond": "LODA_ETAT", "recherche": {
                "champs": [{"typeChamp": t, "operateur": "ET", "criteres": [
                    {"typeRecherche": "EXACTE", "valeur": v, "operateur": "ET"}]}
                    for t, v in champs],
                "filtres": list(filtres), "pageNumber": page, "pageSize": PAGE_SIZE,
                "operateur": "ET", "sort": "PERTINENCE", "typePagination": pagination}})
            page_results = data.get("results") or []
            total = _total(data)
            results += page_results
            read += len(page_results)
            if _complete(read, total):
                return results
            if not page_results:
                break
        raise Unavailable(f"recherche de texte incomplète ({read} résultats lus sur {total})")

    def texts_by_number(self, number):
        """[(identifiant LEGITEXT, titre)] des textes portant ce numéro (« 89-462 »)."""
        out = {}
        for r in self._text_search([("NUM", number)]):
            t = (r.get("titles") or [{}])[0]
            if t.get("id"):
                out[t["id"].split("_")[0]] = _strip_html(t.get("title") or "")
        return sorted(out.items())

    def texts_by_title(self, words, nature):
        """[(identifiant, titre)] des textes de cette nature (LOI, ORDONNANCE, DECRET) dont le
        titre contient ces mots (« 6 juillet 1989 »)."""
        out = {}
        for r in self._text_search([("TITLE", words)],
                                   [{"facette": "NATURE", "valeurs": [nature]}]):
            t = (r.get("titles") or [{}])[0]
            if t.get("id"):
                out[t["id"].split("_")[0]] = _strip_html(t.get("title") or "")
        return sorted(out.items())

    def text_article_versions(self, text_number, text_id, number):
        """Toutes les versions de l'article `number` du texte `text_id` (numéro
        `text_number`), comme versions() pour un code. Liste vide si aucune."""
        found = set()
        for r in self._text_search([("NUM", text_number), ("NUM_ARTICLE", number)],
                                   pagination="ARTICLE"):
            if not any((t.get("id") or "").split("_")[0] == text_id or t.get("cid") == text_id
                       for t in r.get("titles") or []):
                continue
            for section in r.get("sections") or []:
                for ext in section.get("extracts") or []:
                    if ext.get("num") == number and ext.get("id"):
                        found.add(ext["id"])
        if not found:
            return []
        article = self._post("/consult/getArticle", {"id": sorted(found)[0]}).get("article") or {}
        complete = [{"id": v.get("id"), "etat": v.get("etat"), "debut": _day(v.get("dateDebut")),
                     "fin": _day(v.get("dateFin"))}
                    for v in article.get("articleVersions") or [] if v.get("id")]
        if len(complete) < len(found):
            raise Unavailable(f"liste des versions de l'article {number} incohérente")
        # La fiche liste aussi l'article tel que publié au Journal officiel (JORFARTI...),
        # sans date : ce n'est pas une version consolidée.
        complete = [v for v in complete if not v["id"].startswith("JORFARTI")]
        return sorted(dated(complete, number), key=lambda v: v["debut"])

    def convention(self, idcc):
        """(titre, identifiants des textes de base) de la convention, ou None si Légifrance ne
        la connaît pas. Une erreur 500 vaut « inconnue » : c'est ainsi que l'API répond à un
        IDCC inexistant (les contrôles ont prouvé juste avant qu'elle fonctionne)."""
        if idcc not in self._conventions:
            data = None
            for attempt in (1, 2):
                try:
                    data = self._post("/consult/kaliContIdcc", {"id": str(idcc)})
                    break
                except Unavailable as e:
                    if e.status != 500:
                        raise
            if data is None and idcc != KNOWN_IDCC:
                # Deux 500 de suite. Surcharge, ou IDCC inconnu ? Une convention connue
                # interrogée à l'instant tranche : si elle répond, le 500 visait cet IDCC ;
                # sinon la base va mal, et c'est une erreur, jamais « inexistant »
                # (audit du 29/09/2026, K4).
                if self.convention(KNOWN_IDCC) is None:
                    raise Unavailable("Légifrance répond en erreur, même pour une convention "
                                      "connue", 500)
                # L'IDCC est tenu pour inconnu, pour cette citation seulement : un 500 peut
                # aussi être passager, il n'est pas retenu pour la suite (audit du 01/10/2026).
                return None
            base = (data or {}).get("texteBaseId") or []
            base = [base] if isinstance(base, str) else base   # une liste, parfois plusieurs
            if base:
                self._conventions[idcc] = (data.get("titre") or "", tuple(base))
            else:
                self._conventions[idcc] = None
        return self._conventions[idcc]

    def convention_articles(self, text_ids):
        """Tous les articles des textes de base, toutes versions : liste de
        {id, num, etat, debut, fin, texte}."""
        return [a for tid in text_ids for a in self._kali_text(tid)]

    def _kali_text(self, text_id):
        if text_id not in self._kali_texts:
            data = self._post("/consult/kaliText", {"id": text_id})
            found = []

            def walk(section):
                for a in section.get("articles") or []:
                    found.append({"id": a.get("id"), "num": a.get("num"), "etat": a.get("etat"),
                                  "debut": _day(a.get("dateDebut")),
                                  "fin": _day(a.get("dateFin")),
                                  "texte": _strip_html(a.get("content") or "")})
                for sub in section.get("sections") or []:
                    walk(sub)
            walk(data)
            self._kali_texts[text_id] = found
        return self._kali_texts[text_id]


def _day(ms):
    """Date Légifrance (millisecondes depuis 1970) en AAAA-MM-JJ. Par addition, pas par
    fromtimestamp : sous Windows, celui-ci refuse les dates d'avant 1970 (Code civil, 1804).
    "" si la date manque ; "?" si ce n'est pas une date (dated() la refuse)."""
    if ms is None:
        return ""
    from datetime import datetime, timedelta, timezone
    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    try:
        return (epoch + timedelta(milliseconds=ms)).date().isoformat()
    except (TypeError, ValueError, OverflowError):
        return "?"


# Une date de version plausible : du Code civil (1804) et des textes plus anciens encore
# cités, jusqu'à la fin « sans terme » que Légifrance écrit 2999-01-01.
_PLAUSIBLE = re.compile(r"(1[6-9]\d\d|2\d\d\d)-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])")


def dated(versions, number):
    """Les versions, si chacune a une vraie date de début (et de fin, quand elle en a une).
    Sinon Unavailable : une version sans début passerait pour « en vigueur depuis
    toujours » et ferait un bleu que la base n'a pas donné (audit du 01/10/2026)."""
    for v in versions:
        if not _PLAUSIBLE.fullmatch(v["debut"] or "") or (
                v["fin"] and not _PLAUSIBLE.fullmatch(v["fin"])):
            raise Unavailable(f"version de l'article {number} sans date valable")
    return versions


def _total(data):
    """Le nombre de résultats annoncé par une recherche. Absent ou mal formé : Unavailable,
    car « tout a été lu » se décide en le comparant à ce qui a été reçu, et une recherche
    tenue à tort pour complète ferait dire « n'existe pas » (audit du 01/10/2026)."""
    total = data.get("totalResultNumber")
    if type(total) is not int or total < 0:
        raise Unavailable("recherche Légifrance sans nombre de résultats")
    return total


def _complete(read, total):
    """Tout est-il lu ? Plus de résultats reçus qu'annoncés : la réponse se contredit."""
    if read > total:
        raise Unavailable(f"recherche Légifrance incohérente ({read} résultats reçus, "
                          f"{total} annoncés)")
    return read == total


def _strip_html(html):
    import html as h
    import re
    # [^<>] : une balise s'arrête au chevron suivant. Avec [^>], une réponse faite de
    # chevrons ouvrants sans fermant relisait toute la suite à chacun (temps au carré).
    return h.unescape(re.sub(r"<[^<>]*>", " ", html)).strip()

