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
    "Cours d'appel et tribunaux judiciaires : « CA Paris, 2 octobre 2013, RG n° 11/18803 », "
    "« tribunal judiciaire de Périgueux, 18 décembre 2025, RG 23/00452 ». Un RG n'est pas "
    "unique (chaque juridiction a sa numérotation) : la juridiction doit être nommée dans la "
    "même phrase, sinon le RG est signalé sans être vérifié. Base interrogée : Judilibre.",
    "Judilibre ne publie largement ces décisions que depuis peu, et pas au même rythme partout. "
    "Le programme mesure, pour la juridiction citée, le nombre de décisions publiées par année. "
    "Une décision introuvable dans une période publiée en partie, ou datée de moins de six "
    "mois (délai de publication), sort « non vérifiable » : l'absence n'y prouve rien.",
    "Conseil constitutionnel : « Cons. const., 12 mai 2010, n° 2010-605 DC », « 2010-14/22 "
    "QPC ». Base interrogée : Légifrance.",
    "Tribunal des conflits : « T. confl., 17 juin 2013, n° C3911 », « TC, n° 4112 », « n° "
    "00012 » ; le Tribunal doit être nommé dans la même phrase. Base interrogée : Légifrance.",
    "Cour de justice et Tribunal de l'Union européenne : « CJUE, 6 octobre 2021, C-561/19 », "
    "« T-12/15 » (le Tribunal de l'Union doit alors être nommé dans la phrase). Base "
    "interrogée : CELLAR, de l'Office des publications de l'Union.",
    "CEDH : ses décisions sont repérées (« CEDH, n° 13134/87 ») et signalées « à vérifier à la "
    "main », avec le lien de la recherche dans HUDOC, la base de la Cour. La Cour n'autorise "
    "pas la recherche dans HUDOC par un programme, et ce programme ne la contourne pas. Un "
    "numéro de la forme « 13134/87 » est traité de même, même sans juridiction nommée : ce "
    "n'est pas un numéro du Conseil d'État.",
    "Une décision citée SANS numéro (« CE, Ass., 30 octobre 2009, Mme Perreux », « Cass. "
    "soc., 10 juillet 2013 ») est signalée « à vérifier à la main » : une juridiction suivie "
    "de près d'une date suffit à la repérer. Elle n'est pas cherchée : il faudrait envoyer le "
    "nom des parties, et ce programme n'envoie jamais rien de votre document.",
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
    "« Code minier » écrit sans précision désigne deux codes, l'ancien et celui de 2011 : "
    "l'article est cherché dans les deux. S'il existe dans les deux, le programme ne choisit "
    "pas, il montre les deux résultats et c'est au lecteur de dire lequel est visé.",
]

CONVENTIONS = [
    "« article 21 de la convention collective nationale des HCR (IDCC 1979) », « article "
    "25.1 de la CCN », « article 12.1 de ladite convention ».",
    "La convention est identifiée par son IDCC (quatre chiffres, sur le bulletin de paie), "
    "écrit dans la même phrase que la citation, ou donné dans le champ « IDCC ». Elle n'est "
    "jamais devinée à partir de son nom : la recherche par nom de Légifrance mélange "
    "conventions, avenants et accords.",
    "Seul le texte de base de la convention est vérifié. Le texte cité entre guillemets est "
    "comparé à toutes les versions de l'article, et le rapport dit si la version en vigueur "
    "est étendue. Base interrogée : Légifrance.",
]

NOT_CHECKED = [
    "un numéro RG sans cour d'appel ni tribunal judiciaire nommé dans la même phrase : un RG "
    "seul n'identifie pas une décision",
    "les tribunaux de commerce : Judilibre les publie depuis 2025, mais leur vérification "
    "n'est pas encore écrite. Leurs décisions sont signalées « à vérifier à la main »",
    "les conseils de prud'hommes : Judilibre ne les publie pas (leurs jugements frappés "
    "d'appel sont vérifiés, eux, au niveau de la cour d'appel). Signalés « à vérifier à la "
    "main »",
    "les décisions des cours administratives d'appel (CAA) et des tribunaux administratifs "
    "(TA) : pas encore vérifiées. Signalées « à vérifier à la main », jamais cherchées parmi "
    "celles du Conseil d'État",
    "les décisions citées sans numéro : signalées « à vérifier à la main », pas cherchées",
    "les décisions de la CEDH : la Cour n'autorise pas la recherche dans sa base par un "
    "programme. Elles sont signalées, avec le lien de la recherche, à ouvrir soi-même",
    "les articles de lois et de décrets non codifiés (« article 22 de la loi du 6 juillet "
    "1989 ») : signalés, pas vérifiés",
    "les avenants, accords et textes salariaux attachés aux conventions collectives : "
    "signalés, pas vérifiés (seul le texte de base l'est)",
    "un article de convention cité sans IDCC dans sa phrase, si l'IDCC n'est pas donné",
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
        ("Articles de conventions collectives reconnus", CONVENTIONS),
        (f"Les {len(TITLES)} codes reconnus, avec leurs abréviations", codes),
        ("Ce qui n'est PAS vérifié", NOT_CHECKED),
    ]


def not_checked_summary():
    """Version courte, pour la fin du rapport : le détail est dans l'onglet."""
    return ("RG sans juridiction nommée, tribunaux de commerce, prud'hommes, "
            "décisions des CAA et TA, "
            "décisions de la CEDH (lien fourni), lois et décrets non codifiés, avenants et accords "
            "attachés aux conventions, "
            "chambre, sens des décisions. Détail et raisons : onglet « Ce qui est vérifié »")
