"""Cours d'appel, tribunaux judiciaires et tribunaux de commerce, cités par leur numéro RG,
vérifiés dans Judilibre.

UN RG N'EST PAS UNIQUE
  Chaque juridiction a sa propre numérotation : « 11/18803 » existe à Paris, à Lyon, à
  Rennes... On cherche donc toujours dans UNE juridiction, celle nommée dans la phrase, et
  on compare la date.

LA JURIDICTION
  Le nom de ville écrit dans le texte (« Paris », « Aix-en-Provence », « Aix ») est comparé
  aux libellés officiels de Judilibre. Une correspondance exacte, ou un début de nom qui ne
  désigne qu'une seule juridiction (« Aix »), suffit. Sinon on ne devine pas : non vérifiée.

LA COUVERTURE, CALCULÉE ET NON ÉCRITE EN DUR
  Judilibre ne publie largement les décisions des cours d'appel que depuis 2022-2023, et des
  tribunaux judiciaires que depuis 2024-2025 ; avant, une sélection. Et la couverture varie
  d'une juridiction à l'autre (mesuré le 29/09/2026 : Périgueux, 71 décisions pour 2025,
  269 pour les neuf premiers mois de 2026). Le programme lit donc, pour LA juridiction
  citée, le nombre de décisions publiées par année (/stats), ramène l'année en cours à une
  année pleine, et tient une année pour couverte si elle atteint 60 % de la meilleure.

  Les décisions récentes arrivent avec retard : les trois derniers mois mesurés comptaient
  deux à trois fois moins de décisions. Une décision de moins de six mois n'est donc jamais
  déclarée « non publiée ».

  Dans tous ces cas, une décision introuvable sort « non vérifiable », jamais « ne semble
  pas publiée » : l'absence n'y prouve rien. Et même dans une période couverte, certaines
  matières ne sont pas diffusées : le rapport dit « à vérifier ».

LES TRIBUNAUX DE COMMERCE (sondés le 29/09/2026)
  141 juridictions, dont 12 « tribunaux des activités économiques » (Paris, Nanterre,
  Lyon...) : « T. com. Paris » désigne le TAE de Paris. Judilibre ne publie RIEN avant 2025
  (5 décisions en 2024, 112 105 en 2025), et 12 tribunaux presque rien (Agen, Niort,
  Périgueux...) : la couverture mesurée s'en charge. On ne sait pas si l'antérieur viendra.
  Trois formes de numéro : « 2025J05588 », « 2026004078 », « J2026000698 ». La recherche de
  Judilibre ne trouve pas celles qui ont une lettre : on liste les décisions du tribunal au
  jour cité (sources.judilibre_on_day). Un tel numéro absent ce jour-là ne peut donc pas
  être cherché aux autres dates, et le rapport le dit.
  Le numéro porte l'année d'enregistrement de l'affaire : une décision datée d'avant est
  impossible, et c'est signalé sans rien demander au réseau.
"""
import re
import unicodedata
from datetime import date

from . import sources

COMPLETE_SHARE = 0.6
RECENT_DAYS = 183
KIND = {"ca": "cour d'appel", "tj": "tribunal judiciaire", "tcom": "tribunal de commerce"}
RE_TCOM_YEAR = re.compile(r"^[A-Z]?((?:19|20)\d\d)")


def _simplify(name):
    name = unicodedata.normalize("NFKD", name.lower())
    name = "".join(ch for ch in name if not unicodedata.combining(ch))
    name = re.sub(r"^(?:cour d'appel|tribunal judiciaire|tribunal de commerce|tribunal des "
                  r"activites economiques)\s*(?:de |d'|du )?", "", name.strip())
    return " ".join(re.sub(r"[-'’]", " ", name).split())


class Courts:
    """Les juridictions et la couverture de Judilibre, lues une fois par vérification."""

    def __init__(self, key):
        self.key = key
        self._places = {}
        self._first_complete = {}

    def location(self, jurisdiction, place):
        """(code Judilibre, libellé officiel) de la juridiction, ou None."""
        if jurisdiction not in self._places:
            self._places[jurisdiction] = sources.locations(jurisdiction, self.key)
        wanted = _simplify(place)
        found = [(code, label) for code, label in self._places[jurisdiction].items()
                 if _simplify(label) == wanted]
        if not found:
            found = [(code, label) for code, label in self._places[jurisdiction].items()
                     if _simplify(label).startswith(wanted + " ")]
        return found[0] if len(found) == 1 else None

    def first_complete_year(self, jurisdiction, location):
        """(première année couverte, {année: nombre}) pour cette juridiction, ou pour tout le
        type de juridiction si `location` vaut None (la Cour de cassation n'en a qu'une)."""
        location = location or jurisdiction
        if location not in self._first_complete:
            counts = sources.yearly_counts(
                jurisdiction, None if location == jurisdiction else location, self.key)
            today = date.today()
            elapsed = (today - date(today.year, 1, 1)).days + 1
            full = {y: (n * 365 / elapsed if y == str(today.year) else n)
                    for y, n in counts.items()}
            best = max(full.values(), default=0)
            complete = sorted(y for y, n in full.items() if best and n >= COMPLETE_SHARE * best)
            self._first_complete[location] = (complete[0] if complete else None, counts)
        return self._first_complete[location]


def registered_year(citation):
    """L'année d'enregistrement que porte un numéro de tribunal de commerce, ou None."""
    if citation.get("jurisdiction") != "tcom":
        return None
    m = RE_TCOM_YEAR.match(citation["number"])
    return m.group(1) if m else None


def check_lower_court(courts, citation):
    jurisdiction, number = citation["jurisdiction"], citation["number"]
    cited = citation.get("cited_date")
    year = registered_year(citation)
    if year and cited and cited[:4] < year:
        return ("DATE_BEFORE_NUMBER", f"le numéro {number} porte l'année d'enregistrement "
                f"{year}, et la décision est citée au {cited}, avant : l'un des deux semble "
                "inexact ; à vérifier", None)
    found = courts.location(jurisdiction, citation["place"])
    if found is None:
        # Le nom lu dans la pièce n'est pas recopié ici : il est déjà dans `court`, et un
        # rapport « sans extraits » doit pouvoir le retirer sans le chercher dans les phrases.
        return ("NOT_TESTED", f"nom de la {KIND[jurisdiction]} non reconnu sans ambiguïté "
                "parmi les juridictions de Judilibre", None)
    code, label = found
    searchable = jurisdiction != "tcom" or number.isdigit()
    dates = []
    if jurisdiction == "tcom" and cited:
        dates = sources.judilibre_on_day(number, jurisdiction, code, cited, courts.key)
    if searchable and not dates:
        dates = sources.judilibre_rg(number, jurisdiction, code, courts.key)
    if isinstance(dates, dict):
        return "ERROR", f"Judilibre n'a pas répondu ({dates['_err']})", None
    if dates:
        listed = ", ".join(dates)
        if not cited:
            return "EXISTS_DATE_UNCHECKED", f"{label} : existe, rendue le {listed} ; aucune date citée", listed
        if cited in dates:
            return "CONFIRMED", label, cited
        return ("WRONG_DATE", f"{label} : le RG existe, mais Judilibre date la décision du "
                f"{listed}, pas du {cited}", listed)

    first, counts = courts.first_complete_year(jurisdiction, code)
    recent = cited and (date.today() - date.fromisoformat(cited)).days < RECENT_DAYS
    if cited and first and cited[:4] >= first and not recent:
        if not searchable:
            return ("NOT_PUBLISHED", f"{label} : aucune décision sous ce numéro le {cited} "
                    "dans Judilibre. Judilibre ne permet pas de chercher un numéro qui "
                    "contient une lettre aux autres dates : la date est peut-être inexacte, ou "
                    "la décision non publiée ; à vérifier", None)
        return ("NOT_PUBLISHED", f"{label} : aucune décision sous ce RG dans Judilibre, qui "
                f"publie largement les décisions de cette juridiction depuis {first} : la "
                "décision ne semble pas publiée (certaines matières ne sont pas diffusées) ; "
                "à vérifier", None)
    if not cited and not searchable:
        return ("UNVERIFIABLE_PERIOD", f"{label} : aucune date citée, et Judilibre ne permet "
                "pas de chercher un numéro qui contient une lettre sans sa date : l'absence "
                "ne prouve rien", None)
    year = cited[:4] if cited else None
    if jurisdiction == "tcom" and year and year < "2025":
        why = ("Judilibre ne publie les décisions des tribunaux de commerce que depuis 2025 "
               f"({counts.get(year, 0)} pour ce tribunal en {year})")
    elif recent:
        why = "la décision a moins de six mois, et Judilibre publie avec retard"
    elif year:
        why = (f"les décisions de {year} de cette juridiction ne sont publiées qu'en partie "
               f"({counts.get(year, 0)} dans Judilibre cette année-là"
               + (f", publication large depuis {first}" if first else "") + ")")
    else:
        why = "aucune date citée, donc impossible de savoir si la période est couverte"
    return ("UNVERIFIABLE_PERIOD", f"{label} : introuvable dans Judilibre, mais {why} : "
            "l'absence ne prouve rien", None)


def check_lower_courts(citations, courts):
    results = []
    for c in citations:
        try:
            results.append(check_lower_court(courts, c))
        except Exception as e:
            results.append(("ERROR", f"Judilibre n'a pas répondu ({type(e).__name__})", None))
    return results
