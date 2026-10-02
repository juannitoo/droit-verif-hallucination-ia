r"""Sonde Légifrance : le bloc de constitutionnalité et ses articles.

CE QU'ELLE A MONTRÉ (02/10/2026), ET CE QUI EN DÉPEND
  - La recherche par titre ne trouve pas la Déclaration de 1789 ni le Préambule de 1946 :
    leurs identifiants sont fixes, relevés ici en lisant les textes voisins de la Constitution.
      LEGITEXT000006071194  Constitution du 4 octobre 1958
      LEGITEXT000006071192  Déclaration du 26 août 1789 des droits de l'homme et du citoyen
      LEGITEXT000006071193  Constitution du 27 octobre 1946 (dont son Préambule)
    C'est la table BLOCK de texts.py.
  - La version d'un texte à une date (/consult/legiPart) liste ses articles avec leur numéro
    (« 61-1 », « 16 ») ; la fiche d'un article (/consult/getArticle) donne ses versions :
    l'article 61-1 de la Constitution n'existe que depuis le 25 juillet 2008.
  - Un même numéro revient plusieurs fois dans la liste (« 77 » : ses versions abrogée et en
    vigueur, rangées dans plusieurs sections) ; la fiche de l'article les réunit toutes.
    Client.block_article_versions refuse de conclure si un identifiant lu n'est pas dans la
    fiche (deux articles différents sous un même numéro).
  - La Déclaration de 1789 a 17 articles, identiques à toutes les dates : un autre numéro n'a
    jamais existé (« semble inventé »). Pour la Constitution, un numéro absent aujourd'hui et à
    la date de référence a pu exister entre-temps (articles 90 à 93, abrogés en 1995) : « à
    vérifier ».

LANCER (avec vos propres identifiants PISTE, enregistrés dans le programme)
    .venv\Scripts\python probes\constitution.py
La sortie va dans probes\out\constitution.txt (non versionnée). Les clés sont lues dans le
trousseau et jamais affichées ; seuls partent des identifiants de textes publics."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from citecheck import keys                                          # noqa: E402
from citecheck.countries.france.legifrance import Client            # noqa: E402

TEXTS = {"LEGITEXT000006071194": ["61-1", "34", "1", "77"],
         "LEGITEXT000006071192": ["16", "6", "17"],
         "LEGITEXT000006071193": ["PREAMBULE", "1"]}
DAYS = ("2026-10-02", "2005-01-01")


def walk(node, out):
    """Les articles (num, id, état) d'une réponse legiPart, sections comprises."""
    for a in node.get("articles") or []:
        out.append((a.get("num"), a.get("id"), a.get("etat")))
    for s in node.get("sections") or []:
        walk(s, out)
    return out


def main(out):
    client = Client(keys.get("PISTE_CLIENT_ID"), keys.get("PISTE_CLIENT_SECRET"))
    for text_id, numbers in TEXTS.items():
        for day in DAYS:
            data = client._post("/consult/legiPart", {"textId": text_id, "date": day})
            arts = walk(data, [])
            print(f"\n===== {text_id} au {day} : « {data.get('title')} », état "
                  f"{data.get('jurisState')}, {len(arts)} article(s) : "
                  f"{[a[0] for a in arts]}", file=out)
            for num in numbers:
                hit = [a for a in arts if a[0] == num]
                print(f"  article {num} : {hit}", file=out)
                for _, article_id, _ in hit[:2]:
                    article = client._post("/consult/getArticle",
                                           {"id": article_id}).get("article") or {}
                    versions = [(v.get("id"), v.get("etat"), v.get("dateDebut"),
                                 v.get("dateFin")) for v in article.get("articleVersions") or []]
                    print(f"    versions : {json.dumps(versions)}", file=out)


if __name__ == "__main__":
    target = Path(__file__).resolve().parent / "out" / "constitution.txt"
    target.parent.mkdir(exist_ok=True)
    with open(target, "w", encoding="utf-8") as out:
        main(out)
    print(target)
