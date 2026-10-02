"""Ce qui a le droit de partir sur le réseau.

La fenêtre ne voit que des citations sorties de l'extracteur, dont chaque champ a une forme
fixe : « 17-28.268 », « 308850 », « L3121-2 ». La ligne de commande (--number, --case), un
script ou une IA qui appelle check() n'y passent pas. Sans ce filtre, une phrase collée à la
place d'un numéro partait telle quelle vers ArianeWeb, ou dans l'adresse d'une requête
Judilibre, donc dans les journaux du portail (audit du 30/09/2026, point 1).

Le contrôle est fait une fois, à l'entrée de check(), pour tous les appelants. Une citation
refusée n'est pas raccourcie pour passer : elle sort « non vérifiée », avec la raison.
"""
import re

from . import codes
from .extract import LATIN

MAX_NUMBER = 40      # caractères : « 46 quater-0 ZZ bis » en a 18

_ARTICLE = re.compile(rf"(?:[LRDA]\s?)?(?:1er|\d+(?:[-.]\d+)*)"
                      rf"(?:\s{LATIN}|-0|\s[A-Z]{{1,2}})*", re.I)
_DECISION = {
    "administrative": r"\d{5,7}",
    "judicial": r"\d{2}-\d{2}\.?\d{3}",
    "caa": r"\d{2}[A-Z]{2}\d{5}",
    "conflicts": r"C?\d{4,5}",
    "constitutional": r"\d{2,4}-\d{1,5}(?:/\d{1,5}){0,4}",
    "eu": r"[CT]-\d{1,4}/\d{2}",
    "ta": r"\d{5,7}(?:/\d{2,4})?",
}
_LOWER = {"ca": r"\d{2}/\d{4,5}", "tj": r"\d{2}/\d{4,5}",
          "tcom": r"(?:19|20)\d\d[A-Z]\d{5}|[A-Z]?(?:19|20)\d{8}"}
NOT_SENT = {"other", "unnumbered"}      # montrés dans le rapport, jamais cherchés


def _is(pattern, value, flags=0):
    return isinstance(value, str) and len(value) <= MAX_NUMBER and bool(
        re.fullmatch(pattern, value, flags))


def _is_day(value):
    from datetime import date
    if not _is(r"\d{4}-\d{2}-\d{2}", value):
        return False
    try:
        date.fromisoformat(value)
        return True
    except ValueError:
        return False


def refusal(c):
    """None si la citation a la forme que l'extracteur produit ; sinon, pourquoi elle ne
    part pas."""
    kind, order, number = c.get("kind"), c.get("order"), c.get("number")
    if kind == "text":
        # Un texte cité en entier : sa nature, et un numéro ou une date de forme connue.
        if c.get("text_nature") not in ("LOI", "ORDONNANCE", "DECRET"):
            return "nature de texte inconnue : non envoyé"
        if c.get("text_number") is not None and not _is(r"\d{2,4}-\d{1,5}", c["text_number"]):
            return "numéro de texte de forme inconnue : non envoyé"
        if c.get("text_date") is not None and not _is(r"\d{4}-\d{2}-\d{2}", c["text_date"]):
            return "date de texte de forme inconnue : non envoyé"
        if not (c.get("text_number") or c.get("text_date")):
            return "texte sans numéro ni date : non envoyé"
        return None
    if kind in ("article", "text_article", "convention_article"):
        if not _is(_ARTICLE.pattern, number, re.I):
            return "numéro d'article de forme inconnue : non envoyé"
        if kind == "article" and c.get("code") not in (
                set(codes.TITLES) | set(codes.ABROGATED) | set(codes.AMBIGUOUS)
                | set(codes.SUCCESSION)):
            return "code inconnu : non envoyé"
        if kind == "text_article":
            if c.get("text_nature") not in ("LOI", "ORDONNANCE", "DECRET"):
                return "nature de texte inconnue : non envoyé"
            if c.get("text_number") is not None and not _is(r"\d{2,4}-\d{1,5}",
                                                           c["text_number"]):
                return "numéro de texte de forme inconnue : non envoyé"
            if c.get("text_date") is not None and not _is(r"\d{4}-\d{2}-\d{2}", c["text_date"]):
                return "date de texte de forme inconnue : non envoyé"
        if kind == "convention_article" and c.get("idcc") is not None and not _is(
                r"\d{1,4}", str(c["idcc"])):
            return "IDCC de forme inconnue : non envoyé"
        return None
    if kind not in (None, "decision"):
        return "type de citation inconnu : non envoyé"
    # La date citée part dans l'adresse d'une requête (tribunaux de commerce) : une vraie
    # date, ou rien (audit du 01/10/2026).
    if c.get("cited_date") is not None and not _is_day(c["cited_date"]):
        return "date citée de forme inconnue : non envoyé"
    if order in NOT_SENT:
        return None
    if order == "lower":
        pattern = _LOWER.get(c.get("jurisdiction"))
        if not pattern:
            return "juridiction inconnue : non envoyé"
    else:
        pattern = _DECISION.get(order)
        if not pattern:
            return "ordre de juridiction inconnu : non envoyé"
    if not _is(pattern, number):
        return "numéro de forme inconnue pour cette juridiction : non envoyé"
    return None
