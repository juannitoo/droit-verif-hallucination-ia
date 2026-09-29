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
  - /search sur le fonds CODE_ETAT renvoie toutes les versions d'un numéro, avec leur état
    et leurs dates. C'est ce qu'on utilise.
  - Le filtre NOM_CODE ne suffit pas : l'article 1382 du Code civil ramène aussi le 1382 du
    Code général des impôts. On filtre sur l'identifiant du code (LEGITEXT...).
  - /consult/kaliContIdcc donne la convention d'un IDCC et l'identifiant de son texte de
    base ; /consult/kaliText renvoie en un appel tous les articles de ce texte, toutes leurs
    versions et leur contenu. Un IDCC inexistant y provoque une erreur 500, pas une réponse
    vide.

Seuls le numéro d'article et le nom du code partent sur le réseau. Jamais le texte du
document.
"""
import json
import time
import urllib.error
import urllib.parse
import urllib.request

from ... import NAME, __version__

OAUTH = "https://oauth.piste.gouv.fr/api/oauth/token"
API = "https://api.piste.gouv.fr/dila/legifrance/lf-engine-app"
USER_AGENT = f"{NAME}/{__version__}"
PAUSE = 0.3
TIMEOUT = 40
MAX_PAGES = 5


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
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                token = json.loads(r.read().decode()).get("access_token")
        except urllib.error.HTTPError as e:
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
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                return json.loads(r.read().decode("utf-8", "replace"))
        except urllib.error.HTTPError as e:
            raise Unavailable(f"HTTP {e.code}" + (" (accès refusé : l'application PISTE "
                              "est-elle abonnée à Légifrance ?)" if e.code == 403 else ""),
                              e.code)
        except Exception as e:
            raise Unavailable(type(e).__name__)
        finally:
            time.sleep(PAUSE)

    def codes(self):
        """{titre exact: identifiant LEGITEXT} des codes en vigueur."""
        if self._codes is None:
            data = self._post("/list/code", {"pageSize": 200, "pageNumber": 1,
                                             "states": ["VIGUEUR"]})
            self._codes = {c["titre"]: c["cid"] for c in data.get("results") or []}
        return self._codes

    def versions(self, code_title, code_id, number):
        """Toutes les versions de l'article `number` dans ce code, triées par date de début.

        Chaque version : {id, etat, debut, fin} (dates AAAA-MM-JJ). Liste vide si aucun
        article de ce numéro n'a jamais existé dans ce code."""
        found = {}
        for page in range(1, MAX_PAGES + 1):
            data = self._post("/search", {"fond": "CODE_ETAT", "recherche": {
                "champs": [{"typeChamp": "NUM_ARTICLE", "operateur": "ET", "criteres": [
                    {"typeRecherche": "EXACTE", "valeur": number, "operateur": "ET"}]}],
                "filtres": [{"facette": "NOM_CODE", "valeurs": [code_title]}],
                "pageNumber": page, "pageSize": 10, "operateur": "ET",
                "sort": "PERTINENCE", "typePagination": "ARTICLE"}})
            results = data.get("results") or []
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
            if found or len(results) < 10:
                break
        return sorted(found.values(), key=lambda v: v["debut"])

    def text(self, article_id):
        """Le texte d'une version d'article."""
        data = self._post("/consult/getArticle", {"id": article_id})
        return ((data.get("article") or {}).get("texte") or "").strip()

    def convention(self, idcc):
        """(titre, identifiants des textes de base) de la convention, ou None si Légifrance ne
        la connaît pas. Une erreur 500 vaut « inconnue » : c'est ainsi que l'API répond à un
        IDCC inexistant (les contrôles ont prouvé juste avant qu'elle fonctionne)."""
        if idcc not in self._conventions:
            try:
                data = self._post("/consult/kaliContIdcc", {"id": str(idcc)})
            except Unavailable as e:
                if e.status != 500:
                    raise
                data = None
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
    """Date Légifrance (millisecondes depuis 1970) en AAAA-MM-JJ."""
    if ms is None:
        return ""
    from datetime import datetime, timezone
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).date().isoformat()


def _strip_html(html):
    import html as h
    import re
    return h.unescape(re.sub(r"<[^>]+>", " ", html)).strip()

