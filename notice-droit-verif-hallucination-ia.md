# notice-droit-verif-hallucination-ia

Notice destinée à une IA de code (ou à un développeur) qui doit faire tourner, compiler ou
faire évoluer ce programme. Pour les humains qui veulent seulement s'en servir : le README.

> **En cours de création.** Aucun exécutable n'est publié, et il ne le sera pas avant deux
> étapes : la vérification des articles de codes et de conventions collectives
> (Légifrance, fonds LEGI et KALI), puis un audit de sécurité du code. D'ici là, ne rien
> compiler ni distribuer.

## Ce que fait le programme

Il lit un document juridique, relève les citations de jurisprudence, et demande aux bases
officielles si chaque décision existe, et à quelle date. Il rend un rapport en texte (pour
un humain) et en JSON (pour qu'une IA corrige ses propres citations).

Il ne contient **aucune IA**, et c'est voulu : un programme qui consulte une base ne peut pas
inventer. Ne jamais y ajouter un modèle, ni pour extraire les citations, ni pour juger.

Pays couverts : France. Bases : ArianeWeb (Conseil d'État, sans clé) et Judilibre (Cour de
cassation, clé PISTE de l'utilisateur).

## Arborescence

| Chemin | Rôle |
|---|---|
| `run.py` | point d'entrée de l'exécutable |
| `citecheck/__main__.py` | ligne de commande ; sans argument, ouvre la fenêtre |
| `citecheck/gui.py` | la fenêtre (tkinter) |
| `citecheck/engine.py` | document → citations → rapport |
| `citecheck/reader.py` | texte d'un .pdf .docx .odt .txt .md, notes de bas de page comprises |
| `citecheck/keys.py` | clés : variable d'environnement, sinon trousseau du système |
| `citecheck/report.py` | rapport texte et JSON |
| `citecheck/locales/fr.py` | tous les textes affichés ; une langue = un fichier |
| `citecheck/countries/france/` | extraction, bases et verdicts pour la France |
| `cases/perigueux.json` | banc d'essai : un cas réel dont le tribunal a donné la réponse |
| `tests/` | tests hors réseau |

**Langues du code.** Noms de fichiers, de fonctions, de variables, codes de verdict, clés du
JSON et options de la ligne de commande : en anglais. Commentaires du tronc commun : en
anglais. Commentaires et explications d'un pays (`countries/<pays>/`) : dans la langue du
pays. Textes affichés : dans `locales/`.

Les codes de verdict (`CONFIRMED`, `WRONG_DATE`, `NOT_PUBLISHED`...) restent des
identifiants anglais, les mêmes dans toutes les langues, pour qu'un programme ou une IA lise
le JSON sans connaître la langue du rapport. Un humain ne les voit jamais : le rapport, le
journal et le champ `verdict_label` du JSON portent le libellé traduit.

## Lancer depuis les sources

Python 3.10 ou plus récent, avec tkinter.

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt        # Windows : .venv\Scripts\pip
.venv/bin/python -m citecheck                    # la fenêtre
.venv/bin/python -m citecheck conclusions.pdf    # la ligne de commande
.venv/bin/python -m citecheck conclusions.pdf --json
```

La fenêtre a deux onglets : « Vérifier un document » et « Clés d'accès ». La clé Judilibre
se donne une fois dans le second, qui s'ouvre d'office tant qu'aucune clé n'est enregistrée ;
elle va dans le trousseau du système. En ligne de commande, on la passe par la variable
d'environnement `PISTE_API_KEY`. Pour l'obtenir : créer un compte sur
`piste.gouv.fr`, créer une application **en production** (pas en bac à sable), l'abonner à
l'API Judilibre en acceptant ses conditions, puis copier la clé API de l'application. Sans
clé, les décisions judiciaires sortent « non vérifiées », jamais en erreur de l'auteur.

## Vérifier qu'on n'a rien cassé

```bash
.venv/bin/python -m unittest discover tests                  # hors réseau
.venv/bin/python -m citecheck --case cases/perigueux.json   # réseau, doit donner 4/4
```

## Les trois règles, à ne jamais affaiblir

1. **Chaque base se prouve avant de juger.** Des numéros réels doivent être trouvés, des
   numéros inventés ne doivent rien donner (les témoins, dans `countries/france/__init__.py`).
   Si une base rate ses contrôles, ses citations sortent en `NOT_TESTED`.
2. **Jamais « introuvable ».** Les bases publiques ne contiennent pas toutes les décisions :
   zéro résultat veut dire « aucune décision publiée ne correspond ».
3. **Une base injoignable ne donne jamais un verdict négatif.** Sinon une panne réseau ou
   une clé absente passerait pour une erreur de l'auteur du texte.

Et une quatrième qui les résume : **le rapport ne dit jamais plus que ce qui a été
contrôlé.** Une date n'est « conforme » que si la base a la décision elle-même à cette date.

## Compiler

Le programme se compile avec PyInstaller, **sur le système visé** : on compile pour Windows
sous Windows, pour macOS sous macOS.

```bash
.venv/bin/pip install pyinstaller
.venv/bin/pyinstaller --onefile --windowed --name droit-verif \
    --collect-submodules keyring run.py
```

Le résultat est dans `dist/`.

**macOS** : utiliser un Python qui fournit tkinter (celui de python.org, ou Homebrew avec
`brew install python-tk`). PyInstaller produit `dist/droit-verif.app`. Il n'est pas signé :
au premier lancement, clic droit sur l'application puis « Ouvrir », ou
`xattr -dr com.apple.quarantine dist/droit-verif.app`. La clé va dans le Trousseau.

**Windows** : `dist\droit-verif.exe`. Non signé : Windows affiche un avertissement au premier
lancement (« Informations complémentaires », puis « Exécuter quand même »). La clé va dans le
Gestionnaire d'identification.

La licence permet de compiler pour son propre usage, pas de redistribuer le résultat.

## Ajouter un pays

Créer `citecheck/countries/<pays>/` qui expose `NAME`, `KEYS`, `KEY_HELP_URL`,
`extract(text)` et `check(citations, keys, log)` (voir `countries/__init__.py`), puis
l'ajouter à `COUNTRIES`.
Les autres pays n'ont pas à changer. Il faut des témoins pour chaque base, et un cas réel
dans `cases/`.

## Ce que le programme ne sait pas encore faire

- Vérifier les **articles** de loi ou de convention collective, et leur version en vigueur à
  une date donnée (Légifrance, fonds LEGI et KALI).
- Vérifier la **chambre** : une décision peut exister, à la bonne date, mais venir d'une
  chambre sans rapport avec le litige.
- Dire si la décision **soutient** l'argument. Aucune base ne le sait : c'est le travail du
  lecteur.
