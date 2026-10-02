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
from datetime import date

from . import links
from .articles import verdict_versions
from .extract import BLOCK_TITLES, MONTHS, in_words
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


RE_NATURE = re.compile(r"\s*(loi(?:\s+organique)?|ordonnance|d[ée]cret(?:-loi)?)\b", re.I)


def candidates(client, citation):
    """([(identifiant, nature, numéro, date)] des textes que la citation peut désigner, nombre
    de textes de cette nature que Légifrance a renvoyés mais dont le titre ne se lit pas :
    sans numéro, « Loi du 29 juillet 1881 », ou d'une forme imprévue ; ils peuvent être celui
    que vise la pièce ; {identifiant: titre} de tout ce que Légifrance a renvoyé)."""
    nature, number = citation["text_nature"], citation.get("text_number")
    if number:
        found = client.texts_by_number(number)
    else:
        found = client.texts_by_title(in_words(citation["text_date"]), nature)
    out, unread = [], 0
    for text_id, title in found:
        o = own(title)
        if not o:
            n = RE_NATURE.match(title)
            unread += bool(n and NATURES.get(" ".join(n.group(1).lower().split())) == nature)
            continue
        if o[0] != nature:
            continue
        if number and o[1] != number:
            continue
        if not number and o[2] != citation["text_date"]:
            continue
        out.append((text_id,) + o)
    return out, unread, dict(found)


def check_text_article(client, citation, day, texts):
    """(verdict, explication, date de début de la version retenue[, lien]).

    Un texte de ce nom dont le titre ne se lit pas (« Loi du 29 juillet 1881 », sans numéro)
    peut être celui que vise la pièce : on ne l'a pas fouillé, donc aucun verdict sûr, ni bleu
    ni « semble inventé » (audit du 02/10/2026)."""
    number = citation["number"]
    if citation.get("text_nature") in BLOCK_TITLES:
        return _check_block(client, citation, day, texts)
    found, unread, _ = candidates(client, citation)
    if not unread:
        return _check(client, citation, day, texts, found)
    note = (f"Légifrance a {unread} autre{'s' if unread > 1 else ''} texte"
            f"{'s' if unread > 1 else ''} de ce nom dont le titre ne se lit pas ici (sans "
            "numéro, ou d'une forme imprévue), où l'article n'a pas été cherché")
    if not found:
        return ("NOT_TESTED", f"{note} ; à vérifier à la main", None)
    verdict, why, start, *link = _check(client, citation, day, texts, found)
    return ("DOUBTFUL", f"{why} ; mais {note} : vérifiez lequel vise la pièce", start, *link)


def _check_block(client, citation, day, texts):
    """La Constitution, la Déclaration de 1789 : un seul texte, à l'identifiant fixe. L'article
    est cherché dans le texte tel qu'il était à la date de référence et tel qu'il est
    aujourd'hui. Absent des deux : il a pu exister entre-temps (les articles 90 à 93 de la
    Constitution, abrogés en 1995) ; à vérifier, jamais « semble inventé »."""
    number = citation["number"]
    name = "la " + BLOCK_TITLES[citation["text_nature"]]
    versions = client.block_article_versions(citation["text_id"], number,
                                             sorted({day, date.today().isoformat()}))
    if not versions and citation["text_nature"] == "DDHC":
        # Ses 17 articles n'ont jamais changé : un autre numéro n'a jamais existé.
        return verdict_versions(client, citation, day, texts, [], name)
    if not versions:
        return ("DOUBTFUL", f"aucun article {number} dans {name}, ni à la date de référence "
                "ni aujourd'hui : il ne semble pas exister, ou a été abrogé depuis longtemps ; "
                "à vérifier sur Légifrance", None)
    return verdict_versions(client, citation, day, texts, versions, name, links.text_article)


def _check(client, citation, day, texts, found):
    nature, number = citation["text_nature"], citation["number"]
    cited_text = label(nature, citation.get("text_number"), citation.get("text_date"))
    bare = re.sub(r"^(?:la |le |l')", "", cited_text)   # « loi n° 89-462 du 6 juillet 1989 »
    female = nature in FEMININE
    if not found:
        return ("TEXT_NOT_FOUND", f"aucun{'e' if female else ''} {bare} dans Légifrance : ce "
                "texte ne semble pas exister ; à vérifier", None)
    results = []
    for text_id, _, text_number, text_day in found:
        versions = client.text_article_versions(text_number, text_id, number)
        name = label(nature, text_number, text_day)
        result = verdict_versions(client, citation, day, texts, versions, name,
                                  links.text_article)
        if result[0] == "ARTICLE_NOT_FOUND":
            result = _published_only(client, citation, nature, text_number, text_day, name,
                                     result)
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


# Un texte de codification (« décret n° 2006-975 portant code des marchés publics ») reste
# « en vigueur » pour Légifrance alors que le code qu'il porte est abrogé depuis 2016 (relevé
# le 02/10/2026) : sa vigueur ne dit rien de celle du code.
RE_CODIFYING = re.compile(r"\b(?:portant|relative?\s+à\s+la\s+partie\s+\w+\s+du)\s+code\b",
                          re.I)


def check_text(client, citation, day):
    """Un texte cité en entier (« loi n° 91-647 du 10 juillet 1991 ») : existe-t-il, avec ce
    numéro, cette nature, cette date, et est-il en vigueur à la date de référence `day` ?
    (verdict, explication, date, lien).

    Par son numéro : rouge si aucun texte ne le porte ; orange s'il existe à une autre date
    ou sous une autre nature (un décret, pas une loi). Par sa date seule : s'il y en a
    plusieurs, on ne sait pas lequel est visé : non vérifié. Puis la vigueur, lue dans
    Légifrance à la date de référence : bleu seulement en vigueur ; abrogé ou pas encore en
    vigueur, orange (un texte abrogé cité comme applicable est une erreur typique). L'intitulé
    officiel est donné, pour que le lecteur le compare à celui de la pièce."""
    nature, number, cited_day = (citation["text_nature"], citation.get("text_number"),
                                 citation.get("text_date"))
    female = nature in FEMININE
    bare = re.sub(r"^(?:la |le |l')", "", label(nature, number, cited_day))
    found, unread, titles = candidates(client, citation)
    note = (f" ; Légifrance a aussi {unread} texte{'s' if unread > 1 else ''} de ce nom dont "
            "le titre ne se lit pas ici" if unread else "")

    def official(text_id):
        title = " ".join(titles.get(text_id, "").split())
        return f"« {title[:160]}{'...' if len(title) > 160 else ''} »" if title else ""

    if number:
        if not found:
            others = [o for o in (own(t) for t in titles.values()) if o]
            if others:
                o_nature, _, o_day = others[0]
                return ("DOUBTFUL", f"aucun{'e' if female else ''} {bare} dans Légifrance, mais "
                        f"{label(o_nature, number, o_day)} existe : vérifiez la nature du texte "
                        "cité", None)
            if unread:
                return ("NOT_TESTED", f"aucun{'e' if female else ''} {bare} lisible dans "
                        f"Légifrance{note} : à vérifier à la main", None)
            return ("TEXT_NOT_FOUND", f"aucun texte n° {number} dans Légifrance : ce texte ne "
                    "semble pas exister ; à vérifier", None)
        if len(found) > 1:
            return ("DOUBTFUL", f"plusieurs textes n° {number} dans Légifrance : "
                    + " ; ".join(label(*f[1:]) for f in found), None)
        text_id, _, _, text_day = found[0]
        name = label(nature, number, text_day)
        if cited_day and cited_day != text_day:
            pronoun = "elle est datée" if female else "il est daté"
            return ("WRONG_DATE", f"{name[0].upper()}{name[1:]} existe, mais {pronoun} du "
                    f"{text_day}, pas du {cited_day} : {official(text_id)}", None,
                    links.text(text_id))
        head = f"{name[0].upper()}{name[1:]} existe dans Légifrance : {official(text_id)}{note}"
    else:
        if not found:
            if unread:
                return ("NOT_TESTED", f"aucun{'e' if female else ''} {bare} lisible dans "
                        f"Légifrance{note} : à vérifier à la main", None)
            return ("TEXT_NOT_FOUND", f"aucun{'e' if female else ''} {NAMES[nature]} datée du "
                    f"{in_words(cited_day)} dans Légifrance : ce texte ne semble pas exister ; "
                    "à vérifier", None)
        if len(found) > 1 or unread:
            return ("NOT_TESTED", f"« {bare} » désigne {len(found) + unread} textes dans "
                    "Légifrance, on ne sait pas lequel est visé : "
                    + " ; ".join(f"{label(*f[1:])} {official(f[0])}" for f in found) + note,
                    None)
        text_id, _, text_number, text_day = found[0]
        name = label(nature, text_number, text_day)
        head = (f"un{'e' if female else ''} seul{'e' if female else ''} {NAMES[nature]} porte "
                f"cette date dans Légifrance, {name} : {official(text_id)}")
    return _in_force(client, text_id, day, head, titles.get(text_id, ""), female, unread)


def _in_force(client, text_id, day, head, title, female, unread):
    """Le verdict d'un texte trouvé, d'après son état à la date de référence."""
    link = links.text(text_id)
    state, since = client.text_state(text_id, day)
    e = "e" if female else ""
    if state == "Abrogé":
        return ("TEXT_NOT_IN_FORCE", f"{head} ; mais abrogé{e} le {since} : plus en vigueur le "
                f"{day}", None, link)
    if state != "Vigueur":
        return ("DOUBTFUL", f"{head} ; état dans Légifrance le {day} : « {state} » depuis le "
                f"{since} ; à vérifier", None, link)
    if day < since:
        return ("TEXT_NOT_IN_FORCE", f"{head} ; mais pas encore en vigueur le {day} : il l'est "
                f"depuis le {since}", None, link)
    if RE_CODIFYING.search(title):
        return ("DOUBTFUL", f"{head} ; en vigueur le {day}, mais c'est un texte de "
                "codification : sa vigueur ne dit pas celle du code qu'il porte ; vérifiez le "
                "code lui-même", since, link)
    if unread:
        return ("DOUBTFUL", f"{head} ; en vigueur le {day}, mais un autre texte de ce nom n'a "
                "pas pu être lu : vérifiez lequel vise la pièce", since, link)
    return ("TEXT_IN_FORCE", f"{head} ; en vigueur le {day} (depuis le {since})", since, link)


def check_texts(citations, client, day):
    """Vérifie une liste de textes cités en entier, un à un, à la demande."""
    for c in citations:
        try:
            yield check_text(client, c, day)
        except Unavailable as e:
            yield "ERROR", f"Légifrance n'a pas répondu ({e})", None


def _published_only(client, citation, nature, text_number, text_day, name, result):
    """Un article absent de la version consolidée, mais publié au Journal officiel dans ce
    même texte : le plus souvent un article qui en modifie un autre. Jamais « inventé »,
    jamais confirmé : à vérifier."""
    if not text_number:
        return result
    number = citation["number"]
    for title, article_id in client.jorf_articles(text_number, number):
        o = own(title)
        if o and o == (nature, text_number, text_day):
            return ("DOUBTFUL", f"l'article {number} de {name} existe dans sa version publiée "
                    "au Journal officiel, mais pas dans sa version consolidée : le plus souvent "
                    "un article qui modifie un autre texte, dont le contenu se lit dans le texte "
                    "modifié ; à vérifier", None, links.jorf_article(article_id))
    return result


def check_text_articles(citations, client, day):
    """Vérifie une liste de citations d'articles de lois, ordonnances et décrets, une à une, à la demande : chaque citation s'affiche dès qu'elle est vérifiée."""
    texts = {}
    for c in citations:
        try:
            yield check_text_article(client, c, day, texts)
        except Unavailable as e:
            yield "ERROR", f"Légifrance n'a pas répondu ({e})", None
