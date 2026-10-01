"""Vérifier un article de code : existe-t-il, était-il en vigueur à la date de référence, et
le texte cité entre guillemets est-il bien celui de cette version ?

LA DATE DE RÉFÉRENCE
  C'est la date à laquelle le texte doit être lu : en contentieux, la date des faits. Par
  défaut, la date du jour, et le rapport le dit. Un modèle cite souvent la version qu'il a
  apprise, périmée depuis : L. 3121-2 du Code du travail a été réécrit le 10/08/2016,
  l'article 1382 du Code civil a changé de contenu le 01/10/2016.

CE QUE VEUT DIRE « AUCUN ARTICLE »
  Légifrance consolide les articles des codes avec leurs versions successives. Zéro version
  pour un numéro est donc un signal fort, mais le rapport dit « ne semble pas exister » et
  renvoie à une vérification : on pointe ce qui est suspect, on ne tranche pas.

LA COMPARAISON DU TEXTE CITÉ
  On compare des morceaux, pas une phrase entière : les coupures « [...] » ou « (...) »
  découpent la citation, et chaque morceau d'au moins quatre mots doit se trouver tel quel
  dans la version. Casse, espaces et apostrophes ne comptent pas. Une paraphrase ne sera
  jamais retrouvée : le rapport le dit sans conclure à un faux.
"""
import re
import unicodedata

from . import links
from .codes import AMBIGUOUS, LABELS, SUCCESSION
from .legifrance import Unavailable

MIN_WORDS = 4
MAX_VERSIONS_READ = 80   # au-delà, le rapport dit combien il en a lu, jamais « aucune »
RE_CUT = re.compile(r"\[\s*(?:\.\.\.|…)\s*\]|\(\s*(?:\.\.\.|…)\s*\)|\.\.\.|…")


def _norm(text):
    text = unicodedata.normalize("NFKC", text).lower().replace("’", "'")
    text = re.sub(r"[«»“”\"]", " ", text)
    return " ".join(text.split())


def quote_fragments(quote):
    parts = [_norm(p).strip(" ,;:.") for p in RE_CUT.split(quote)]
    return [p for p in parts if len(p.split()) >= MIN_WORDS]


def quote_in(fragments, text):
    body = _norm(text)
    return bool(fragments) and all(f in body for f in fragments)


def version_at(versions, day):
    for v in versions:
        if v["debut"] <= day < (v["fin"] or "2999-01-01"):
            return v
    return None


def _period(v):
    fin = v["fin"]
    return f"du {v['debut']}" + ("" if not fin or fin.startswith("2999") else f" au {fin}")


def check_article(client, citation, day, texts):
    """(verdict, explication, date de début de la version retenue[, lien]). `texts` sert de
    cache {id de version: texte}.

    Un titre ambigu (AMBIGUOUS) est cherché dans chacun des codes qu'il peut désigner. Si
    l'article n'existe que dans l'un, on le dit ; s'il existe dans plusieurs, on ne choisit
    pas : DOUTEUX, avec ce qu'on a trouvé dans chacun."""
    code, number = citation["code"], citation["number"]
    if code in SUCCESSION:
        return _check_succession(client, citation, day, texts)
    if code not in AMBIGUOUS:
        return _check_one(client, citation, day, texts)
    found = [(t, _check_one(client, {**citation, "code": t}, day, texts))
             for t in AMBIGUOUS[code]]
    names = " et ".join(_the(t) for t, _ in found)
    head = f"« {code} » sans précision désigne deux codes, {names} : cherché dans les deux"
    hits = [(t, r) for t, r in found if r[0] != "ARTICLE_NOT_FOUND"]
    if not hits:
        return ("ARTICLE_NOT_FOUND", f"{head} ; aucun article {number} dans l'un ni dans "
                "l'autre, à aucune date : il ne semble pas exister ; à vérifier sur Légifrance",
                None)
    if len(hits) == 1:
        # Trouvé dans un seul : peut-être pas celui que vise la pièce. Jamais bleu (règle du
        # 02/10/2026 : un bleu doit être sûr) ; le lien mène à celui qu'on a trouvé.
        t, (verdict, why, start, *link) = hits[0]
        return ("DOUBTFUL", f"{head} ; l'article {number} n'existe que dans {_the(t)} : {why} ; "
                "vérifiez que c'est bien ce code que vise la pièce", start, *link)
    return ("DOUBTFUL", f"{head} ; l'article {number} existe dans les deux, à vous de dire "
            "lequel est visé : " + " ; ".join(f"dans {_the(t)}, {why}"
                                             for t, (_, why, *_) in hits), None)


IN_FORCE = ("ARTICLE_IN_FORCE", "ARTICLE_OTHER_VERSION", "QUOTE_NOT_FOUND")


def _check_succession(client, citation, day, texts):
    """Un code et ses éditions abrogées (SUCCESSION), du plus récent au plus ancien. Le
    premier où l'article est en vigueur à la date de référence est celui que le texte
    applique : on s'arrête là. Sinon on montre ce que chacun contient."""
    code, number = citation["code"], citation["number"]
    found = []
    for title in SUCCESSION[code]:
        result = _check_one(client, {**citation, "code": title}, day, texts)
        if result[0] in IN_FORCE:
            if not found and title == code:
                return result           # le cas courant : le code nommé, sans bruit
            head = f"« {code} » : "
            if found:
                head += (f"l'article {number} n'est pas en vigueur le {day} dans "
                         + ", ni dans ".join(_the(t) for t, _ in found) + " ; il l'est ")
            return (result[0], f"{head}dans {_the(title)} : {result[1]}", result[2],
                    *result[3:])
        found.append((title, result))
    hits = [(t, r) for t, r in found if r[0] != "ARTICLE_NOT_FOUND"]
    names = ", ".join(_the(t) for t, _ in found)
    if not hits:
        if any(r[0] == "NOT_TESTED" for _, r in found):
            return "NOT_TESTED", " ; ".join(f"{_the(t)} : {r[1]}" for t, r in found), None
        return ("ARTICLE_NOT_FOUND", f"aucun article {number} dans {names}, à aucune date : "
                "il ne semble pas exister ; à vérifier sur Légifrance", None)
    # « plus en vigueur le <jour> : abrogé le ... » : le jour est déjà dans la phrase de tête.
    said = [re.sub(rf"^plus en vigueur le {day} : ", "", r[1]) for _, r in hits]
    return ("ARTICLE_NOT_IN_FORCE", f"« {code} » : cherché dans {names} ; l'article {number} "
            f"n'est en vigueur le {day} dans aucun : "
            + " ; ".join(f"dans {_the(t)}, {w}" for (t, _), w in zip(hits, said)), None)


def _the(title):
    """« le Code minier (nouveau) », « l'ancien Code minier »."""
    label = LABELS.get(title, title)
    return ("l'" if label[0].lower() in "aeiouéè" else "le ") + label


def _check_one(client, citation, day, texts):
    code, number = citation["code"], citation["number"]
    codes = client.codes()
    if code not in codes:
        return "NOT_TESTED", f"{code} : code inconnu de Légifrance", None
    versions = client.versions(code, codes[code], number)
    return verdict_versions(client, citation, day, texts, versions, f"le {code}")


def verdict_versions(client, citation, day, texts, versions, where, link=links.code_article):
    """Le verdict d'un article d'après la liste COMPLÈTE de ses versions : existe-t-il, en
    vigueur à la date de référence, et le texte cité est-il celui de cette version ? `where` :
    « le Code civil », « la loi n° 89-462 ». `link` : l'adresse d'une version d'après son
    identifiant ; le lien mène à la version dont parle le verdict."""
    number = citation["number"]
    if not versions:
        return ("ARTICLE_NOT_FOUND",
                f"aucun article {number} trouvé dans {where}, à aucune date : il ne semble "
                "pas exister ; à vérifier sur Légifrance", None)

    current = version_at(versions, day)
    if current is None:
        first, last = versions[0], versions[-1]
        if day < first["debut"]:
            return ("ARTICLE_NOT_IN_FORCE",
                    f"pas encore en vigueur le {day} : entre en vigueur le {first['debut']}",
                    None, link(first["id"]))
        if last["fin"] and last["fin"] <= day:
            return ("ARTICLE_NOT_IN_FORCE",
                    f"plus en vigueur le {day} : abrogé ou déplacé le {last['fin']}", None,
                    link(last["id"]))
        return ("ARTICLE_NOT_IN_FORCE", f"aucune version en vigueur le {day}", None,
                link(last["id"]))

    history = ""
    if len(versions) > 1:
        history = f" ; {len(versions)} versions, dernière modification le {versions[-1]['debut']}"
    base = f"en vigueur le {day} (version {_period(current)}{history})"

    here = link(current["id"])
    fragments = quote_fragments(citation.get("quote") or "")
    if not fragments:
        return "ARTICLE_IN_FORCE", base, current["debut"], here

    def text_of(v):
        if v["id"] not in texts:
            texts[v["id"]] = client.text(v["id"])
        return texts[v["id"]]

    if quote_in(fragments, text_of(current)):
        return ("ARTICLE_IN_FORCE", base + " ; texte cité conforme à cette version",
                current["debut"], here)
    others = [v for v in versions if v is not current]
    read = others[-MAX_VERSIONS_READ:]
    for v in reversed(read):
        if quote_in(fragments, text_of(v)):
            return ("ARTICLE_OTHER_VERSION",
                    f"le texte cité est celui de la version {_period(v)}, pas de celle en "
                    f"vigueur le {day} (version {_period(current)})", v["debut"],
                    link(v["id"]))
    scope = (f"aucune des {len(versions)} versions de l'article" if len(read) == len(others)
             else f"aucune des {len(read) + 1} versions les plus récentes lues, sur "
                  f"{len(versions)}")
    return ("QUOTE_NOT_FOUND",
            f"{base} ; mais le texte cité ne se retrouve dans {scope} "
            "(paraphrase, ou texte inventé : à vérifier)", current["debut"], here)


def check_articles(citations, client, day, log):
    """Vérifie une liste de citations d'articles, une à une, à la demande : chaque citation s'affiche dès qu'elle est vérifiée."""
    texts = {}
    for c in citations:
        try:
            yield check_article(client, c, day, texts)
        except Unavailable as e:
            yield "ERROR", f"Légifrance n'a pas répondu ({e})", None
