"""Vérifier un article de loi, d'ordonnance ou de décret non codifié : « article 22 de la loi
n° 89-462 du 6 juillet 1989 », « article 14 de la loi du 10 juillet 1965 ».

LE TEXTE D'ABORD
  Par son numéro (« 89-462 ») : il désigne un seul texte dans Légifrance. Par sa date
  seule (« loi du 6 juillet 1989 ») : elle en désigne souvent plusieurs, neuf lois ce
  jour-là. On ne choisit pas : on cherche l'article dans chacune, et on dit dans laquelle
  on l'a trouvé ; s'il existe dans plusieurs, on les montre toutes et c'est au lecteur de
  dire laquelle est visée.

PUIS L'ARTICLE
  Comme pour un code : toutes ses versions, celle en vigueur à la date de référence, et le
  texte cité entre guillemets (articles.verdict_versions).

Seuls partent le numéro ou la date du texte, et le numéro de l'article. Jamais le texte du
document.
"""
import re

from . import links
from .articles import verdict_versions
from .extract import MONTHS, in_words
from .legifrance import Unavailable

# Le titre d'un texte commence par sa nature, son numéro et SA date : « Loi n° 89-462 du 6
# juillet 1989 tendant à ... ». Une autre date plus loin (« modifiant la loi n° 65-557 du 10
# juillet 1965 ») n'est pas la sienne.
RE_OWN = re.compile(r"^(?P<nature>loi(?:\s+organique)?|ordonnance|d[ée]cret(?:-loi)?)\s+"
                    r"n[°º]\s*(?P<num>\d{2,4}-\d{1,5})\s+du\s+(?P<day>1er|\d{1,2})\s+"
                    r"(?P<month>[a-zéû]+)\s+(?P<year>\d{4})", re.I)
NATURES = {"loi": "LOI", "loi organique": "LOI", "ordonnance": "ORDONNANCE",
           "décret": "DECRET", "decret": "DECRET", "décret-loi": "DECRET"}
NAMES = {"LOI": "loi", "ORDONNANCE": "ordonnance", "DECRET": "décret"}
FEMININE = {"LOI", "ORDONNANCE"}


def own(title):
    """(nature, numéro, date AAAA-MM-JJ) du texte d'après son titre, ou None."""
    m = RE_OWN.match(" ".join(title.split()))
    if not m or m.group("month").lower() not in MONTHS:
        return None
    day = 1 if m.group("day").lower() == "1er" else int(m.group("day"))
    iso = f"{m.group('year')}-{MONTHS[m.group('month').lower()]:02d}-{day:02d}"
    return NATURES.get(" ".join(m.group("nature").lower().split())), m.group("num"), iso


def label(nature, number=None, day=None):
    """« la loi n° 89-462 du 6 juillet 1989 », « l'ordonnance n° 2016-131 », « le décret du 17
    mars 1967 »."""
    name = NAMES[nature]
    text = ("l'" if name[0] in "aeiouéo" else "la " if nature in FEMININE else "le ") + name
    if number:
        text += f" n° {number}"
    if day:
        text += f" du {in_words(day)}"
    return text


def candidates(client, citation):
    """[(identifiant, nature, numéro, date)] des textes que la citation peut désigner."""
    nature, number = citation["text_nature"], citation.get("text_number")
    if number:
        found = client.texts_by_number(number)
    else:
        found = client.texts_by_title(in_words(citation["text_date"]), nature)
    out = []
    for text_id, title in found:
        o = own(title)
        if not o or o[0] != nature:
            continue
        if number and o[1] != number:
            continue
        if not number and o[2] != citation["text_date"]:
            continue
        out.append((text_id,) + o)
    return out


def check_text_article(client, citation, day, texts):
    """(verdict, explication, date de début de la version retenue[, lien])."""
    nature, number = citation["text_nature"], citation["number"]
    cited_text = label(nature, citation.get("text_number"), citation.get("text_date"))
    bare = re.sub(r"^(?:la |le |l')", "", cited_text)   # « loi n° 89-462 du 6 juillet 1989 »
    female = nature in FEMININE
    found = candidates(client, citation)
    if not found:
        return ("TEXT_NOT_FOUND", f"aucun{'e' if female else ''} {bare} dans Légifrance : ce "
                "texte ne semble pas exister ; à vérifier", None)
    results = []
    for text_id, _, text_number, text_day in found:
        versions = client.text_article_versions(text_number, text_id, number)
        name = label(nature, text_number, text_day)
        result = verdict_versions(client, citation, day, texts, versions, name,
                                  links.text_article)
        if result[0] == "ARTICLE_NOT_IN_FORCE" and day < text_day:
            # Le texte lui-même est postérieur aux faits : le dire, c'est plus fort que « pas
            # encore en vigueur » (une IA applique le droit actuel à des faits anciens).
            start = re.search(r"entre en vigueur le (\S+)$", result[1])
            result = ("ARTICLE_NOT_IN_FORCE", f"le texte n'existait pas encore le {day} : "
                      f"{name} lui est postérieur{'e' if nature in FEMININE else ''}"
                      + (f" ; son article {number} est en vigueur depuis le {start.group(1)}"
                         if start else ""), None, *result[3:])
        results.append((name, text_day, result))

    if len(results) == 1:
        name, text_day, result = results[0]
        cited_day = citation.get("text_date")
        if citation.get("text_number") and cited_day and cited_day != text_day:
            pronoun = "elle est datée" if female else "il est daté"
            return ("WRONG_DATE", f"{name[0].upper()}{name[1:]} existe, mais {pronoun} du "
                    f"{text_day}, pas du {cited_day} ; pour l'article {number} : {result[1]}",
                    result[2], *result[3:])
        return result

    head = (f"« {bare} » désigne {len(results)} textes dans Légifrance : l'article "
            f"{number} a été cherché dans chacun")
    hits = [(n, r) for n, _, r in results if r[0] != "ARTICLE_NOT_FOUND"]
    if not hits:
        return ("ARTICLE_NOT_FOUND", f"{head} ; aucun ne le contient, à aucune date : il ne "
                "semble pas exister ; à vérifier sur Légifrance", None)
    if len(hits) == 1:
        # Trouvé dans un seul : peut-être pas celui que vise la pièce. Jamais bleu (règle du
        # 02/10/2026 : un bleu doit être sûr) ; le lien mène à celui qu'on a trouvé.
        name, (verdict, why, start, *link) = hits[0]
        return ("DOUBTFUL", f"{head} ; il n'existe que dans {name} : {why} ; vérifiez que "
                "c'est bien ce texte que vise la pièce", start, *link)
    return ("DOUBTFUL", f"{head} ; il existe dans {len(hits)} d'entre eux, à vous de dire "
            "lequel est visé : " + " ; ".join(f"dans {n}, {r[1]}" for n, r in hits), None)


def check_text_articles(citations, client, day):
    """Vérifie une liste de citations d'articles de lois, ordonnances et décrets, une à une, à la demande : chaque citation s'affiche dès qu'elle est vérifiée."""
    texts = {}
    for c in citations:
        try:
            yield check_text_article(client, c, day, texts)
        except Unavailable as e:
            yield "ERROR", f"Légifrance n'a pas répondu ({e})", None
