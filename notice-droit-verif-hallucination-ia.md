# notice-droit-verif-hallucination-ia

Notice destinée à une IA de code (ou à un développeur) qui doit faire tourner, compiler ou
faire évoluer ce programme. Pour les humains qui veulent seulement s'en servir : le README.

> **En cours de création.** Aucun exécutable n'est publié, et il ne le sera pas avant deux
> étapes : la vérification des arrêts de cours d'appel, puis un audit de sécurité du code. D'ici là, ne rien
> compiler ni distribuer.

## Ce que fait le programme

Il lit un document juridique, relève les citations de jurisprudence, d'articles de codes et
d'articles de conventions collectives, et demande aux bases officielles si chaque décision existe, et à quelle date ; si chaque
article existe, s'il était en vigueur à la date des faits, et si le texte cité entre
guillemets est bien celui de la version en vigueur à cette date. Il rend un rapport en texte (pour
un humain) et en JSON (pour qu'une IA corrige ses propres citations).

Il ne contient **aucune IA**, et c'est voulu : un programme qui consulte une base ne peut pas
inventer. Ne jamais y ajouter un modèle, ni pour extraire les citations, ni pour juger.

Pays couverts : France. Bases : ArianeWeb (Conseil d'État, sans clé), Judilibre (Cour de
cassation) et Légifrance (codes et conventions collectives), ces deux dernières avec le
compte PISTE de l'utilisateur.

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
| `citecheck/countries/france/` | extraction, bases et verdicts pour la France : `extract.py`, `sources.py` (ArianeWeb, Judilibre), `legifrance.py`, `articles.py` (codes), `conventions.py`, `codes.py` (noms et abréviations), `scope.py` (ce qui est vérifié) |
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

La fenêtre a trois onglets : « Vérifier un document », « Clés d'accès » et « Ce qui est
vérifié ». Les clés se donnent une fois dans le deuxième, qui s'ouvre d'office tant qu'il en
manque une ; elles vont dans le trousseau du système. Le troisième dit à l'utilisateur ce
que le programme reconnaît (formats de décisions, codes et abréviations) et ce qu'il ne
vérifie pas ; il est construit à partir des listes que l'extracteur utilise
(`countries/france/scope.py`), et `python -m citecheck --scope` l'affiche en ligne de
commande. En ligne de commande, on les passe par des variables
d'environnement.

| Variable | Sert à | Où la trouver |
|---|---|---|
| `PISTE_API_KEY` | Judilibre | la clé API de l'application PISTE |
| `PISTE_CLIENT_ID` | Légifrance | l'identifiant OAuth de la même application |
| `PISTE_CLIENT_SECRET` | Légifrance | le secret OAuth de la même application |

Pour les obtenir : créer un compte sur `piste.gouv.fr`, créer une application **en
production** (pas en bac à sable), l'abonner aux API Judilibre et Légifrance en acceptant
leurs conditions. Judilibre s'authentifie par la clé API, Légifrance par l'identifiant et le
secret : ce sont deux mécanismes, sur la même application. Sans clé, les citations
concernées sortent « non vérifiées », jamais en erreur de l'auteur.

**Où est la citation.** Chaque citation du rapport porte un extrait du texte qui
l'entoure, et sa page : exacte pour un PDF, approximative pour Word et LibreOffice (ils
enregistrent les sauts de page de leur dernier affichage), absente pour du texte brut. Une
citation placée dans une note de bas de page Word est signalée comme telle.

**La date des faits** (champ facultatif de l'onglet Vérifier, ou `--reference-date`) est la
date à laquelle les articles sont lus. Vide, c'est la date du jour, et le rapport le dit.

**L'IDCC** (champ facultatif, ou `--idcc`) identifie la convention collective des articles
cités sans IDCC dans leur phrase. Le programme ne devine jamais une convention à partir de
son nom ; sans IDCC, la citation sort « non vérifiée ». Seul le texte de base d'une
convention est vérifié, pas ses avenants ni ses accords attachés.

## Vérifier qu'on n'a rien cassé

```bash
.venv/bin/python -m unittest discover tests                  # hors réseau
.venv/bin/python -m citecheck --case cases/perigueux.json   # réseau, doit donner 4/4
.venv/bin/python -m citecheck --case cases/articles.json    # réseau, doit donner 7/7
.venv/bin/python -m citecheck --case cases/conventions.json # réseau, doit donner 6/6
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

**Le programme pointe ce qui est suspect, il ne donne pas d'avis.** Les verdicts constatent
(« ne semble pas publiée », « ne semble pas exister », « existe, mais à une autre date ») et
renvoient à une vérification ; ils ne disent jamais « faux » ni « inventé ». Toute
formulation nouvelle doit suivre cette règle.

## Compiler

**Les versions publiées sont compilées par GitHub**, automatiquement, pour Windows, macOS
et Linux. Elles apparaissent dans **Releases**, dans la colonne de droite de la page du
dépôt sur GitHub. Un utilisateur n'a rien à compiler : il télécharge le fichier de son
système. (Pas encore en place : voir l'encadré « En cours de création » en tête.)

Pour compiler soi-même, avec PyInstaller, **sur le système visé** : on compile pour
Windows sous Windows, pour macOS sous macOS.

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

- Vérifier les **arrêts de cours d'appel** cités par leur numéro RG : prévu, il faut relever
  la cour, le RG et la date ensemble (un RG n'est pas unique), et dire « non vérifiable »
  pour les périodes où la publication est partielle.
- Vérifier les articles des **lois et décrets** non codifiés (« article 22 de la loi du 6
  juillet 1989 ») et des **avenants** de conventions. Ils sont signalés dans les remarques du
  rapport, jamais devinés.
- Vérifier la **chambre** : une décision peut exister, à la bonne date, mais venir d'une
  chambre sans rapport avec le litige.
- Dire si la décision **soutient** l'argument. Aucune base ne le sait : c'est le travail du
  lecteur.
