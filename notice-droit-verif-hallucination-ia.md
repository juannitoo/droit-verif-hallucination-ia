# notice-droit-verif-hallucination-ia

Notice destinée à une IA de code (ou à un développeur) qui doit faire tourner, compiler ou
faire évoluer ce programme. Pour les humains qui veulent seulement s'en servir : le README.

> **En cours de création.** Aucun exécutable n'est publié. L'audit de sécurité est fait,
> en deux passes par deux modèles différents, et corrigé. Reste, avant publication, une
> vérification sur des cas réels de citations inventées. D'ici là, ne rien compiler pour
> d'autres ni distribuer.

## Ce que fait le programme

Il lit un document juridique, relève les citations de jurisprudence, d'articles de codes et
d'articles de conventions collectives, et demande aux bases officielles si chaque décision existe, et à quelle date ; si chaque
article existe, s'il était en vigueur à la date des faits, et si le texte cité entre
guillemets est bien celui de la version en vigueur à cette date. Il rend un rapport en texte (pour
un humain, en tableau, avec le lien de ce qui a été trouvé ; en .txt ou en PDF), en JSON (pour qu'une IA corrige
ses propres citations) et, pour un PDF, une copie annotée du document.

Il ne contient **aucune IA**, et c'est voulu : un programme qui consulte une base ne peut pas
inventer. Ne jamais y ajouter un modèle, ni pour extraire les citations, ni pour juger.

Pays couverts : France. Bases : ArianeWeb (Conseil d'État, sans clé), Judilibre (Cour de
cassation, cours d'appel, tribunaux judiciaires) et Légifrance (codes, conventions
collectives, Conseil constitutionnel, Tribunal des conflits), ces deux dernières avec le
compte PISTE de l'utilisateur ; CELLAR, le dépôt public de l'Office des publications de
l'Union, par son API REST (Cour de justice et Tribunal de l'UE, sans clé). Pas par son
point d'accès SPARQL : trop instable (mesuré, détail dans `other_courts.py`).

**La CEDH n'est pas interrogée, et ne doit pas l'être.** Sa base HUDOC est derrière un défi
Cloudflare (HTTP 403 sur sa recherche comme sur son `robots.txt`, constaté le 29/09/2026) :
la Cour n'autorise pas la recherche par un programme. Ne jamais contourner ce refus
(navigateur piloté, en-têtes imités) : ce programme est fait pour des avocats, il doit
s'utiliser sans embrouille. Le rapport donne le lien de la recherche HUDOC, que l'avocat
ouvre dans son navigateur.

## Arborescence

| Chemin | Rôle |
|---|---|
| `run.py` | point d'entrée de l'exécutable |
| `citecheck/__main__.py` | ligne de commande ; sans argument, ouvre la fenêtre |
| `citecheck/gui.py` | la fenêtre (tkinter) |
| `citecheck/engine.py` | document → citations → rapport |
| `citecheck/reader.py` | texte d'un .pdf .docx .odt .txt .md, notes de bas de page comprises |
| `citecheck/keys.py` | clés : variable d'environnement, sinon trousseau du système |
| `citecheck/report.py` | rapport texte (tableau) et JSON ; la couleur de chaque verdict |
| `citecheck/report_pdf.py` | le rapport en PDF : tableau aux couleurs des verdicts, liens cliquables (fpdf2, police Roboto de customtkinter) |
| `citecheck/annotate.py` | le PDF annoté : chaque citation surlignée de la couleur de son verdict, cliquable (pdfminer.six pour la place des lettres) |
| `citecheck/locales/fr.py` | tous les textes affichés ; une langue = un fichier |
| `citecheck/countries/france/` | extraction, bases et verdicts pour la France : `extract.py`, `sources.py` (ArianeWeb, Judilibre), `legifrance.py`, `articles.py` (codes), `texts.py` (lois, ordonnances, décrets non codifiés), `conventions.py`, `links.py` (le lien de ce qui a été trouvé, sur un modèle fixe), `lower_courts.py` (cours d'appel, tribunaux judiciaires et de commerce), `other_courts.py` (CAA, base locale, Conseil constitutionnel, Tribunal des conflits, Union européenne, lien CEDH), `codes.py` (noms et abréviations), `scope.py` (ce qui est vérifié) |
| `citecheck/http.py` | le seul point de sortie réseau, qui refuse toute redirection (une redirection emporterait les clés) |
| `cases/` | bancs d'essai dont la réponse est connue : `perigueux.json` (cas réel jugé), `articles.json`, `conventions.json`, `lower_courts.json`, `other_courts.json`, `abrogated_codes.json` et `abrogated_codes_2010.json` (codes abrogés, lus à deux dates), `cgi.json` (suffixes et annexes du CGI), `commercial_courts.json`, `chambers.json`, `texts.json` et `texts_2010.json` |
| `tests/` | tests hors réseau |
| `probes/` | sondes Légifrance : ce que la base renvoie vraiment, quand le code en dépend (état d'un texte entier, articles d'un code recodifié, article publié au seul Journal officiel) ; chacune dit ce qu'elle a montré et quel code en dépend |

**Langues du code.** Noms de fichiers, de fonctions, de variables, codes de verdict, clés du
JSON et options de la ligne de commande : en anglais. Commentaires du tronc commun : en
anglais. Commentaires et explications d'un pays (`citecheck/countries/<pays>/`) : dans la langue du
pays. Textes affichés : dans `locales/`.

Les codes de verdict (`CONFIRMED`, `WRONG_DATE`, `NOT_PUBLISHED`...) restent des
identifiants anglais, les mêmes dans toutes les langues, pour qu'un programme ou une IA lise
le JSON sans connaître la langue du rapport. Un humain ne les voit jamais : le rapport, le
journal et le champ `verdict_label` du JSON portent le libellé traduit.

## Lancer depuis les sources

Python 3.10 ou plus récent, avec tkinter.

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m citecheck                    # la fenêtre
.venv/bin/python -m citecheck conclusions.pdf    # la ligne de commande
.venv/bin/python -m citecheck conclusions.pdf --json
.venv/bin/python -m citecheck conclusions.pdf --pdf  # + conclusions-citations-verifiees.pdf
.venv/bin/python -m citecheck conclusions.docx -o rapport.pdf  # le rapport en PDF
```

Sous Windows (PowerShell), les exécutables du venv sont dans `.venv\Scripts\` :

```powershell
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python -m citecheck                    # la fenêtre
.venv\Scripts\python -m citecheck conclusions.pdf    # la ligne de commande
.venv\Scripts\python -m citecheck conclusions.pdf --json
.venv\Scripts\python -m citecheck conclusions.pdf --pdf  # + conclusions-citations-verifiees.pdf
.venv\Scripts\python -m citecheck conclusions.docx -o rapport.pdf  # le rapport en PDF
```

La fenêtre a trois onglets : « Vérifier un document », « Clés d'accès » et « Ce qui est
vérifié ». Les clés se donnent une fois dans le deuxième, qui s'ouvre d'office tant qu'il en
manque une ; elles vont dans le trousseau du système. Le troisième dit à l'utilisateur ce
que le programme reconnaît (formats de décisions, codes et abréviations) et ce qu'il ne
vérifie pas ; il est construit à partir des listes que l'extracteur utilise
(`citecheck/countries/france/scope.py`), et `python -m citecheck --scope` l'affiche en ligne
de commande.

En ligne de commande, les clés se passent par des variables d'environnement.

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

**Le PDF annoté** (bouton « PDF annoté », ou `--pdf`) : une copie du document, nommée
`<nom>-citations-verifiees.pdf`, où chaque citation est surlignée : **bleu** confirmée,
**orange** à vérifier (autre date, autre chambre, autre version, texte cité non retrouvé :
tout ce qui est douteux, jamais confirmé), **rouge** semble inventée, **gris avec « ? »**
non vérifiée (clé absente, base en panne, période non couverte). Un clic ouvre ce qui a
été trouvé ; le survol donne le verdict et son explication. Une citation reprise plus loin
est surlignée à chaque reprise. Le document d'origine n'est jamais modifié : un PDF ne se
recompose pas, les couleurs sont des annotations posées par-dessus, que tout lecteur de PDF
peut masquer.

**Enregistrer sans extraits** (case cochée par défaut ; en ligne de commande, c'est aussi le défaut, `--with-excerpts` pour les garder) : le rapport
enregistré ne garde que numéros, dates et verdicts, sans aucune phrase du document. C'est
ce qu'il faut pour le donner à une IA en ligne sans y faire passer des noms ou des faits
couverts par le secret professionnel.

**La date des faits** (champ facultatif de l'onglet Vérifier, ou `--reference-date`) est la
date à laquelle les articles sont lus. Vide, c'est la date du jour, et le rapport le dit.

**Cours d'appel et tribunaux judiciaires.** Un RG n'est pas unique : il n'est vérifié que
si la juridiction est nommée dans la même phrase. Judilibre ne publie largement ces
décisions que depuis peu, et pas au même rythme partout : le programme mesure la couverture
de la juridiction citée (`/stats`, année par année) au lieu de l'écrire en dur, et une
décision introuvable dans une période publiée en partie, ou de moins de six mois, sort
« non vérifiable ». Détail et mesures du 29/09/2026 : `citecheck/countries/france/lower_courts.py`.

**L'IDCC** (champ facultatif, ou `--idcc`) identifie la convention collective des articles
cités sans IDCC dans leur phrase. Le programme ne devine jamais une convention à partir de
son nom ; sans IDCC, la citation sort « non vérifiée ». Seul le texte de base d'une
convention est vérifié, pas ses avenants ni ses accords attachés.

**La base locale des décisions administratives** (facultatif ; onglet « Clés d'accès », ou
variable `ADMIN_LOCAL_BASE_URL`). Les tribunaux administratifs ne sont dans aucune base
interrogeable en ligne : Légifrance n'en a aucun, et opendata.justice-administrative.fr, qui
les publie tous depuis juin 2022 (et les CAA depuis mars 2022), ne les diffuse qu'en
archives ZIP mensuelles, sans API (article XI de ses conditions d'utilisation ; son
interface de recherche interne ne doit pas être utilisée). Quelqu'un peut installer une
base locale à partir de ces archives ; le programme l'interroge si elle respecte ce contrat :

```
GET <adresse>/coverage
    -> {"CAA": "2022-03-01", "TA": "2022-06-01"}     première date couverte en entier
GET <adresse>/decisions?court=TA&number=2301234      court : TA ou CAA
    -> {"decisions": [{"number": "2301234", "date": "2023-05-12"}]}
```

Comme toute base, elle passe ses témoins avant de juger (`LOCAL_REAL`, `LOCAL_FAKE` dans
`countries/france/__init__.py`) : une base qui répond oui à tout est écartée. Seuls le type
de juridiction et le numéro lui sont envoyés.

## Vérifier qu'on n'a rien cassé

```bash
.venv/bin/python -m unittest discover tests                  # hors réseau
.venv/bin/python -m citecheck --case cases/perigueux.json   # réseau, doit donner 4/4
.venv/bin/python -m citecheck --case cases/articles.json    # réseau, doit donner 9/9
.venv/bin/python -m citecheck --case cases/conventions.json # réseau, doit donner 6/6
.venv/bin/python -m citecheck --case cases/lower_courts.json # réseau, doit donner 4/4
.venv/bin/python -m citecheck --case cases/other_courts.json # réseau, doit donner 13/13
.venv/bin/python -m citecheck --case cases/abrogated_codes.json      # réseau, 7/7
.venv/bin/python -m citecheck --case cases/abrogated_codes_2010.json # réseau, 3/3
.venv/bin/python -m citecheck --case cases/cgi.json                  # réseau, 7/7
.venv/bin/python -m citecheck --case cases/commercial_courts.json    # réseau, 9/9
.venv/bin/python -m citecheck --case cases/chambers.json             # réseau, 6/6
.venv/bin/python -m citecheck --case cases/texts.json                # réseau, 7/7
.venv/bin/python -m citecheck --case cases/texts_2010.json           # réseau, 2/2
```

Quand une réponse de Légifrance surprend, une sonde de `probes/` la montre telle quelle, avec vos propres identifiants (réseau ; la sortie va dans `probes/out/`, non versionné) :

```bash
.venv/bin/python probes/text_state.py            # vigueur d'un texte entier
.venv/bin/python probes/recodified_articles.py   # un numéro, plusieurs articles
.venv/bin/python probes/journal_officiel.py      # article absent de la version consolidée
```

## Les trois règles, à ne jamais affaiblir

1. **Chaque base se prouve avant de juger.** Des numéros réels doivent être trouvés, des
   numéros inventés ne doivent rien donner (les témoins, dans `citecheck/countries/france/__init__.py`).
   Si une base rate ses contrôles, ses citations sortent en `NOT_TESTED`.
2. **Jamais « introuvable ».** Les bases publiques ne contiennent pas toutes les décisions :
   zéro résultat veut dire « ne semble pas publiée ». Et quand la base ne couvre la période
   qu'en partie (mesuré, pas supposé), zéro résultat veut dire « non vérifiable ».
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

Pour compiler soi-même, avec PyInstaller **6 ou plus récent** (les versions antérieures à
5.13.1 ont une faille en mode `--onefile` sous Windows), **sur le système visé** : on
compile pour Windows sous Windows, pour macOS sous macOS.

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
`extract(text)` et `check(citations, keys, log, options)` (voir `citecheck/countries/__init__.py`), puis
l'ajouter à `COUNTRIES`.
Les autres pays n'ont pas à changer. Il faut des témoins pour chaque base, et un cas réel
dans `cases/`.

## Un nouveau code chez Légifrance

Personne ne fait de veille, et c'est voulu : un cron sur un VPS disparaît avec le VPS, et
GitHub coupe les tâches planifiées d'un dépôt public après 60 jours sans commit. Ce qui
tient sans personne :

- `prepare()` (`countries/france/__init__.py`) demande la liste des codes à Légifrance avant
  chaque extraction et ajoute les titres inconnus (`codes.learn`). Le nouveau code est
  reconnu en toutes lettres chez tout utilisateur qui a ses identifiants PISTE.
- Le rapport le dit, et invite l'utilisateur à le signaler dans les issues.

Quand un signalement arrive : ajouter le titre à `TITLES` et son abréviation d'usage à
`ABBREVIATIONS` dans `codes.py` (jamais un sigle ambigu), passer le compte du test
`test_every_title_is_recognized_whole` au nouveau total, puis `python3 tests/online_codes.py`
doit sortir 0. Un code abrogé va dans `ABROGATED`, avec sa date de fin ; s'il remplace un
code du même nom, ou porte un titre que l'usage donne au nouveau (« Code forestier »), il va
aussi dans `SUCCESSION`, du plus récent au plus ancien.

## Ce que le programme ne sait pas encore faire

La liste qui fait foi est `NOT_CHECKED` dans `citecheck/countries/france/scope.py` : c'est
elle que l'utilisateur voit dans l'onglet « Ce qui est vérifié ». Le README et cette section
la résument ; en cas d'écart, c'est `scope.py` qu'il faut croire, et les deux autres qu'il
faut corriger.

- Vérifier les décisions **citées sans numéro**. Elles sont signalées ; les chercher
  demanderait d'envoyer le nom des parties, ce que le programme ne fait jamais. Une piste
  sans rien envoyer du document : juridiction et date seules, mais une chambre de la Cour de
  cassation rend des dizaines de décisions le même jour.
- Vérifier les **TA** sans base locale, et les **CAA** absentes de Légifrance : impossible
  en ligne (voir « La base locale » plus haut). Un **RG** cité sans juridiction dans sa
  phrase n'est pas vérifié non plus.
- Vérifier la **CEDH** : impossible sans l'accord de la Cour (voir plus haut).
- Les **tribunaux de commerce** avant 2025 : Judilibre n'en publie rien (5 décisions en
  2024, 112 105 en 2025, mesuré le 29/09/2026), sans qu'on sache si l'antérieur viendra.
  Depuis 2025, ils sont vérifiés (`lower_courts.py`). Les **prud'hommes**, eux, ne sont pas
  dans Judilibre.
- Vérifier les articles d'un texte cité **sans numéro ni date**, des **arrêtés** (souvent
  plusieurs le même jour, sans numéro) et des **avenants** de conventions : chaque avenant est
  un texte à part dans Légifrance, cité de façons trop variées (« avenant n° 12 du ... ») pour
  être identifié sans risque. Ils sont signalés dans les remarques du rapport, jamais
  devinés.
- Vérifier la **formation** du Conseil d'État et la chambre des cours d'appel : seule la
  chambre de la Cour de cassation est comparée (`cited_chamber` dans `extract.py`, taxonomie
  de Judilibre dans `CHAMBERS`).
- Dire si la décision **soutient** l'argument. Aucune base ne le sait : c'est le travail du
  lecteur.
