"""Le lien vers ce qui a été trouvé, pour que le lecteur l'ouvre d'un clic.

Chaque adresse est construite ici, sur un modèle fixe, à partir d'un identifiant renvoyé par
une base officielle. L'identifiant est contrôlé avant : une réponse d'une forme inattendue ne
donne pas de lien, jamais une adresse fabriquée avec ce qu'elle contient. Rien ne vient du
document vérifié.

Les liens ne sont pas ouverts par le programme : Légifrance et EUR-Lex refusent les robots
(HTTP 403 et 202 à un programme), un navigateur les ouvre normalement.
"""
import re

LEGIFRANCE = "https://www.legifrance.gouv.fr"

_LEGIARTI = re.compile(r"LEGIARTI\d{12}")
_KALIARTI = re.compile(r"KALIARTI\d{12}")
# Les décisions dans Légifrance : Conseil constitutionnel, Conseil d'État et cours
# administratives d'appel (fonds CETAT, où sont aussi celles du Tribunal des conflits).
_DECISION = {"CONSTEXT": "cons", "CETATEXT": "ceta", "JURITEXT": "juri"}
_JUDILIBRE = re.compile(r"[0-9a-f]{24}")
_CELEX = re.compile(r"6\d{4}[A-Z]{2}\d{4}")
_DAY = re.compile(r"\d{4}-\d{2}-\d{2}")


class Found(list):
    """Les dates des décisions trouvées, triées, comme avant ; et `links`, {date: lien}.
    Reste une liste : tout ce qui compare ou parcourt des dates marche sans changer."""

    def __init__(self, links=None):
        self.links = {d: u for d, u in (links or {}).items() if d}
        super().__init__(sorted(self.links))


def link_for(days, day=None):
    """Le lien de la décision de ce jour, ou de la première trouvée ; None si aucun."""
    found = getattr(days, "links", None) or {}
    if day in found:
        return found[day]
    return next((u for u in found.values() if u), None)


def code_article(version_id):
    """Une version d'un article de code."""
    if _LEGIARTI.fullmatch(version_id or ""):
        return f"{LEGIFRANCE}/codes/article_lc/{version_id}"
    return None


def text_article(version_id):
    """Une version d'un article de loi, d'ordonnance ou de décret non codifié."""
    if _LEGIARTI.fullmatch(version_id or ""):
        return f"{LEGIFRANCE}/loda/article_lc/{version_id}"
    return None


def convention_article(version_id):
    """Une version d'un article de convention collective (fonds KALI)."""
    if _KALIARTI.fullmatch(version_id or ""):
        return f"{LEGIFRANCE}/conv_coll/article/{version_id}"
    return None


def legifrance_decision(text_id):
    """Une décision publiée dans Légifrance : CONSTEXT..., CETATEXT..., JURITEXT..."""
    m = re.fullmatch(r"([A-Z]{8})\d{12}", text_id or "")
    if m and m.group(1) in _DECISION:
        return f"{LEGIFRANCE}/{_DECISION[m.group(1)]}/id/{text_id}"
    return None


def judilibre(decision_id):
    """Une décision publiée par Judilibre : Cour de cassation, cours d'appel, tribunaux."""
    if _JUDILIBRE.fullmatch(decision_id or ""):
        return f"https://www.courdecassation.fr/decision/{decision_id}"
    return None


def arianeweb(number, day):
    """Une décision du Conseil d'État dans ArianeWeb : son numéro et sa date suffisent."""
    if re.fullmatch(r"\d{1,7}", number or "") and _DAY.fullmatch(day or ""):
        return f"https://www.conseil-etat.fr/fr/arianeweb/CE/decision/{day}/{number}"
    return None


def eur_lex(celex):
    """Une décision de la Cour de justice ou du Tribunal de l'Union européenne."""
    if _CELEX.fullmatch(celex or ""):
        return f"https://eur-lex.europa.eu/legal-content/FR/TXT/?uri=CELEX:{celex}"
    return None
