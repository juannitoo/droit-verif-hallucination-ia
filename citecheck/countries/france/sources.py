"""Les bases officielles françaises interrogées.

  Ordre administratif (CE, CAA, TA) : ArianeWeb, la base du Conseil d'État. Sans clé.
    POST https://www.conseil-etat.fr/xsearch?type=json, paramètre `text`.
  Ordre judiciaire (Cass.) : Judilibre, l'API de la Cour de cassation, via le portail
    PISTE. Clé API personnelle de l'utilisateur, passée dans l'en-tête `KeyId`.

Seuls le numéro de la décision et, pour Judilibre, la clé partent sur le réseau. Jamais
le texte du document.
"""
import json
import time
import urllib.error
import urllib.parse
import urllib.request

from ... import NAME, __version__

ARIANE = "https://www.conseil-etat.fr/xsearch?type=json"
JUDILIBRE = "https://api.piste.gouv.fr/cassation/judilibre/v1.0"
USER_AGENT = f"{NAME}/{__version__}"
PAUSE = 0.7          # on ne martèle pas un service public
TIMEOUT = 40


def _get_json(req):
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def ariane(number):
    """(occurrences, dates) du numéro dans ArianeWeb. (-1, set()) si la base n'a pas répondu.

    `dates` : les dates des documents qui SONT cette décision (son numéro en SourceStr5 ou
    SourceCsv1, sa date en SourceDateTime1), et non de ceux qui se contentent de la citer.
    Vide si la décision n'est connue que par les citations des autres."""
    body = urllib.parse.urlencode({"text": str(number)}).encode()
    req = urllib.request.Request(ARIANE, data=body, headers={
        "Content-Type": "application/x-www-form-urlencoded", "User-Agent": USER_AGENT})
    try:
        data = _get_json(req)
    except Exception:
        return -1, set()
    finally:
        time.sleep(PAUSE)
    dates = set()
    for doc in data.get("Documents") or []:
        numbers = {doc.get("SourceStr5", "")} | set((doc.get("SourceCsv1") or "").split(";"))
        if str(number) in numbers and doc.get("SourceDateTime1"):
            dates.add(doc["SourceDateTime1"][:10])
    return int(data.get("TotalCount", 0)), dates


def normalize(number):
    """17-28.268 et 17-28268 désignent le même pourvoi. Judilibre écrit avec le point."""
    return str(number).replace(".", "").replace(" ", "")


def judilibre(number, key):
    """La fiche de la décision, None si aucun pourvoi de ce numéro, ou {'_err': ...} si la
    base n'a pas répondu."""
    url = f"{JUDILIBRE}/search?" + urllib.parse.urlencode(
        {"query": str(number), "page_size": 5, "resolve_references": "true"})
    req = urllib.request.Request(url, headers={
        "KeyId": key, "Accept": "application/json", "User-Agent": USER_AGENT})
    try:
        data = _get_json(req)
    except urllib.error.HTTPError as e:
        return {"_err": f"HTTP {e.code}" + (" (clé refusée)" if e.code in (401, 403) else "")}
    except Exception as e:
        return {"_err": type(e).__name__}
    finally:
        time.sleep(PAUSE)
    target = normalize(number)
    for res in data.get("results", []):
        if target in [normalize(x) for x in (res.get("numbers") or [])]:
            return res
    return None


# Cours d'appel et tribunaux judiciaires (Judilibre)

API = "https://api.piste.gouv.fr/cassation/judilibre/v1.0"


def _judilibre_get(route, params, key):
    url = f"{API}/{route}?" + urllib.parse.urlencode(params, doseq=True)
    req = urllib.request.Request(url, headers={
        "KeyId": key, "Accept": "application/json", "User-Agent": USER_AGENT})
    try:
        return _get_json(req)
    finally:
        time.sleep(PAUSE)


def locations(jurisdiction, key):
    """{code Judilibre: libellé} des juridictions : « ca_paris » -> « Cour d'appel de Paris »."""
    data = _judilibre_get("taxonomy", {"id": "location", "context_value": jurisdiction}, key)
    return data.get("result") or {}


def yearly_counts(jurisdiction, location, key):
    """{année: nombre de décisions publiées} dans Judilibre pour cette juridiction."""
    data = _judilibre_get("stats", {"jurisdiction": jurisdiction, "location": location,
                                    "keys": "year"}, key)
    return {a["key"]["year"]: a["decisions_count"]
            for a in (data.get("results") or {}).get("aggregated_data") or []}


def judilibre_rg(number, jurisdiction, location, key):
    """Les décisions de cette juridiction sous ce numéro RG : liste de dates, vide si aucune,
    ou {'_err': ...} si la base n'a pas répondu."""
    try:
        data = _judilibre_get("search", {"query": number, "jurisdiction": jurisdiction,
                                         "location": location, "page_size": 20}, key)
    except urllib.error.HTTPError as e:
        return {"_err": f"HTTP {e.code}"}
    except Exception as e:
        return {"_err": type(e).__name__}
    target = normalize(number)
    return sorted({(r.get("decision_date") or "")[:10] for r in data.get("results") or []
                   if target in [normalize(x) for x in (r.get("numbers") or [])]})
