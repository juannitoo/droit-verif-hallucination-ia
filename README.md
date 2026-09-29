# droit-verif-hallucination-ia

Vérifie les citations d'un texte juridique français, sans rien inventer :

- **les décisions de justice** (Conseil d'État, Cour de cassation, cours d'appel, tribunaux
  judiciaires, Conseil constitutionnel, Tribunal des conflits, Cour de justice et Tribunal de
  l'Union européenne) : existent-elles, et à la date indiquée ?
- **les articles de codes et de conventions collectives** : existent-ils, étaient-ils en
  vigueur à la date des faits, et le texte cité entre guillemets est-il bien le leur ?

Les IA inventent des décisions, citent une vraie décision avec une fausse date, ou
reprennent un article dans une version périmée. Des tribunaux l'ont relevé dans des
conclusions d'avocats (TJ Périgueux, 18 décembre 2025). Ce programme interroge les bases
officielles (Judilibre, Légifrance, ArianeWeb, et CELLAR pour l'Union européenne) et rend un rapport, avec la page de chaque
citation : exacte pour un PDF, approximative pour les autres formats.

Il pointe ce qui est suspect, il ne donne pas d'avis. Il ne dit pas si une décision soutient
l'argument : ça reste le travail de l'avocat. Ce qu'il reconnaît, et ce qu'il ne vérifie
pas, est listé dans l'onglet « Ce qui est vérifié » du programme.

## État

Programme en construction. Pas encore d'exécutable à télécharger. Audité par Claude Opus 5.5
et Kimi K3 le 29 septembre 2026. Il reste à le vérifier sur des cas réels qui n'ont pas
servi lors de la conception.

## Ce qu'il ne vérifie pas

- les décisions des cours administratives d'appel et des tribunaux administratifs ;
- les décisions de la CEDH : la Cour n'autorise pas la recherche dans sa base par un
  programme. Le rapport les signale, avec le lien de la recherche à ouvrir soi-même ;
- les tribunaux de commerce (publiés par Judilibre depuis 2025 : pas encore fait) et les
  conseils de prud'hommes (que Judilibre ne publie pas) ;
- un numéro RG cité sans le nom de la juridiction dans la même phrase (le même numéro
  existe dans plusieurs juridictions) ;
- les articles de lois et de décrets non codifiés, et ceux des avenants de conventions
  collectives : ils sont signalés dans le rapport, pas vérifiés ;
- la chambre qui a rendu la décision ;
- le sens d'une décision : si elle soutient l'argument pour lequel elle est citée.

## Ce qu'il faut

Un compte PISTE, gratuit, pour interroger Judilibre et Légifrance. Vos clés restent sur
votre ordinateur, dans le trousseau du système. Seuls partent vers les bases publiques les
numéros des décisions, les numéros d'articles avec le nom du code, et les numéros de
conventions collectives (IDCC) : jamais votre texte.

Le rapport peut être enregistré sans aucun extrait de votre document, pour le donner à une
IA sans y faire passer de noms ni de faits.

## Installer

Pas encore disponible. Quand il le sera, les installeurs pour **Windows**, **Mac** et
**Linux** seront compilés automatiquement par GitHub et publiés dans **Releases**, dans la
colonne de droite de cette page.

Pour compiler soi-même : donnez ce dépôt à une IA de code (Claude Code, Codex, ou autre).
Le fichier `notice-droit-verif-hallucination-ia.md` lui explique tout.

## Démonstration

Explications et démonstration sur des cas réels : [zicalo.com](https://www.zicalo.com/)
(bientôt).

## Contribuer : personne n'assure la veille

Ce programme est gratuit et public. Personne n'est payé pour le tenir à jour, et personne ne
le fera sur la durée. Le meilleur moyen reste donc de mettre les utilisateurs à
contribution. Quand Légifrance crée un
[code](https://www.legifrance.gouv.fr/liste/code?etatTexte=VIGUEUR), le programme le
reconnaît tout seul sous son titre complet et le dit dans le rapport, mais pas encore sous
[son abréviation](citecheck/countries/france/codes.py). Des citations ne seront donc pas
recueillies. C'est vous, à l'usage, qui le découvrirez : signalez-le dans les
[issues](https://github.com/juannitoo/droit-verif-hallucination-ia/issues), ou proposez la
correction par une pull request pour ceux qui comprennent ce que c'est. Même chose pour une
[abréviation d'usage](citecheck/countries/france/codes.py) qui manque, ou une citation mal
lue.

## Licence

Deux licences au choix, détail dans [LICENSE.md](LICENSE.md). Cabinets et entreprises :
usage interne. Particuliers, associations, enseignement, administrations : usage non
commercial. Personne ne peut le revendre.

**FOURNI TEL QUEL, SANS GARANTIE. VOUS RESTEZ RESPONSABLE DES CITATIONS QUE VOUS PRODUISEZ.**
