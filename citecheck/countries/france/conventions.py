"""Vérifier un article de convention collective : la convention de cet IDCC existe-t-elle,
l'article existe-t-il dans son texte de base, était-il en vigueur à la date de référence,
et le texte cité est-il celui de cette version ?

L'IDCC
  C'est le numéro à quatre chiffres de la convention, sur le bulletin de paie. On ne le
  déduit jamais du nom de la convention : la recherche par nom de Légifrance mélange
  conventions, avenants et accords. S'il n'est pas écrit dans la phrase de la citation,
  l'utilisateur peut le donner (champ « IDCC »), sinon la citation n'est pas vérifiée.

LE TEXTE DE BASE SEULEMENT
  Une convention, c'est un texte de base et des dizaines de textes attachés (avenants,
  accords, salaires). On ne vérifie que le texte de base ; un article absent du texte de base
  peut figurer dans un avenant, et le rapport le dit.

LES NUMÉROS
  Légifrance écrit « 1er », « 25.1 », et parfois « 8 (1) » : le « (1) » est un renvoi de
  note, on l'ignore pour comparer.
"""
import re

from .articles import _period, quote_fragments, quote_in, version_at
from .legifrance import Unavailable

EXTENSION = {"VIGUEUR_ETEN": "version étendue", "VIGUEUR_NON_ETEN": "version non étendue"}


def _key(number):
    n = re.sub(r"\s*\(\d+\)\s*$", "", (number or "").strip())
    n = re.sub(r"^art(?:icle)?\.?\s*", "", n, flags=re.I)
    return "1" if n.lower() in ("1er", "1") else n.lower()


def check_convention_article(client, citation, day, default_idcc):
    idcc = citation.get("idcc") or default_idcc
    number = citation["number"]
    if not idcc:
        return ("NOT_TESTED", "IDCC non indiqué à côté de la citation : la convention ne peut "
                "pas être identifiée sans deviner ; donnez l'IDCC pour la vérifier", None)
    convention = client.convention(idcc)
    if convention is None:
        return ("CONVENTION_NOT_FOUND", f"l'IDCC {idcc} ne semble correspondre à aucune "
                "convention collective dans Légifrance ; à vérifier", None)
    title, text_ids = convention
    versions = sorted((a for a in client.convention_articles(text_ids)
                       if _key(a["num"]) == _key(number)), key=lambda a: a["debut"])
    source = "" if citation.get("idcc") else ", donné par l'utilisateur"
    if not versions:
        return ("ARTICLE_NOT_FOUND", f"aucun article {number} trouvé dans le texte de base de "
                f"« {title} » (IDCC {idcc}{source}) : il ne semble pas exister ; il peut figurer "
                "dans un avenant ou un accord attaché, non vérifiés", None)

    current = version_at(versions, day)
    if current is None:
        if day < versions[0]["debut"]:
            why = f"pas encore en vigueur le {day} : entre en vigueur le {versions[0]['debut']}"
        else:
            why = f"plus en vigueur le {day} : dernière version terminée le {versions[-1]['fin']}"
        return "ARTICLE_NOT_IN_FORCE", f"{why} (IDCC {idcc}{source})", None

    extension = EXTENSION.get(current["etat"])
    base = (f"en vigueur le {day} (IDCC {idcc}{source}, version {_period(current)}"
            + (f", {extension}" if extension else "")
            + (f" ; {len(versions)} versions" if len(versions) > 1 else "") + ")")
    fragments = quote_fragments(citation.get("quote") or "")
    if not fragments:
        return "ARTICLE_IN_FORCE", base, current["debut"]
    if quote_in(fragments, current["texte"]):
        return "ARTICLE_IN_FORCE", base + " ; texte cité conforme à cette version", current["debut"]
    for v in reversed([v for v in versions if v is not current]):
        if quote_in(fragments, v["texte"]):
            return ("ARTICLE_OTHER_VERSION",
                    f"le texte cité est celui de la version {_period(v)}, pas de celle en "
                    f"vigueur le {day} (IDCC {idcc}, version {_period(current)})", v["debut"])
    return ("QUOTE_NOT_FOUND",
            f"{base} ; mais le texte cité ne se retrouve dans aucune version de l'article "
            "(paraphrase, texte d'un avenant, ou texte inventé : à vérifier)", current["debut"])


def check_convention_articles(citations, client, day, default_idcc):
    results = []
    for c in citations:
        try:
            results.append(check_convention_article(client, c, day, default_idcc))
        except Unavailable as e:
            results.append(("ERROR", f"Légifrance n'a pas répondu ({e})", None))
    return results
