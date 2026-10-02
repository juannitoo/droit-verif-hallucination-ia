r"""Sonde Légifrance : l'état d'un texte entier (en vigueur, abrogé, depuis quand).

CE QU'ELLE A MONTRÉ (02/10/2026), ET CE QUI EN DÉPEND
  - La recherche (/search, fonds LODA_ETAT) dit « VIGUEUR » pour l'ordonnance n° 2005-649,
    pourtant abrogée le 2016-04-01 : son « etat » et son « legalStatus » ne valent rien.
  - La version du texte à une date (/consult/legiPart) dit juste : « Abrogé » en 2026,
    « Vigueur » en 2010, avec la date de cet état (jurisDate). C'est ce que lit
    Client.text_state (legifrance.py), pour texts.check_text.
  - Le décret n° 2006-975 « portant code des marchés publics » est « Vigueur » en 2026, alors
    que le code qu'il porte est abrogé depuis 2016 : un texte de codification n'est jamais
    confirmé (texts.RE_CODIFYING).

LANCER (avec vos propres identifiants PISTE, enregistrés dans le programme)
    .venv\Scripts\python probes\text_state.py
La sortie va dans probes\out\text_state.txt (non versionnée). Les clés sont lues dans le
trousseau et jamais affichées ; seuls partent des numéros de textes publics."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from citecheck import keys                                          # noqa: E402
from citecheck.countries.france.legifrance import Client            # noqa: E402

TEXTS = [
    ("91-647", "loi relative à l'aide juridique : EN VIGUEUR"),
    ("2005-649", "ordonnance sur les marchés de certaines personnes publiques : ABROGÉE en 2016"),
    ("2006-975", "décret portant code des marchés publics : son code est ABROGÉ en 2016"),
]
DAYS = ("2026-10-02", "2010-01-01")


def short(value):
    """La réponse sans les longs textes : les clés, les dates, les états."""
    if isinstance(value, dict):
        return {k: short(v) for k, v in value.items()
                if k not in ("articles", "sections", "texte", "texteHtml", "nota", "notaHtml",
                             "visa", "signers", "prepWork", "dossiersLegislatifs")}
    if isinstance(value, list):
        return [short(v) for v in value[:3]] + (["..."] if len(value) > 3 else [])
    if isinstance(value, str) and len(value) > 200:
        return value[:200] + "..."
    return value


def main(out):
    client = Client(keys.get("PISTE_CLIENT_ID"), keys.get("PISTE_CLIENT_SECRET"))
    for number, what in TEXTS:
        print(f"\n===== {number} ({what})", file=out)
        results = client._text_search([("NUM", number)])
        print("--- /search LODA_ETAT :", file=out)
        print(json.dumps(short(results), ensure_ascii=False, indent=1), file=out)
        for text_id, _ in client.texts_by_number(number)[:1]:
            for day in DAYS:
                print(f"--- text_state({text_id}, {day}) : {client.text_state(text_id, day)}",
                      file=out)


if __name__ == "__main__":
    target = Path(__file__).resolve().parent / "out" / "text_state.txt"
    target.parent.mkdir(exist_ok=True)
    with open(target, "w", encoding="utf-8") as out:
        main(out)
    print(target)
