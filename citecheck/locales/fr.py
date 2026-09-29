"""Textes affichés, en français."""

DISCLAIMER = (
    "Aide à la vérification, sans garantie. Ce rapport dit si les décisions citées existent "
    "dans les bases officielles, et à quelle date. Il ne dit pas si elles soutiennent "
    "l'argument. L'auteur du texte reste responsable de ses citations.")

VERDICTS = {
    "CONFIRMED": "existe, date conforme",
    "WRONG_DATE": "EXISTE, MAIS DATE FAUSSE",
    "EXISTS_DATE_UNCHECKED": "existe, date non contrôlée",
    "NOT_PUBLISHED": "aucune décision publiée ne correspond",
    "DOUBTFUL": "douteux, à regarder à la main",
    "NOT_TESTED": "non vérifiée",
    "ERROR": "erreur technique, non vérifiée",
}

NOTE_NOT_PUBLISHED = ("« Aucune décision publiée ne correspond » ne veut pas dire « n'existe "
                      "pas » : les bases publiques ne contiennent pas toutes les décisions.")
NOTE_WRONG_DATE = ("Une citation « existe, mais date fausse » passe un contrôle rapide du "
                   "seul numéro. C'est l'erreur la plus fréquente des textes rédigés par IA.")
NO_CITATION = ("Aucune citation de jurisprudence relevée dans ce document. Soit il n'en "
               "contient pas, soit leur format n'est pas reconnu.")

# Rapport
DOCUMENT_LINE = "Document : {source}"
CHECKED_LINE = "Vérifié le {date} par {program}"
CITATION_LINE = "{court} n° {number}, cité au {date}"
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
CLI_DESCRIPTION = "Vérifie les citations de jurisprudence d'un document."
CLI_UNREADABLE = "Document illisible : {error}"
BENCH_RESULT = ("Banc d'essai : {ok}/{tested} verdicts identiques à ceux du tribunal, "
                "{untested} non testé(s).")
BENCH_GAP = "  ÉCART n° {number} : attendu {expected}, obtenu {got}"

# Fenêtre
TAB_CHECK = "Vérifier un document"
TAB_KEYS = "Clés d'accès"
KEYS_EXPLANATION = (
    "Certaines bases officielles demandent une clé gratuite, liée à votre compte. Vous la "
    "donnez une fois : elle reste sur cet ordinateur, dans le trousseau du système. Seul le "
    "numéro de chaque décision citée est envoyé aux bases, jamais le texte de votre document.")
KEYS_MISSING_WARNING = ("Une clé d'accès manque : une partie des décisions ne sera pas "
                        "vérifiée. Voir l'onglet « Clés d'accès ».")
TITLE = "Vérification des citations de jurisprudence"
DOCUMENT = "Document à vérifier"
CHOOSE = "Choisir un document…"
NO_DOCUMENT = "aucun document choisi"
FORMATS = "Documents (.pdf .docx .odt .txt .md)"
KEY_SAVE = "Enregistrer la clé"
KEY_DELETE = "Effacer"
KEY_PRESENT = "clé enregistrée"
KEY_MISSING = "aucune clé : ces décisions ne seront pas vérifiées"
KEY_HELP = "Obtenir une clé (gratuit)"
KEY_NO_KEYRING = "ce système n'a pas de trousseau : la clé ne sera pas conservée"
CHECK = "Vérifier"
IN_PROGRESS = "Vérification en cours…"
SAVE_TXT = "Enregistrer le rapport (texte)"
SAVE_JSON = "Enregistrer le rapport (pour une IA)"
REPORT_FILE = "rapport-citations"
