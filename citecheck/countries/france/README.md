# Vérifier les citations d'un texte juridique français

**Pour les avocats, juristes, magistrats, greffiers et enseignants** qui passent des heures à
vérifier qu'une décision existe, qu'elle date bien du jour indiqué et contient bien le
passage cité, qu'un article était en vigueur à la date des faits et qu'il disait bien ce
qu'on lui fait dire.

Ce programme fait ce travail de vérification, citation par citation, dans les bases
officielles. Il rend un rapport qui dit, pour chacune : ce qu'il a trouvé, où, et à quelle
date. Et il dit aussi, honnêtement, ce qu'il n'a pas pu contrôler.

## Pourquoi maintenant

Les textes rédigés avec une IA contiennent des citations fausses : décisions inventées,
vraies décisions avec une fausse date, articles cités dans une version périmée, codes
abrogés depuis vingt ans. Des juridictions l'ont déjà relevé dans des conclusions d'avocats
(tribunal judiciaire de Périgueux, 18 décembre 2025). Une citation fausse, c'est la
crédibilité d'un dossier, et parfois une sanction.

Vérifier à la main prend du temps. Vérifier avec une autre IA ne sert à rien : elle peut
inventer la confirmation. Ce programme ne contient **aucune IA**. Il ne sait que lire des
numéros et des dates, et poser la question aux bases publiques. Il ne peut rien inventer.

## Ce qu'il repère : des exemples

Chaque verdict ci-dessous a été obtenu sur les bases officielles, en septembre 2026.

| Dans le texte | Ce que dit le rapport |
|---|---|
| « Civ. 2e, 10 juillet 2013, n° 12-18.273 » | **EXISTE, MAIS D'UNE AUTRE CHAMBRE** : l'arrêt est de la chambre sociale |
| une vraie décision de la Cour de cassation, citée au mauvais jour | **EXISTE, MAIS À UNE AUTRE DATE**, avec la vraie date |
| « article 28 du Code des marchés publics », pour des faits de 2026 | **ARTICLE PAS EN VIGUEUR** : le code est abrogé ; les quatre éditions sont listées avec leur date d'abrogation |
| « article 405 du Code pénal » (l'escroquerie d'avant 1994) | **ARTICLE PAS EN VIGUEUR** : il n'existe que dans l'ancien Code pénal, abrogé le 1er mars 1994 |
| « article 199 undecies B du CGI » | le bon article, suffixe compris ; la vérification ne s'arrête pas à l'article 199 |
| « article 46 quater-0 ZZ bis du CGI » | **CET ARTICLE NE SEMBLE PAS EXISTER** dans le CGI : il est dans l'annexe III |
| « article 22 de la loi du 6 juillet 1989 » | **DOUTEUX, À REGARDER À LA MAIN** : neuf lois portent cette date ; l'article 22 n'existe que dans la loi n° 89-462 (rapports locatifs), avec son lien ; à vous de confirmer que c'est bien elle que vise la pièce |
| « loi n° 89-462 du 7 juillet 1989 » | **EXISTE, MAIS À UNE AUTRE DATE** : la loi est du 6 juillet |
| « loi n° 89-9999 » | **CE TEXTE NE SEMBLE PAS EXISTER** |
| une ordonnance de 2016 citée pour des faits de 2010 | **le texte n'existait pas encore** à la date des faits |
| « article 1382 du Code civil : "Tout fait quelconque de l'homme, qui cause à autrui un dommage..." », pour des faits de 2026 | **TEXTE CITÉ D'UNE AUTRE VERSION** : cette phrase est l'ancienne rédaction, d'avant la réforme de 2016 (elle est aujourd'hui à l'article 1240). Une IA cite souvent la version qu'elle a apprise |
| « T. confl., 8 février 1873, Blanco, n° 00012 » | vérifié au Tribunal des conflits seul ; le même numéro désigne aussi une décision du Conseil d'État de 1977, que le programme n'a pas le droit de confondre |
| « T. com. Paris, n° 2025F00234 », jugement daté du 12 mars 2024 | **DATE ANTÉRIEURE AU NUMÉRO** : l'affaire n'a été enregistrée qu'en 2025 |
| « CEDH, 25 mars 1993, n° 13134/87 » | **À VÉRIFIER À LA MAIN**, avec le lien de la recherche dans la base de la Cour |

## Ce qui est vérifié

### Les décisions de justice

| Juridiction | Base interrogée | Ce qui est contrôlé |
|---|---|---|
| Conseil d'État | ArianeWeb | existence, date |
| Cour de cassation | Judilibre | existence, date, **chambre** |
| Cours d'appel, tribunaux judiciaires | Judilibre | existence, date, par numéro RG, la juridiction étant nommée dans la phrase |
| Tribunaux de commerce et tribunaux des activités économiques | Judilibre | existence, date ; décisions publiées depuis 2025 |
| Cours administratives d'appel | Légifrance | existence, date ; Légifrance n'en publie qu'environ la moitié |
| Conseil constitutionnel | Légifrance | existence, date (« 2010-605 DC », « 2010-14/22 QPC ») |
| Tribunal des conflits | Légifrance | existence, date |
| Cour de justice et Tribunal de l'Union européenne | CELLAR (Office des publications de l'Union) | existence, date (« C-561/19 ») |

La date citée est lue à côté du numéro, en toutes lettres ou en chiffres, dans la même phrase.
La chambre de la Cour de cassation est lue sous toutes ses formes (« Cass. soc. », « Civ. 2e »,
« 1re civ. », « chambre commerciale », « Ass. plén. »), avant ou juste après le numéro.

Quand une décision trouvée est accompagnée d'un passage entre guillemets, ce passage est
cherché dans son texte intégral, sommaire et titres compris (un avocat cite souvent le
sommaire). Le texte vient de Judilibre (Cour de cassation, cours d'appel, tribunaux) ou de
Légifrance (Conseil constitutionnel, cours administratives d'appel, Tribunal des conflits).
Pour le Conseil d'État et l'Union européenne, le programme ne lit pas encore le texte : la
décision est vérifiée, le passage non, et le rapport le dit. Seul le numéro de la décision
part sur le réseau, jamais le passage.

### Les articles

- **Les 76 codes en vigueur**, en toutes lettres ou sous leur abréviation d'usage (C. civ.,
  C. trav., CSS, CPC, CGI, CGCT, CESEDA...).
- **Les 32 codes abrogés** : Code des marchés publics (quatre éditions), ancien Code pénal,
  Code de procédure civile de 1807, ancien Code de commerce, Code de la nationalité, codes de
  déontologie... Une IA a appris l'ancien droit : elle les cite.
- **Le code et ses éditions successives** : « Code forestier » ou « Code pénal » sans
  précision est cherché d'abord dans le code actuel, puis dans les éditions abrogées si
  l'article n'y est pas en vigueur à la date des faits. Le rapport dit dans lequel il l'a
  trouvé. Si deux éditions l'ont en vigueur le même jour (l'ancien Code rural l'est encore
  en partie), ou si le code actuel existait sans ce numéro : à vérifier, jamais confirmé.
- **Les numéros du Code général des impôts** et de ses annexes I à IV, suffixes empilés
  compris (« 46 quater-0 ZZ bis », « 238 bis-0 I », « 302 bis ZA »).
- **Les lois, lois organiques, ordonnances et décrets non codifiés** : « article 22 de la loi
  n° 89-462 du 6 juillet 1989 », « Loi n° 65-557, art. 14 », « article 6 de la même loi ».
  Cités en entier aussi (« la loi n° 91-647 du 10 juillet 1991 relative à l'aide
  juridique ») : le programme vérifie qu'un texte de cette nature porte ce numéro, à cette
  date, et donne son intitulé officiel, à comparer à celui de la pièce. Une IA invente
  volontiers un numéro de loi, ou date la bonne loi d'un autre jour. Confirmé seulement
  s'il est en vigueur à la date de référence ; abrogé, ou texte de codification (« décret
  ... portant code des marchés publics », en vigueur alors que le code est abrogé) : à
  vérifier.
- **Les conventions collectives**, par leur IDCC (écrit dans la phrase, ou donné au
  programme) : jamais devinées à partir de leur nom.

Pour chaque article : existe-t-il, était-il **en vigueur à la date des faits** (que vous
indiquez ; à défaut, la date du jour), et le passage cité entre guillemets est-il bien celui
de la version applicable ? Toutes les versions de l'article sont lues, pas seulement la
dernière.

## Le principe : on montre, on ne choisit pas

Quand une citation est ambiguë, le programme ne tranche pas à votre place. « La loi du 6
juillet 1989 » désigne neuf lois : il cherche l'article dans chacune et vous dit laquelle le
contient, ou vous les montre toutes s'il existe dans plusieurs. Dans les deux cas, le
verdict reste « à regarder à la main » : c'est à vous de dire laquelle est visée.

Un verdict confirmé doit être sûr. Si la phrase ne rattache pas l'article à un seul code ou
à un seul texte de façon certaine (« article 22 du Code civil ou de la loi du 6 juillet
1989 », « art. 1240, C. trav., art. L. 1152-1 », où le code peut être celui de l'un ou de
l'autre), l'article n'est pas vérifié : le rapport le signale, et le PDF annoté le surligne
en gris avec un « ? », pour que vous sachiez où regarder dans la pièce.
Mieux vaut une citation juste laissée en gris qu'une citation confirmée sur le mauvais
texte.

De même, il ne dit jamais « faux » ni « inventé ». Il dit « ne semble pas publiée », « ne semble
pas exister », « existe, mais à une autre date » : il constate, et vous renvoie à une
vérification. Les bases publiques ne contiennent pas toutes les décisions, et le programme
ne dit jamais plus que ce qu'il a contrôlé.

Trois règles le protègent contre ses propres erreurs, et contre celles des bases de données
publiques qu'il interroge (Judilibre, Légifrance, ArianeWeb, CELLAR) :

1. **Chaque base est mise à l'épreuve avant de servir.** Au début de chaque vérification, le
   programme lui demande des décisions et des articles dont il sait qu'ils existent, et des
   numéros dont il sait qu'ils sont inventés. Si elle ne retrouve pas les premiers, ou si
   elle trouve les seconds, il ne s'en sert pas : les citations qui en dépendent sortent
   « non vérifiées ».
2. **La couverture est mesurée, pas supposée.** Judilibre ne publie largement les cours
   d'appel que depuis 2022-2023, les tribunaux judiciaires depuis 2024-2025, et pas au même
   rythme partout. Le programme compte, pour la juridiction citée, les décisions publiées
   année par année. Une décision introuvable dans une période mal couverte sort « non
   vérifiable », jamais « ne semble pas publiée ».
3. **Une panne ne passe jamais pour une erreur de l'auteur.** Base injoignable, clé absente,
   refus de PISTE : la citation sort « non vérifiée », jamais « ne semble pas publiée ».

## Ce qu'il ne vérifie pas, et pourquoi

Rien ne passe en silence : tout ce que le programme voit sans pouvoir le vérifier figure
dans le rapport, avec sa page, marqué « à vérifier à la main ».

| Ce qui manque | Pourquoi |
|---|---|
| **Tribunaux administratifs** | Aucune base en ligne ne permet à un programme de les interroger. Le Conseil d'État publie toutes leurs décisions depuis juin 2022 (et celles des CAA depuis mars 2022) sur opendata.justice-administrative.fr, mais seulement en archives mensuelles à télécharger, sans interface de recherche pour les programmes. Un cabinet spécialisé peut se faire installer une base locale construite à partir de ces archives : le programme a un champ pour en donner l'adresse, et l'interroge alors. |
| **Cours administratives d'appel absentes de Légifrance** | Légifrance n'en publie qu'environ la moitié : une absence ne prouve rien (« non vérifiable »). La base locale ci-dessus comble ce manque. |
| **Tribunaux de commerce avant 2025** | Judilibre ne publie leurs décisions que depuis 2025. On ne sait pas encore si les décisions antérieures le seront un jour. |
| **Conseils de prud'hommes** | Ils ne sont dans aucune base publique : Judilibre ne connaît que la Cour de cassation, les cours d'appel, les tribunaux judiciaires et les tribunaux de commerce. Leurs jugements frappés d'appel se retrouvent au niveau de la cour d'appel. |
| **Cour européenne des droits de l'homme** | La Cour n'autorise pas la recherche dans sa base HUDOC par un programme, et ce programme ne contourne pas ce refus. Le rapport vous donne le lien de la recherche, à ouvrir dans votre navigateur. |
| **Décisions citées sans numéro** (« CE, Ass., 30 octobre 2009, Mme Perreux ») | Les bases se consultent par numéro. Les chercher par le nom des parties voudrait dire envoyer ce nom, qui vient de votre document : le programme ne le fait jamais. |
| **Un RG cité sans la juridiction dans la phrase** | Le même numéro existe dans des dizaines de juridictions. |
| **Arrêtés, textes cités sans numéro ni date, textes d'avant 1945** | Souvent plusieurs arrêtés le même jour, sans numéro ; les textes anciens n'en ont pas. |
| **Avenants et accords attachés aux conventions collectives** | Chaque avenant est un texte à part, cité de façons trop variées (« avenant n° 12 du ... ») pour être identifié sans risque. Seul le texte de base de la convention est vérifié. |
| **Passage cité d'une décision du Conseil d'État ou de l'Union européenne** | Le programme ne lit pas encore le texte des décisions dans ArianeWeb et CELLAR. La décision elle-même est vérifiée. |
| **Formation du Conseil d'État, chambre des cours d'appel** | Seule la chambre de la Cour de cassation est comparée. |
| **Le sens de la décision** | Savoir si une décision soutient l'argument pour lequel elle est citée demande de la comprendre, donc une IA dans le programme. C'est le travail de l'avocat. |

## Où est la citation

Chaque citation du rapport porte sa **page** (exacte pour un PDF, approximative pour Word et
LibreOffice, qui enregistrent les sauts de page de leur dernier affichage), un **extrait** du
texte qui l'entoure, et l'indication **note de bas de page** quand elle y figure.

## Taille du document

Jusqu'à **3 000 pages** pour un PDF, et 10 millions de caractères pour tout format (Word et
LibreOffice compris), ce qui fait aussi environ 3 000 pages de conclusions. Au-delà, le
programme refuse le document et le dit : rien n'est vérifié à moitié. Ces plafonds
protègent l'ordinateur d'un fichier fabriqué pour le bloquer ; un dossier réel, même très
lourd, reste en dessous.

Le PDF annoté a deux limites de plus : une minute pour relire les pages qui portent une
citation, et 200 000 lettres par page (une page pleine en compte quelques milliers). S'il ne
peut pas être écrit, le rapport, lui, reste valable.

## Votre texte ne sort pas de votre ordinateur

Seuls partent vers les bases publiques les numéros des décisions, les numéros d'articles
avec le nom du code ou du texte, et les numéros de conventions collectives. **Jamais votre
texte, jamais les noms des parties.**

Le rapport peut être enregistré **sans aucun extrait** de votre document (c'est le réglage
par défaut) : seulement des numéros, des dates et des verdicts. Vous pouvez alors le donner
à une IA pour qu'elle corrige ses propres citations, sans y faire passer de faits couverts
par le secret professionnel.

Vos clés d'accès (un compte PISTE gratuit, pour Judilibre et Légifrance) restent dans le
trousseau de votre système.

## Lire le rapport

| Verdict | Ce qu'il veut dire |
|---|---|
| existe, à la date citée | la base a la décision, à ce jour-là |
| existe, date non contrôlée | la décision existe, mais la date n'a pas pu être comparée : aucune date citée à côté du numéro (la vraie date est donnée), ou décision connue seulement par d'autres qui la citent |
| **EXISTE, MAIS À UNE AUTRE DATE** | le numéro existe ; la vraie date est donnée. Erreur typique d'un texte d'IA |
| **EXISTE, MAIS D'UNE AUTRE CHAMBRE** | la décision existe, mais la Cour de cassation l'a rendue dans une autre chambre |
| **NE SEMBLE PAS PUBLIÉE** | aucune trace dans une base qui couvre la période : à vérifier |
| non vérifiable | introuvable, mais la base ne couvre pas cette période, ou pas en entier : l'absence ne prouve rien |
| **DATE ANTÉRIEURE AU NUMÉRO** | la date citée précède l'année d'enregistrement que porte le numéro |
| **PASSAGE CITÉ NON RETROUVÉ dans la décision** | la décision existe, mais le passage entre guillemets n'y est pas tel quel (paraphrase, citation de mémoire, nom remplacé par [X] à la publication, ou passage inventé) : à relire |
| article en vigueur à la date de référence | l'article existait et s'appliquait à la date des faits |
| **ARTICLE PAS EN VIGUEUR à la date de référence** | abrogé, pas encore entré en vigueur, ou texte postérieur aux faits |
| **TEXTE CITÉ D'UNE AUTRE VERSION** | le passage entre guillemets est celui d'une rédaction antérieure ou postérieure |
| **TEXTE CITÉ NON RETROUVÉ dans l'article** | le passage entre guillemets n'est dans aucune version (paraphrase, ou texte inventé) |
| **CET ARTICLE NE SEMBLE PAS EXISTER dans ce texte** | aucune version de cet article, à aucune date |
| **CE TEXTE NE SEMBLE PAS EXISTER** | aucune loi, ordonnance ou décret sous ce numéro |
| **CET IDCC NE SEMBLE CORRESPONDRE À AUCUNE CONVENTION** | aucune convention collective sous ce numéro |
| douteux, à regarder à la main | plusieurs textes possibles contiennent l'article ; le rapport les montre |
| **À VÉRIFIER À LA MAIN** | vu, mais aucune base interrogeable (voir plus haut) |
| non vérifiée | base injoignable, clé absente ou refus de PISTE : rien n'a pu être contrôlé, la raison est donnée |

## Ce qui a été éprouvé

- Des **bancs d'essai** dont la réponse est connue, rejoués contre les vraies bases : près
  de 80 citations (décisions réelles, dates fausses, chambres fausses, numéros inventés,
  codes abrogés, lois ambiguës), dont le cas du tribunal judiciaire de Périgueux.
- Des **audits de sécurité** par trois modèles différents : Claude Opus 5.5 et Kimi K3 le 29
  septembre 2026, puis Grok 4.7 à trois reprises, du 30 septembre au 1er octobre 2026
  (fichiers piégés, ce qui part sur le réseau, rapport sans extraits, PDF annoté, réponses
  incomplètes des bases, lecture des phrases).
- Reste à faire avant diffusion : l'éprouver sur des cas réels de citations inventées, qui
  n'ont pas servi à le construire.

## L'obtenir

Voir le [README](../../../README.md) à la racine du dépôt. Le programme est gratuit.
Des installeurs pour Windows, macOS et Linux sont prévus.

**Aide à la vérification, sans garantie. L'auteur du texte reste responsable de ses
citations.**
