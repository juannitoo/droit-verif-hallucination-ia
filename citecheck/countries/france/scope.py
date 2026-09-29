"""Ce que le programme cherche, et ce qu'il ne cherche pas, pour la France.

Ce texte est affiché dans l'onglet « Ce qui est vérifié » et résumé en fin de rapport. Il
est construit à partir des listes que l'extracteur utilise vraiment (codes, abréviations) :
il ne peut pas annoncer une abréviation que le programme ne reconnaît pas.
"""
from .codes import TITLES, abbreviations_of

DECISIONS = [
    "Conseil d'État : « CE, 5 juin 2009, n° 308850 », « Conseil d'État, n° 308850 ». Le "
    "numéro doit suivre « n° ». Base interrogée : ArianeWeb.",
    "Cour de cassation : les numéros de pourvoi « 17-28.268 » ou « 17-28268 », avec ou sans "
    "« Cass. », « Civ. 2e », « Soc. »... Base interrogée : Judilibre.",
    "La date citée est lue à côté du numéro, en toutes lettres (« 5 juin 2009 ») ou en "
    "chiffres (« 05/06/2009 »), puis comparée à celle de la base.",
]

ARTICLES = [
    "« article L. 3121-2 du Code du travail », « art. 1240 C. civ. », « C. trav., art. "
    "L. 1152-1 », « articles L. 1234-1 et L. 1234-5 du même code ».",
    "Le texte cité entre guillemets juste à côté de l'article est comparé à toutes les "
    "versions de l'article. Base interrogée : Légifrance.",
    "Les articles sont lus à la « date des faits » si elle est donnée, sinon à la date du "
    "jour.",
]

NOT_CHECKED = [
    "les arrêts des cours d'appel et les jugements des tribunaux, cités par leur numéro RG "
    "(« CA Paris, 2 octobre 2013, RG 11/18803 ») : un RG n'est pas unique (chaque "
    "juridiction a sa propre numérotation, « 11/18803 » existe dans plusieurs cours), et "
    "ces décisions ne sont publiées en entier que depuis peu (2022 pour les cours d'appel en "
    "matière civile), seulement en partie avant",
    "les décisions des cours administratives d'appel (CAA) et des tribunaux administratifs "
    "(TA), à numéro mêlant chiffres et lettres (« 21BX01234 ») : les bases interrogeables "
    "sans installation n'en publient qu'une sélection",
    "les décisions européennes et internationales (CJUE, CEDH)",
    "les articles de lois et de décrets non codifiés (« article 22 de la loi du 6 juillet "
    "1989 ») : signalés, pas vérifiés",
    "les conventions collectives (en préparation)",
    "la chambre ou la formation qui a rendu la décision",
    "le sens d'une décision : si elle soutient l'argument pour lequel elle est citée",
]


def scope():
    """Liste de (titre, lignes)."""
    codes = []
    for title in TITLES:
        abbrev = abbreviations_of(title)
        codes.append(title + (f" ({', '.join(abbrev)})" if abbrev else ""))
    return [
        ("Décisions de justice reconnues", DECISIONS),
        ("Articles de codes reconnus", ARTICLES),
        (f"Les {len(TITLES)} codes reconnus, avec leurs abréviations", codes),
        ("Ce qui n'est PAS vérifié", NOT_CHECKED),
    ]


def not_checked_summary():
    """Version courte, pour la fin du rapport : le détail est dans l'onglet."""
    return ("arrêts de cours d'appel et jugements (numéros RG), décisions des CAA et TA, "
            "décisions européennes, lois et décrets non codifiés, conventions collectives, "
            "chambre, sens des décisions. Détail et raisons : onglet « Ce qui est vérifié »")
