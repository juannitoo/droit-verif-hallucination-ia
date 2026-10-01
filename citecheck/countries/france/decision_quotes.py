"""Le passage cité entre guillemets est-il vraiment dans la décision ?

POURQUOI
  Un numéro réel, à la bonne date, peut porter un passage qu'il ne contient pas. Le
  numéro passe alors tout contrôle ; le passage cité, lui, se compare au texte.

COMMENT
  Quand une décision trouvée est suivie (ou précédée, collé) d'un passage entre guillemets,
  on lit son texte intégral, là où la base le donne, et on y cherche le passage, par
  morceaux, comme pour un article (articles.quote_fragments). Le sommaire et les titres
  comptent : un avocat cite souvent le sommaire.
    Judilibre   : Cour de cassation, cours d'appel, tribunaux (texte pseudonymisé)
    Légifrance  : Conseil constitutionnel, CAA, Tribunal des conflits
  ArianeWeb (Conseil d'État) et CELLAR (Union européenne) : ce programme ne lit pas encore
  leur texte ; le rapport le dit.

CE QUE VEUT DIRE « NON RETROUVÉ »
  Pas « inventé ». Une paraphrase, une citation de mémoire, un nom que la pseudonymisation a
  remplacé par [X] : le passage n'est pas là tel quel, et c'est au lecteur de juger. Le
  verdict passe donc en orange, jamais en rouge.

Seul l'identifiant de la décision part sur le réseau, jamais le passage cité.
"""
import re

from . import piste, sources
from .articles import _norm, quote_fragments


# Les verdicts où la décision a été trouvée : c'est là qu'un passage cité peut se vérifier.
FOUND = ("CONFIRMED", "EXISTS_DATE_UNCHECKED", "WRONG_DATE", "WRONG_CHAMBER")
_JUDILIBRE = re.compile(r"https://www\.courdecassation\.fr/decision/([0-9a-f]{24})")
_LEGIFRANCE = re.compile(r"https://www\.legifrance\.gouv\.fr/(?:cons|ceta|juri)/id/"
                         r"((?:CONSTEXT|CETATEXT|JURITEXT)\d{12})")


def _strip(html):
    import html as h
    return h.unescape(re.sub(r"<[^<>]*>", " ", html or ""))     # voir legifrance._strip_html


def judilibre_text(decision_id, key):
    """Le texte intégral, le sommaire et les titres d'une décision de Judilibre."""
    data = sources._judilibre_get("decision", {"id": decision_id}, key)
    parts = [data.get("text") or "", data.get("summary") or ""]
    for entry in data.get("titlesAndSummaries") or []:
        parts += [entry.get("summary") or ""] + list(entry.get("titles") or [])
    return "\n".join(p for p in parts if isinstance(p, str))


def legifrance_text(client, text_id):
    """Le texte intégral et les sommaires d'une décision publiée dans Légifrance."""
    t = client._post("/consult/juri", {"textId": text_id}).get("text") or {}
    parts = [_strip(t.get("texte")), _strip(t.get("texteHtml"))]
    for s in t.get("sommaire") or []:
        parts.append(_strip(s.get("resumePrincipal") if isinstance(s, dict) else str(s)))
    return "\n".join(parts)


def source_text(link, keys, client):
    """(texte de la décision, nom de la base), ou (None, raison) si on ne sait pas le lire."""
    m = _JUDILIBRE.fullmatch(link or "")
    if m:
        if not keys.get("PISTE_API_KEY"):
            return None, "clé PISTE absente"
        return judilibre_text(m.group(1), keys["PISTE_API_KEY"]), "Judilibre"
    m = _LEGIFRANCE.fullmatch(link or "")
    if m:
        if client is None:
            return None, "identifiants Légifrance absents"
        return legifrance_text(client, m.group(1)), "Légifrance"
    return None, "ce programme ne lit pas encore le texte des décisions de cette base"


# En dessous, la base a répondu sans le texte, ou avec un simple avis (« document
# indisponible ») : on n'a rien lu de la décision, donc rien à comparer. Une décision, même un
# rejet non spécialement motivé, dépasse largement 500 caractères (audit du 01/10/2026).
MIN_TEXT = 500
# Au-dessus, ce n'est plus une décision (les plus longues font quelques centaines de milliers
# de caractères) : on ne compare que le début.
MAX_TEXT = 2_000_000


def _missing(fragments, body):
    return [f for f in fragments if f not in body]


def check(citation, result, keys, client=None):
    """Le verdict, revu d'après le passage cité : inchangé s'il n'y en a pas, ou si la
    décision n'a pas été trouvée ; « non retrouvé » (orange) si le passage n'y est pas."""
    verdict, why, actual, *rest = result
    link = rest[0] if rest else None
    fragments = quote_fragments(citation.get("quote") or "")
    if verdict not in FOUND or not fragments:
        return result
    try:
        text, base = source_text(link, keys, client)
    except Exception as e:      # Unavailable, HTTP, réseau : une base muette ne conclut rien
        said = str(e) if isinstance(e, piste.Limited) else type(e).__name__
        return (verdict, f"{why} ; passage cité non contrôlé (la base n'a pas répondu : "
                f"{said})", actual, link)
    if text is None:
        return verdict, f"{why} ; passage cité non contrôlé ({base})", actual, link
    body = _norm(text[:MAX_TEXT])
    if len(body) < MIN_TEXT:
        # Une réponse vide n'est pas un texte où le passage manque : « non retrouvé »
        # accuserait le document à tort.
        return (verdict, f"{why} ; passage cité non contrôlé ({base} a répondu sans le "
                "texte de la décision)", actual, link)
    missing = _missing(fragments, body)
    if not missing:
        return verdict, f"{why} ; passage cité retrouvé dans la décision ({base})", actual, link
    part = ("le passage cité entre guillemets" if len(missing) == len(fragments)
            else f"{len(missing)} des {len(fragments)} morceaux du passage cité")
    said = (f"{part} ne se retrouve pas dans la décision, ni dans son sommaire ({base}) : "
            "paraphrase, ou contenu prêté à une vraie décision ; à vérifier")
    if verdict in ("CONFIRMED", "EXISTS_DATE_UNCHECKED"):
        return "DECISION_QUOTE_NOT_FOUND", f"{why} ; mais {said}", actual, link
    return verdict, f"{why} ; et {said}", actual, link
