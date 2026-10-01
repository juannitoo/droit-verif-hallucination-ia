"""Textes affichés, en français."""

DISCLAIMER = (
    "Aide à la vérification, sans garantie. Ce rapport dit si les décisions et les articles "
    "cités existent dans les bases officielles, à quelle date, et dans quelle version. Il ne "
    "dit pas s'ils soutiennent l'argument. L'auteur du texte reste responsable de ses "
    "citations.")

VERDICTS = {
    "CONFIRMED": "existe, à la date citée",
    "WRONG_DATE": "EXISTE, MAIS À UNE AUTRE DATE",
    "WRONG_CHAMBER": "EXISTE, MAIS D'UNE AUTRE CHAMBRE",
    "EXISTS_DATE_UNCHECKED": "existe, date non contrôlée",
    "NOT_PUBLISHED": "NE SEMBLE PAS PUBLIÉE",
    "DOUBTFUL": "douteux, à regarder à la main",
    "ARTICLE_IN_FORCE": "article en vigueur à la date de référence",
    "ARTICLE_OTHER_VERSION": "TEXTE CITÉ D'UNE AUTRE VERSION",
    "QUOTE_NOT_FOUND": "TEXTE CITÉ NON RETROUVÉ dans l'article",
    "DECISION_QUOTE_NOT_FOUND": "PASSAGE CITÉ NON RETROUVÉ dans la décision",
    "ARTICLE_NOT_IN_FORCE": "ARTICLE PAS EN VIGUEUR à la date de référence",
    "TEXT_NOT_FOUND": "CE TEXTE NE SEMBLE PAS EXISTER",
    "ARTICLE_NOT_FOUND": "CET ARTICLE NE SEMBLE PAS EXISTER dans ce texte",
    "CONVENTION_NOT_FOUND": "CET IDCC NE SEMBLE CORRESPONDRE À AUCUNE CONVENTION",
    "DATE_BEFORE_NUMBER": "DATE ANTÉRIEURE AU NUMÉRO",
    "UNVERIFIABLE_PERIOD": "non vérifiable",
    "MANUAL_CHECK": "À VÉRIFIER À LA MAIN",
    "NOT_TESTED": "non vérifiée",
    "ERROR": "erreur technique, non vérifiée",
}

NOTE_NOT_PUBLISHED = ("« Ne semble pas publiée » ne veut pas dire « n'existe pas » : les "
                      "bases publiques ne contiennent pas toutes les décisions. À vérifier.")
NOTE_OTHER_VERSION = ("Un texte cité « d'une autre version » est souvent celui qu'un modèle a "
                      "appris : l'article a changé depuis, ou n'était pas encore rédigé ainsi.")
NOTE_WRONG_DATE = ("Une citation « existe, mais à une autre date » passe un contrôle rapide "
                   "du seul numéro. C'est une erreur fréquente des textes rédigés par IA.")
NO_CITATION = ("Aucune citation juridique relevée dans ce document. Soit il n'en "
               "contient pas, soit leur format n'est pas reconnu.")

# Rapport
DOCUMENT_LINE = "Document : {source}"
CHECKED_LINE = "Vérifié le {date} par {program}"
CITATION_LINE = "{court} n° {number}, {date}"
UNNUMBERED_LINE = "{court}, décision du {date} (aucun numéro lu)"
RG_LINE = "{court}, RG {number}, {date}"
ARTICLE_LINE = "{code}, article {number}"
CONVENTION_LINE = "Convention collective IDCC {idcc}, article {number}"
IDCC_UNKNOWN = "non indiqué"
QUOTE_LINE = "texte cité : « {quote} »"
LINK_LINE = "     lien : {link}"
NOT_CHECKED = "Non vérifié par ce programme : {what}."
EXCERPT_LINE = "extrait : {excerpt}"
PAGE_EXACT = "{page}"
PAGE_APPROX = "~ {page}"
PAGE_NOTES = "notes"
COL_NUMBER = "N°"
COL_PAGE = "Page"
COL_CITATION = "Citation"
COL_VERDICT = "Verdict"
DETAILS = "Détail, citation par citation :"
COL_SOURCE = "Source"
OPEN_LINK = "ouvrir"
LIGHT_LABELS = {"ok": "confirmée(s)", "check": "à vérifier", "invented": "semble(nt) inventée(s)",
                "unchecked": "non vérifiée(s)"}
REMARKS_HEADING = "Remarques"
# La notice de la première page du rapport PDF.
HOW_TO_READ = "Comment lire ce rapport"
HOW_TO_READ_DOCUMENT = "Comment lire ce document"
HOW_LINKS = ("Liens : « ouvrir » et les adresses mènent à la source officielle. Pour l'ouvrir "
             "dans un nouvel onglet : Ctrl + clic (Windows, Linux) ou Cmd + clic (Mac).")
HOW_COLORS = {
    # La mise en garde est DANS la ligne du bleu, pas dans un encadré à part : un encadré, on
    # le saute.
    "ok": ("Bleu : confirmé.", "La décision existe à la date citée, ou l'article est en vigueur "
           "à la date de référence ; si un passage est cité entre guillemets, il a été retrouvé "
           "tel quel dans le texte. Une citation en bleu affirme juste cela : « ce numéro existe "
           "à cette date », et, le cas échéant, « ces mots y figurent ». Elle ne veut pas dire "
           "« cet arrêt dit ce qu'on lui fait dire ». Cela reste la responsabilité et le "
           "jugement de l'utilisateur : l'administrateur du programme n'a pas compétence pour "
           "se prononcer."),
    "check": ("Orange : à vérifier.", "Trouvé, mais quelque chose ne concorde pas : autre date, "
              "autre chambre, autre version, passage cité non retrouvé. Rien de douteux n'est "
              "jamais mis en bleu."),
    "invented": ("Rouge : semble inventé.", "Introuvable dans une base qui publie tout : à "
                 "vérifier avant toute conclusion."),
    "unchecked": ("Gris : non vérifié.", "Clé absente, base indisponible, période non couverte, "
                  "ou vérification à faire à la main. Ce n'est pas une faute du document."),
}
HOW_LINKS_ANNOTATED = ("Liens : chaque passage surligné mène à la source officielle, et son "
                       "survol montre le verdict (selon le lecteur de PDF). Pour l'ouvrir dans "
                       "un nouvel onglet : Ctrl + clic (Windows, Linux) ou Cmd + clic (Mac).")
CLICKABLE = "Lien cliquable."
ANNOTATED_TITLE = "Citations vérifiées"
ANNOTATED_NEXT = ("Cette page a été ajoutée par {program}. Le document commence à la page "
                  "suivante ; il n'est pas modifié, les couleurs sont des annotations posées "
                  "par-dessus, que tout lecteur de PDF peut masquer.")
READING_HEADING = "Pour lire ce rapport"
PDF_REPORT_FOOTER = "{program} - page {page} / {pages}"
REFERENCE_LINE = "Date de référence pour les articles : {date}{default}"
REFERENCE_DEFAULT = " (date du jour, faute de date des faits)"
NO_DATE = "sans date citée"
CITED_ON = "cité au {date}"
SUMMARY = "Bilan :"
REMARK = "Remarque : {text}"
FOUND = "{n} citation(s) relevée(s)."
CHECKING = "Vérification des citations :"

# Lecture des documents
PDF_FAILED = "pdftotext a échoué : {detail}"
PDF_NO_READER = "Pour lire un PDF, installer pypdf :  pip install pypdf"
EXPORT_FIRST = ("{name} : format {fmt} non lu. L'exporter en PDF ou en Word (.docx) depuis "
                "le logiciel qui l'a créé.")
DAMAGED = "{name} : fichier abîmé ou pas au format {ext} ({detail})"
UNKNOWN_FORMAT = "{name} : format inconnu. Formats lus : .pdf .docx .odt .txt .md"
NO_TEXT = "{name} : aucun texte lisible."
TOO_DEEP = "{name} : structure anormalement imbriquée, refusée par prudence."
TOO_BIG = "Document trop volumineux une fois décompressé ({name}) : refusé par prudence."
TOO_LONG = "{name} : texte anormalement long, refusé par prudence."
TOO_MANY_PAGES = "{name} : {n} pages, au-delà des {max} lues : refusé par prudence."
SUSPICIOUS = ("{name} : structure qu'aucun traitement de texte n'écrit ({detail}), refusé par "
              "prudence.")
NO_TEXT_PDF = ("{name} : aucun texte lisible. C'est sans doute un PDF scanné (une image) : "
               "il faut un PDF texte.")

# Ligne de commande
CLI_DESCRIPTION = "Vérifie les citations juridiques d'un document."
CLI_SCOPE = "afficher ce qui est vérifié, et ce qui ne l'est pas"
CLI_UNREADABLE = "Document illisible : {error}"
BENCH_RESULT = ("Banc d'essai : {ok}/{tested} verdicts identiques aux réponses connues, "
                "{untested} non testé(s).")
BENCH_GAP = "  ÉCART n° {number} : attendu {expected}, obtenu {got}"

# Fenêtre
TAB_CHECK = "Vérifier un document"
TAB_KEYS = "Clés d'accès"
TAB_SCOPE = "Ce qui est vérifié"
KEYS_EXPLANATION = (
    "Certaines bases officielles demandent une clé gratuite, liée à votre compte. Vous la "
    "donnez une fois : elle reste sur cet ordinateur, dans le trousseau du système. Seuls "
    "partent vers les bases les numéros des décisions, les numéros d'articles avec le nom du "
    "code ou la référence de la loi ou du décret, et les numéros de conventions collectives "
    "(IDCC). Jamais le texte de votre document, ni les passages que vous citez entre "
    "guillemets : ils sont comparés sur cet ordinateur.")
KEYS_MISSING_WARNING = ("Une clé d'accès manque : une partie des citations ne sera pas "
                        "vérifiée. Voir l'onglet « Clés d'accès ».")
TITLE = "Vérification des citations juridiques"
DOCUMENT = "Document à vérifier"
CHOOSE = "Choisir un document…"
NO_DOCUMENT = "aucun document choisi"
FORMATS = "Documents (.pdf .docx .odt .txt .md)"
KEY_SAVE = "Enregistrer la clé"
SETTING_SAVE = "Enregistrer"
SETTING_SAVED = ("adresse enregistrée : la base sera essayée sur des décisions connues au "
                 "début de chaque vérification")
SETTING_EMPTY = "aucune base locale"
SETTING_NO_KEYRING = "ce système n'a pas de trousseau : l'adresse ne sera pas conservée"
SETTING_BAD_URL = "l'adresse doit commencer par https://"
KEY_DELETE = "Effacer"
KEY_PRESENT = "clé enregistrée"
KEY_MISSING = "aucune clé : ces décisions ne seront pas vérifiées"
KEY_HELP = "Obtenir une clé (gratuit)"
REFERENCE_DATE = "Date des faits (facultatif)"
REFERENCE_HINT = "AAAA-MM-JJ ; sinon la date du jour. Les articles sont lus à cette date."
IDCC = "IDCC de la convention (facultatif)"
IDCC_HINT = ("Quatre chiffres, sur le bulletin de paie. Utilisé pour les articles de "
             "convention cités sans IDCC.")
IDCC_INVALID = "IDCC invalide : des chiffres seulement, par exemple 1979."
REFERENCE_INVALID = "Date des faits invalide : écrire AAAA-MM-JJ, par exemple 2019-03-21."
KEY_NOT_A_KEY = ("ceci ne ressemble pas à une clé (espaces, accents ou retours à la ligne) : "
                 "non enregistrée. Recopiez la clé depuis PISTE, et elle seule")
KEY_NO_KEYRING = "ce système n'a pas de trousseau : la clé ne sera pas conservée"
CHECK = "Vérifier"
IN_PROGRESS = "Vérification en cours…"
SAVE = "Enregistrer :"
SAVE_TXT = "Rapport (texte)"
SAVE_REPORT_PDF = "Rapport (PDF)"
SAVE_JSON = "Rapport (pour une IA)"
SAVE_PDF = "PDF annoté"
PDF_IN_PROGRESS = "Écriture du PDF annoté…"
PDF_SAVED = ("PDF annoté enregistré : {path}\n{placed} citation(s) surlignée(s) : bleu "
             "confirmé, orange à vérifier, rouge semble inventée, gris « ? » non vérifiée. "
             "Chaque surlignage mène d'un clic à ce qui a été trouvé ; son survol donne le "
             "verdict.")
PDF_MISSED = ("\n{n} citation(s) non retrouvée(s) sur leur page, donc non surlignée(s) : "
              "voir le rapport.")
PDF_ONLY = "--pdf : seul un document PDF peut être annoté ; aucun PDF écrit."
NOT_OVER_DOCUMENT = ("Ce fichier est le document vérifié : il n'est jamais remplacé. "
                     "Choisissez un autre nom.")
PDF_NOT_OVER_ORIGINAL = "Le PDF annoté ne remplace jamais le document : choisissez un autre nom."
PDF_FAILED_ANNOTATE = "Le PDF annoté n'a pas pu être écrit ({error}). Le rapport reste valable."
REPORT_FILE = "rapport-citations"
NO_EXCERPTS = "Enregistrer sans extraits du document"
NO_EXCERPTS_HINT = ("Le rapport enregistré ne contient alors que les numéros, les dates et les "
                    "verdicts : ni phrase de votre document, ni nom du fichier. À garder coché "
                    "si vous le donnez à une IA en ligne : les extraits pourraient contenir les "
                    "noms des parties ou des faits couverts par le secret professionnel. Le "
                    "rapport affiché ci-dessus, lui, garde les extraits : donnez à l'IA le "
                    "fichier enregistré, pas un copier-coller de cette fenêtre.")
SOURCE_WITHHELD = "(nom du fichier retiré)"
