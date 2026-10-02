r"""Sonde Légifrance : un article absent de la version consolidée d'une loi.

CE QU'ELLE A MONTRÉ (02/10/2026), ET CE QUI EN DÉPEND
  - « article 1er de la loi n° 2014-366 du 24 mars 2014 » (ALUR) : aucun article 1 dans la
    version consolidée (fonds LODA_ETAT), alors que les articles 2, 3, 153 y sont. Il est
    dans la version publiée au Journal officiel (fonds JORF) : « I. ― Le chapitre Ier du
    titre Ier de la loi n° 89-462 du 6 juillet 1989 ... ». C'est un article qui en modifie un
    autre. Le programme disait « ne semble pas exister » ; il dit maintenant « publié au
    Journal officiel, pas dans la version consolidée : à vérifier » (Client.jorf_articles,
    texts._published_only).
  - La recherche JORF par numéro renvoie aussi d'autres textes de même numéro (« Décision
    n° 2014-366 du 16 juillet 2014 » du CSA) : on ne garde que le texte de même nature, même
    numéro et même date.

LANCER (avec vos propres identifiants PISTE, enregistrés dans le programme)
    .venv\Scripts\python probes\journal_officiel.py
La sortie va dans probes\out\journal_officiel.txt (non versionnée). Les clés sont lues dans
le trousseau et jamais affichées ; seuls partent des numéros de textes publics."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from citecheck import keys                                          # noqa: E402
from citecheck.countries.france.legifrance import Client            # noqa: E402

TEXT, ARTICLES = "2014-366", ("1", "2", "3")


def main(out):
    client = Client(keys.get("PISTE_CLIENT_ID"), keys.get("PISTE_CLIENT_SECRET"))
    found = client.texts_by_number(TEXT)
    print(f"texts_by_number({TEXT}) : {found}", file=out)
    for number in ARTICLES:
        print(f"\n===== article {number}", file=out)
        print("version consolidée :",
              client.text_article_versions(TEXT, found[0][0], number)[:3], file=out)
        print("Journal officiel :", client.jorf_articles(TEXT, number), file=out)


if __name__ == "__main__":
    target = Path(__file__).resolve().parent / "out" / "journal_officiel.txt"
    target.parent.mkdir(exist_ok=True)
    with open(target, "w", encoding="utf-8") as out:
        main(out)
    print(target)
