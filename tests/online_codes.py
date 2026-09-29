"""Compare la liste embarquée des codes (codes.TITLES) à celle de Légifrance, en ligne.

Hors des tests unitaires : il faut le réseau et les identifiants PISTE (variables
d'environnement ou trousseau, comme le programme). À lancer avant chaque version :

    python3 tests/online_codes.py

Code de sortie 1 si Légifrance a des codes que la liste n'a pas : les ajouter à TITLES.
Un code de la liste absent de Légifrance est seulement signalé : on le garde, une IA peut
encore le citer."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from citecheck import keys                                          # noqa: E402
from citecheck.countries.france.codes import TITLES                 # noqa: E402
from citecheck.countries.france.legifrance import Client            # noqa: E402

cid, secret = keys.get("PISTE_CLIENT_ID"), keys.get("PISTE_CLIENT_SECRET")
if not (cid and secret):
    sys.exit("PISTE_CLIENT_ID / PISTE_CLIENT_SECRET absents")
online = set(Client(cid, secret).codes())
missing = sorted(online - set(TITLES))
gone = sorted(set(TITLES) - online)
print(f"Légifrance : {len(online)} codes en vigueur, liste embarquée : {len(TITLES)}")
for title in missing:
    print(f'  À AJOUTER : "{title}",')
for title in gone:
    print(f"  plus sur Légifrance (à garder) : {title}")
sys.exit(1 if missing else 0)
