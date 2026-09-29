"""Textes affichés, en français."""

DISCLAIMER = (
    "Aide à la vérification, sans garantie. Ce rapport dit si les décisions et les articles "
    "cités existent dans les bases officielles, à quelle date, et dans quelle version. Il ne "
    "dit pas s'ils soutiennent l'argument. L'auteur du texte reste responsable de ses "
    "citations.")

VERDICTS = {
    "CONFIRMED": "existe, à la date citée",
    "WRONG_DATE": "EXISTE, MAIS À UNE AUTRE DATE",
    "EXISTS_DATE_UNCHECKED": "existe, date non contrôlée",
    "NOT_PUBLISHED": "NE SEMBLE PAS PUBLIÉE",
    "DOUBTFUL": "douteux, à regarder à la main",
    "ARTICLE_IN_FORCE": "article en vigueur à la date de référence",
    "ARTICLE_OTHER_VERSION": "TEXTE CITÉ D'UNE AUTRE VERSION",
    "QUOTE_NOT_FOUND": "TEXTE CITÉ NON RETROUVÉ dans l'article",
    "ARTICLE_NOT_IN_FORCE": "ARTICLE PAS EN VIGUEUR à la date de référence",
    "ARTICLE_NOT_FOUND": "CET ARTICLE NE SEMBLE PAS EXISTER dans ce texte",
    "CONVENTION_NOT_FOUND": "CET IDCC NE SEMBLE CORRESPONDRE À AUCUNE CONVENTION",
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
CITATION_LINE = "{court} n° {number}, cité au {date}"
ARTICLE_LINE = "{code}, article {number}"
CONVENTION_LINE = "Convention collective IDCC {idcc}, article {number}"
IDCC_UNKNOWN = "non indiqué"
QUOTE_LINE = "    texte cité : « {quote} »"
NOT_CHECKED = "Non vérifié par ce programme : {what}."
EXCERPT_LINE = "    extrait : {excerpt}"
WHERE_PAGE = " (page {page})"
WHERE_PAGE_APPROX = " (vers la page {page})"
WHERE_NOTES = " (dans les notes de bas de page)"
REFERENCE_LINE = "Date de référence pour les articles : {date}{default}"
REFERENCE_DEFAULT = " (date du jour, faute de date des faits)"
NO_DATE = "sans date"
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
    "donnez une fois : elle reste sur cet ordinateur, dans le trousseau du système. Seul le "
    "numéro de chaque décision citée est envoyé aux bases, jamais le texte de votre document.")
KEYS_MISSING_WARNING = ("Une clé d'accès manque : une partie des citations ne sera pas "
                        "vérifiée. Voir l'onglet « Clés d'accès ».")
TITLE = "Vérification des citations juridiques"
DOCUMENT = "Document à vérifier"
CHOOSE = "Choisir un document…"
NO_DOCUMENT = "aucun document choisi"
FORMATS = "Documents (.pdf .docx .odt .txt .md)"
KEY_SAVE = "Enregistrer la clé"
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
KEY_NO_KEYRING = "ce système n'a pas de trousseau : la clé ne sera pas conservée"
CHECK = "Vérifier"
IN_PROGRESS = "Vérification en cours…"
SAVE_TXT = "Enregistrer le rapport (texte)"
SAVE_JSON = "Enregistrer le rapport (pour une IA)"
REPORT_FILE = "rapport-citations"
