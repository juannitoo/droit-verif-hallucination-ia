# droit-verif-hallucination-ia

Vérifie les citations d'un texte juridique français, sans rien inventer :

- **les décisions de justice** (Conseil d'État, cours administratives d'appel, Cour de
  cassation, cours d'appel, tribunaux judiciaires, tribunaux de commerce et des activités
  économiques, Conseil constitutionnel, Tribunal des conflits, Cour de justice et Tribunal
  de l'Union européenne) : existent-elles, à la date indiquée, et le passage cité entre
  guillemets est-il bien dans la décision ?
- **les articles de codes et de conventions collectives** : existent-ils, étaient-ils en
  vigueur à la date des faits, et le texte cité entre guillemets est-il bien le leur ? Les
  codes abrogés sont reconnus (Code des marchés publics, ancien Code pénal...) : une IA les
  cite volontiers, elle a appris l'ancien droit. De même pour les **articles des lois,
  ordonnances et décrets** non codifiés (loi du 6 juillet 1989 sur les baux, loi du 10
  juillet 1965 sur la copropriété...).

Les IA inventent des décisions, citent une vraie décision avec une fausse date, ou
reprennent un article dans une version périmée. Des tribunaux l'ont relevé dans des
conclusions d'avocats (TJ Périgueux, 18 décembre 2025). Ce programme interroge les bases
officielles (Judilibre, Légifrance, ArianeWeb, et CELLAR pour l'Union européenne) et rend
un rapport, avec la page de chaque citation : exacte pour un PDF, approximative pour les
autres formats.

Il pointe ce qui est suspect, il ne donne pas d'avis. Il ne dit pas si une décision soutient
l'argument : ça reste le travail de l'avocat. Ce qu'il reconnaît, et ce qu'il ne vérifie
pas, est listé dans l'onglet « Ce qui est vérifié » du programme.

**Avocats, juristes, magistrats : [la notice détaillée](citecheck/countries/france/README.md)
montre, exemples à l'appui, tout ce que le programme vérifie, et explique pourquoi certaines
choses ne peuvent pas l'être.**

## Pourquoi ce programme

En septembre 2026, deux voix de la profession ont décrit le problème
([Le Figaro, d'après l'AFP, 24 septembre 2026](https://www.lefigaro.fr/vie-professionnelle/c-est-le-syndrome-doctissimo-jurisprudences-sorties-de-nulle-part-contentieux-loufoques-l-ia-rend-fou-les-avocats-20260924)).

Le bâtonnier de Paris, Louis Degos, parle d'un « syndrome Doctissimo » : l'IA générative
« n'est pas entraînée à répondre aux questions juridiques, elle n'a pas forcément les bonnes
bases de données. Et elle continue à “halluciner”, à créer des choses qui n'existent pas pour
satisfaire l'humain qui attend une réponse ». Ces hallucinations se retrouvent dans des
conclusions d'avocats, et « quand c'est la juridiction qui s'en aperçoit et qui me saisit,
cela devient nettement plus embêtant ».

François Girault, président de la commission Prospective innovation du Conseil national des
barreaux, constate « une augmentation claire des décisions qui sanctionnent des avocats », et
prévient : « la prochaine étape, ce sera des condamnations ». Les clients, eux, arrivent au
cabinet avec des jurisprudences trouvées par une IA (« Regardez Maître, j'ai trouvé ça »), et
il faut alors « détricoter tout ce qui a été fait, tout revérifier ».

Tout revérifier, c'est ce que fait ce programme : citation par citation, dans les bases
officielles, et sans IA, donc sans pouvoir inventer la confirmation. Il sert aussi bien à
relire ses propres conclusions qu'à contrôler en quelques minutes les références apportées
par un client ou par le confrère adverse. Il est gratuit : un avocat seul y a accès comme un
grand cabinet, qui a, lui, les moyens de développer ses propres outils.

## Pour juger sur pièces

- fichier de test : [conclusions-test.pdf](exemples/conclusions-test.pdf), des conclusions
  fictives de deux pages, avec des citations exactes, inventées ou mal datées (dont celles
  relevées par le TJ de Périgueux) ;
- fichiers générés suite au test :
  - [conclusions-test-citations-verifiees.pdf](exemples/conclusions-test-citations-verifiees.pdf) :
    le document lui-même, chaque citation surlignée de la couleur de son verdict et
    cliquable lorsqu'elle est retrouvée, avec en première page le mode d'emploi des couleurs ;
  - [rapport-citations.pdf](exemples/rapport-citations.pdf) : le rapport, tableau et détail
    de chaque citation, enregistré sans extraits (ni phrase ni nom du document).

## État

Programme en construction. Pas encore d'exécutable à télécharger. Audité par Claude Opus 5.5
et Kimi K3 le 29 septembre 2026, puis deux fois par Grok 4.7, les 30 septembre et 1er octobre
2026 (sécurité : lecture des fichiers reçus, ce qui part sur le réseau, rapport sans
extraits, base locale, fichiers piégés, PDF annoté). Il reste à le vérifier sur des cas
réels qui n'ont pas servi lors de la conception.

Code écrit avec Claude Opus 5.5 (Claude Code, Anthropic), sous la direction de Jean BALANGUE.

## Ce qu'il ne vérifie pas

- les décisions des tribunaux administratifs : aucune base en ligne ne permet à un
  programme de les interroger. Elles ne sont publiées qu'en archives à télécharger ; une
  base locale construite à partir de ces archives peut être déclarée dans le programme.
  Celles des cours administratives d'appel sont vérifiées dans Légifrance, qui n'en publie
  qu'environ la moitié ;
- les décisions citées sans numéro : le rapport les signale, à vérifier à la main ;
- le passage cité d'une décision du Conseil d'État ou de l'Union européenne : la décision
  est vérifiée, pas encore le passage (le rapport le dit) ;
- les décisions de la CEDH : la Cour n'autorise pas la recherche dans sa base par un
  programme. Le rapport les signale, avec le lien de la recherche à ouvrir soi-même ;
- les décisions des tribunaux de commerce antérieures à 2025 (Judilibre n'en publie pas,
  pour l'instant) et celles des conseils de prud'hommes (que Judilibre ne publie pas) ;
- un numéro RG cité sans le nom de la juridiction dans la même phrase (le même numéro
  existe dans plusieurs juridictions) ;
- les articles d'une loi ou d'un décret cité sans numéro ni date, ceux des textes d'avant
  1945, des arrêtés et des avenants de conventions collectives : ils sont signalés dans le
  rapport, pas vérifiés ;
- la chambre, sauf celle de la Cour de cassation, qui est comparée à Judilibre ;
- le sens d'une décision : si elle soutient l'argument pour lequel elle est citée.

## Ce qu'il faut

Un compte PISTE, gratuit, pour interroger Judilibre et Légifrance. Vos clés restent sur
votre ordinateur, dans le trousseau du système. Seuls partent vers les bases publiques les
numéros des décisions, les numéros d'articles avec le nom du code ou la référence de la loi
ou du décret, et les numéros de conventions collectives (IDCC) : jamais votre texte.

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
son abréviation : les citations abrégées de ce code ne seront donc pas repérées. C'est vous,
à l'usage, qui le découvrirez : signalez-le dans les
[issues](https://github.com/juannitoo/droit-verif-hallucination-ia/issues), ou proposez la
correction par une pull request pour ceux qui comprennent ce que c'est. Même chose pour une
[abréviation d'usage](citecheck/countries/france/codes.py) qui manque, ou une citation mal
lue.

## Licence

Deux licences au choix, détail dans [LICENSE.md](LICENSE.md). Cabinets et entreprises :
usage interne. Particuliers, associations, enseignement, administrations : usage non
commercial. Personne ne peut le revendre.

**FOURNI TEL QUEL, SANS GARANTIE. VOUS RESTEZ RESPONSABLE DES CITATIONS QUE VOUS PRODUISEZ.**
