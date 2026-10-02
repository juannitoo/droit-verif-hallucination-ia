r"""Sonde Légifrance : les versions d'un article de code, fiche par fiche.

CE QU'ELLE A MONTRÉ (02/10/2026), ET CE QUI EN DÉPEND
  - Un code recodifié a eu deux articles DIFFÉRENTS sous le même numéro : CESEDA L611-1
    (l'ancien jusqu'au 2021-05-01, le nouveau depuis), consommation L212-1 (2016). La
    recherche montre les versions des deux ; la fiche (/consult/getArticle) d'une version ne
    liste que celles de son article. Le programme ne lisait qu'une fiche et abandonnait
    (« liste des versions incohérente »). Client.versions (legifrance.py) lit maintenant
    toutes les fiches, et refuse de choisir si deux articles différents sont en vigueur le
    même jour.
  - CGI article 39 : une seule fiche, 83 versions, dont certaines se chevauchent (effets
    différés). Ce chevauchement-là n'empêche rien : version_at (articles.py) choisit.

LANCER (avec vos propres identifiants PISTE, enregistrés dans le programme)
    .venv\Scripts\python probes\recodified_articles.py
La sortie va dans probes\out\recodified_articles.txt (non versionnée). Les clés sont lues
dans le trousseau et jamais affichées ; seuls partent des numéros d'articles publics."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from citecheck import keys                                          # noqa: E402
from citecheck.countries.france.legifrance import Client            # noqa: E402

ARTICLES = [
    ("Code de l'entrée et du séjour des étrangers et du droit d'asile", "L611-1"),
    ("Code de la consommation", "L212-1"),
    ("Code général des impôts", "39"),
]


def main(out):
    client = Client(keys.get("PISTE_CLIENT_ID"), keys.get("PISTE_CLIENT_SECRET"))
    codes = client.codes()
    for title, number in ARTICLES:
        print(f"\n===== {title}, {number}", file=out)
        found = client._search_versions(title, codes[title], number)
        print(f"recherche : {len(found)} version(s)", json.dumps(found, ensure_ascii=False),
              file=out)
        read = set()
        for f in found:
            if f["id"] in read:
                continue
            article = client._post("/consult/getArticle", {"id": f["id"]}).get("article") or {}
            versions = article.get("articleVersions") or []
            read |= {v.get("id") for v in versions}
            print(f"  fiche {f['id']} (article {article.get('cid')}) : {len(versions)} "
                  f"version(s), de {min(v.get('dateDebut') for v in versions)} "
                  f"à {max(v.get('dateFin') for v in versions)} (millisecondes)", file=out)
        try:
            kept = client.versions(title, codes[title], number)
            print(f"  versions() : {len(kept)} version(s), de {kept[0]['debut']} à "
                  f"{kept[-1]['fin']}", file=out)
        except Exception as e:
            print(f"  versions() : {type(e).__name__} : {e}", file=out)


if __name__ == "__main__":
    target = Path(__file__).resolve().parent / "out" / "recodified_articles.txt"
    target.parent.mkdir(exist_ok=True)
    with open(target, "w", encoding="utf-8") as out:
        main(out)
    print(target)
