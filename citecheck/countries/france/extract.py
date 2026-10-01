"""Relève les citations de jurisprudence française dans un texte, par expressions régulières.

POURQUOI PAS UN MODÈLE
  Un modèle qui extrait les citations les comprend, et un modèle qui comprend corrige en
  silence : il rétablit la bonne date, rattache le bon arrêt. Il gommerait exactement ce
  qu'on cherche. Pour relever ce qu'un texte DIT, il faut un outil incapable de savoir ce
  qu'il DEVRAIT dire.

CE QU'IL SAIT LIRE
  administratif : CE / CAA / TA ... n° 308850            (5 à 7 chiffres après « n° »)
  judiciaire    : Cass. / Civ. 2e / Soc. ... 17-28.268 ou 17-28268
  appel, TJ     : CA Paris / cour d'appel de Paris / TJ Périgueux ... RG n° 11/18803 ;
                  la juridiction doit être nommée dans la même phrase
  Cons. const.  : « 2010-605 DC », « 2010-14/22 QPC » ; les autres suffixes (L, LP, AN...)
                  seulement si le Conseil constitutionnel est nommé dans la phrase
  T. confl.     : « C3911 », « n° 4112 », « n° 00012 », le Tribunal des conflits nommé dans
                  la phrase
  Union europ.  : « C-561/19 » (Cour de justice) ; « T-12/15 » (Tribunal) seulement si une
                  juridiction de l'Union est nommée dans la phrase
  CEDH, et tout numéro « 13134/87 » : jamais envoyés à une base qui n'est pas la leur, et
                  rendus « à vérifier à la main »
  CAA et TA     : « 21BX01234 », « TA Paris, n° 1901234 » : rendus « à vérifier à la main »,
                  jamais envoyés dans ArianeWeb comme des décisions du Conseil d'État
  sans numéro   : « CE, Ass., 30 octobre 2009, Mme Perreux », « Cass. soc., 10 juillet
                  2013 » : une juridiction suivie de près d'une date, sans numéro, est
                  rendue « à vérifier à la main ». Jamais cherchée : il faudrait envoyer le
                  nom des parties, qui vient du document
  dates en toutes lettres (« 5 juin 2009 ») et en chiffres (05/06/2009)
  articles      : « article L. 3121-2 du Code du travail », « art. 1240 C. civ. »,
                  « C. trav., art. L. 1152-1 », « articles L. 1234-1 et L. 1234-5 du ... »,
                  « du même code » ; et le texte cité entre guillemets juste à côté
  conventions   : « article 21 de la convention collective nationale des HCR (IDCC
                  1979) » ; l'IDCC est lu à proximité, jamais déduit du nom

CE QU'IL NE FAIT JAMAIS
  Deviner. Un numéro sans date lisible sort sans date, et le contrôle de date est annoncé
  impossible. Tout ce qu'il n'a pas su rattacher est signalé : un trou est un trou.
"""
import bisect
import re
import unicodedata
from datetime import date

from ...reader import PAGE
from .codes import find_code

MONTHS = {"janvier": 1, "février": 2, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5,
          "juin": 6, "juillet": 7, "août": 8, "aout": 8, "septembre": 9, "octobre": 10,
          "novembre": 11, "décembre": 12, "decembre": 12}

# Numéro de pourvoi : deux chiffres, tiret, deux chiffres, point facultatif, trois chiffres.
RE_APPEAL = re.compile(r"\b(\d{2}-\d{2}\.?\d{3})\b")
# Numéro de requête administrative : 5 à 7 chiffres précédés d'un marqueur n°.
RE_REQUEST = re.compile(r"n[°ºo]\s*(\d{5,7})\b", re.I)
RE_DATE_WORDS = re.compile(
    r"\b(\d{1,2})(?:er)?\s+(" + "|".join(MONTHS) + r")\s+(\d{4})\b", re.I)
RE_DATE_DIGITS = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b")

# Le Conseil d'État SEUL : les CAA et les TA ont leurs propres numéros, qu'ArianeWeb ne
# connaît pas (audit du 30/09/2026, point B : « TA Paris, n° 1901234 » partait dans
# ArianeWeb comme une décision du Conseil d'État). Sigles en majuscules : insensible à la
# casse, « CE » était le pronom « ce ».
MARK_ADMIN = re.compile(r"\b(?:CE\b|C\.E\.|Conseil\s+d['’]\s*[ÉE]tat\b)")
# Les abréviations se terminent par un point ou une fin de mot : sans ça, « Com » attrapait
# le « com » de « communication », et une décision du Conseil d'État était écartée sans bruit.
MARK_JUDICIAL = re.compile(
    r"\b(?:(?:Cass|Civ|Soc|Com|Crim)(?:\.|\b)|Cour de cassation"
    r"|chambre (?:civile|sociale|commerciale))",
    re.I)

# Juridictions que le programme ne vérifie pas. Les reconnaître sert à une chose : qu'un
# « CEDH, n° 13134/87 » ne parte pas dans ArianeWeb comme une requête du Conseil d'État, où
# il « confirmerait » une décision sans rapport, ou ferait dire « ne semble pas publiée »
# d'une décision qui existe (audit du 30/09/2026, point A).
MARK_OTHER = [
    ("CEDH", re.compile(r"\b(?:CEDH|C\.\s?EDH|Cour\s+EDH|Comm\.\s?EDH"
                        r"|Cour\s+européenne\s+des\s+droits\s+de\s+l['’]\s*homme)\b", re.I)),
    ("Tribunal des conflits", re.compile(r"\b(?:T\.\s?confl\.|Trib\.\s?confl\.|TC\b"
                                         r"|Tribunal\s+des\s+conflits)", re.I)),
    ("Conseil constitutionnel", re.compile(r"\b(?:Cons\.\s?const\.|Conseil\s+constitutionnel)",
                                           re.I)),
    ("CAA", re.compile(r"\bCAA\b|\b[Cc]our\s+administrative\s+d['’]\s*appel\b")),
    ("TA", re.compile(r"\bTA\b|\b[Tt]ribunal\s+administratif\b")),
    ("CJUE", re.compile(r"\b(?:CJUE|CJCE|TPICE|Trib\.\s?UE|Tribunal\s+de\s+l['’]\s*Union"
                        r"|Cour\s+de\s+justice\s+(?:de\s+l['’]\s*Union|des\s+Communautés))",
                        re.I)),
]
# « n° 13134/87 » : un numéro suivi d'une barre et de l'année n'est pas une requête du
# Conseil d'État (c'est la forme des requêtes CEDH), même si aucune juridiction n'est nommée.
RE_SLASH_YEAR = re.compile(r"/\d{2,4}\b")

CONSTIT = "Conseil constitutionnel"
CONFLICTS = "Tribunal des conflits"
EU = "CJUE"
# « 2010-605 DC » : l'année, le numéro, la nature. DC et QPC suffisent à reconnaître le
# Conseil constitutionnel ; les autres natures (« L », « D »...) sont trop courtes pour être
# lues sans que le Conseil soit nommé dans la phrase.
RE_CONSTIT = re.compile(r"\b(\d{2,4}-\d{1,5}(?:/\d{1,5})*)\s+"
                        r"(DC|QPC|LP|FNR|LOM|ORGA|RIP|PDR|REF|ELEC|AN|SEN|L|D|I)\b")
CONSTIT_ALONE = {"DC", "QPC"}
RE_CONFLICTS = re.compile(r"\bn[°ºo]\s*(C?\s?\d{4,5})\b|\b(C\d{4})\b")
# Tribunaux de commerce, et « tribunaux des activités économiques » (Paris, Nanterre, Lyon...
# depuis 2025). Le numéro n'est lu que si le tribunal est nommé dans la même phrase.
RE_TCOM_COURT = re.compile(
    r"\bT\.\s?com\.|\bTAE\b|\bT\.\s?A\.\s?E\.|\b[Tt]ribunal\s+de\s+commerce\b"
    r"|\b[Tt]ribunal\s+des\s+activit[ée]s\s+[ée]conomiques\b")
RE_TCOM_CITY = re.compile(r"\s*,?\s*(?:de\s+|d['’]\s*|du\s+|des\s+)?")
# « 2025J05588 », « 2026004078 », « J2026000698 » : l'année d'enregistrement en tête.
RE_TCOM_NUMBER = re.compile(r"\b((?:19|20)\d\d[A-Z]\d{5}|[A-Z]?(?:19|20)\d{8})\b")
# Numéro de CAA : l'année, deux lettres de la cour, cinq chiffres. Aucune autre juridiction
# n'a cette forme.
RE_CAA = re.compile(r"\b(\d{2}[A-Z]{2}\d{5})\b")
# Pour les décisions citées sans numéro : toute juridiction, suivie de près d'une date.
MARK_ANY = [("CE", MARK_ADMIN), ("Cass.", MARK_JUDICIAL),
            ("CA", re.compile(r"\bCA\b|\b[Cc]our\s+d['’]\s*appel\b")),
            ("TJ", re.compile(r"\b(?:TJ|TGI)\b|\b[Tt]ribunal\s+(?:judiciaire|de\s+grande\s+"
                              r"instance)\b")),
            ("T. com.", RE_TCOM_COURT),
            ("CPH", re.compile(r"\bCPH\b|\b[Cc]onseil\s+de\s+prud['’]\s*hommes\b"))
            ] + MARK_OTHER
UNNUMBERED_GAP = 60   # entre la juridiction et la date : « CE, Ass., sect., »
# « la Cour de cassation applique la loi du 6 juillet 1989 » : la date est celle d'un texte.
RE_NOT_A_DECISION = re.compile(r"\b(?:loi|décret|ordonnance|arrêté|circulaire|directive|"
                               r"règlement|convention|accord|avenant|article|art\.)", re.I)
RE_EU = re.compile(r"\b([CT])\s?[-‑–]\s?(\d{1,4})/(\d{2})\b")
# La date d'un texte, juste avant elle : « la loi du 8 août 2016 », « décret n° 2016-1234 du
# 29 septembre 2016 ». Ce n'est pas la date de la décision voisine.
RE_TEXT_DATE = re.compile(
    r"\b(?:loi|décret|ordonnance|arrêté|circulaire|directive|règlement|avenant|accord)s?"
    r"(?:\s+organique)?(?:\s+n[°º]\s*[\d-]+)?\s+(?:du|en\s+date\s+du)\s+$", re.I)
# Un pourvoi (« 17-28.268 ») n'est une décision de la Cour de cassation que si la phrase le
# dit : une juridiction judiciaire ou une chambre nommée, ou les mots « pourvoi », « arrêt ».
# « Référence 17-28.268 communiquée le 21 mars 2019 au client » n'est pas une citation
# (audit du 01/10/2026).
MARK_APPEAL = re.compile(r"\bpourvoi|\barr[êe]t|\bass(?:emblée)?\.?\s*pl[ée]n|\bch(?:ambre)?\.?\s*mixte"
                         r"|\bch(?:ambres)?\.?\s*réunies", re.I)

WINDOW = 160   # caractères de part et d'autre où l'on cherche la date et la juridiction


def _iso(m, words=True):
    """La date en AAAA-MM-JJ, ou None si elle n'existe pas au calendrier (« 31/02/2019 ») :
    une date impossible n'est pas une date citée."""
    if words:
        day, month, year = m.group(1), MONTHS[m.group(2).lower()], m.group(3)
    else:
        day, month, year = m.group(1), int(m.group(2)), m.group(3)
    iso = f"{year}-{month:02d}-{int(day):02d}"
    try:
        date.fromisoformat(iso)
    except ValueError:
        return None
    return iso


def assign_dates(text, spans, used=None, places=None):
    """Rattache chaque date à UN seul numéro de décision : le plus proche, dans la même
    phrase. Renvoie {début du numéro: date}.

    Avant (audit du 29/09/2026, K3) : chaque numéro prenait la date la plus proche, même
    celle de son voisin. « CE n° 308850 du 5 juin 2009 et n° 402517 » datait les deux du
    5 juin 2009, et le programme pouvait « confirmer » une association que le document n'a
    jamais faite."""
    starts = sorted(spans)
    firsts = [start for start, _ in starts]
    longest = max((end - start for start, end in starts), default=0)
    best = {}
    dates = [(m, _iso(m)) for m in RE_DATE_WORDS.finditer(text)]
    dates += [(m, _iso(m, False)) for m in RE_DATE_DIGITS.finditer(text)]
    disputed = set()
    for m, day in dates:
        if not day or RE_TEXT_DATE.search(text[max(0, m.start() - 60):m.start()]):
            continue                        # « la loi du 8 août 2016 » : pas la décision
        candidates = []
        # Seuls les numéros à moins de WINDOW caractères comptent : on ne parcourt qu'eux.
        # (Tous, pour chaque date : un document de mille fois la même citation y passait
        # des minutes, audit du 01/10/2026.)
        lo = bisect.bisect_left(firsts, m.start() - WINDOW - longest)
        hi = bisect.bisect_right(firsts, m.end() + WINDOW)
        for start, end in starts[lo:hi]:
            gap = m.start() - end if m.start() >= end else start - m.end()
            if gap < 0 or gap > WINDOW:
                continue
            lo, hi = (end, m.start()) if m.start() >= end else (m.end(), start)
            if RE_SENTENCE_END.search(text, max(0, lo - 1), hi):
                continue                    # une fin de phrase les sépare
            candidates.append((gap, start))
        if candidates:
            gap, start = min(candidates)
            if start in best and best[start][1] != day:
                # Deux dates pour un seul numéro, dans la même phrase : « arrêt du 1er
                # janvier 1900 (et non du 21 mars 2019), n° 17-28.268 ». Choisir la plus
                # proche pourrait confirmer celle que la phrase écarte : aucune n'est retenue,
                # la date n'est pas contrôlée (audit du 01/10/2026).
                disputed.add(start)
                if used is not None:
                    used.update((best[start][2], m.start()))
            if start not in best or gap < best[start][0]:
                best[start] = (gap, day, m.start(), m.end())
    if used is not None:
        used.update(where for _, _, where, _ in best.values())
    if places is not None:      # où est écrite la date retenue, pour le PDF annoté
        places.update({start: (a, b) for start, (_, _, a, b) in best.items()
                       if start not in disputed})
    return {start: day for start, (_, day, _, _) in best.items() if start not in disputed}


# La chambre de la Cour de cassation citée avant le pourvoi, dans la même phrase. Codes de
# Judilibre (taxonomie « chamber », relevée le 30/09/2026). « civ » : une chambre civile, sans
# dire laquelle (« Civ. », « chambre civile »). Une vraie décision attribuée à la mauvaise
# chambre est une erreur typique d'une IA.
ORDINALS = {"1": "civ1", "2": "civ2", "3": "civ3", "première": "civ1", "deuxième": "civ2",
            "troisième": "civ3"}
CHAMBERS = [
    (re.compile(r"\bciv(?:ile)?\.?\s*([123])\s*(?:re|ère|er|e|ème)\b", re.I), None),
    (re.compile(r"\b([123])\s*(?:re|ère|er|e|ème)\.?\s*(?:ch(?:ambre)?\.?\s*)?civ(?:ile)?\b",
                re.I), None),
    (re.compile(r"\b(première|deuxième|troisième)\s+chambre\s+civile\b", re.I), None),
    (re.compile(r"\bchambre\s+sociale\b|\bsoc\.|\bCass\.?\s*soc\b", re.I), "soc"),
    (re.compile(r"\bchambre\s+commerciale\b|\bcom\.|\bCass\.?\s*com\b", re.I), "comm"),
    (re.compile(r"\bchambre\s+criminelle\b|\bcrim\.|\bCass\.?\s*crim\b", re.I), "cr"),
    (re.compile(r"\bass(?:emblée)?\.?\s*pl[ée]n(?:ière)?\b", re.I), "pl"),
    (re.compile(r"\bch(?:ambre)?\.?\s*mixte\b", re.I), "mi"),
    (re.compile(r"\bch(?:ambres)?\.?\s*réunies\b", re.I), "creun"),
    (re.compile(r"\bciv\.|\bchambre\s+civile\b|\bCass\.?\s*civ\b", re.I), "civ"),
]


CHAMBER_AFTER = 80    # « n° 21-11.484, la deuxième chambre civile a jugé » : tout près
CHAMBER_NEXT = 40     # « Civ. 2e, 5 mars 2019, n° » : une chambre qui annonce le pourvoi suivant


def cited_chamber(text, start, end=None, stop=None):
    """Le code Judilibre de la chambre nommée avant le numéro (`start`), dans la même phrase ;
    à défaut, juste après (`end`), sans dépasser la phrase ni le numéro suivant (`stop`)."""
    return _cited_chamber(text, start, end, stop)[0]


def _cited_chamber(text, start, end=None, stop=None):
    """(code, (début, fin) de la chambre dans le texte), ou (None, None)."""
    lo = _sentence_start(text, start)
    found = _chambers(text, lo, start)
    if not found and end is not None:
        hi = min(len(text), end + CHAMBER_AFTER, stop if stop is not None else len(text))
        m = RE_SENTENCE_END.search(text, end, hi)
        found = _chambers(text, end, m.start() if m else hi)
        if found:           # après le numéro : la PREMIÈRE nommée, pas la dernière
            first = min(found, key=lambda f: f[0])
            # « n° 19-11.399, puis Civ. 2e, n° 18-12.345 » : suivie de près par le pourvoi
            # suivant, dans la même phrase, elle est à lui.
            if (stop is not None and stop - first[1] <= CHAMBER_NEXT
                    and not RE_SENTENCE_END.search(text, first[1], stop)):
                return None, None
            f = min((f for f in found if f[0] < first[1] and first[0] < f[1]),
                    key=lambda f: f[2])
            return f[3], (f[0], f[1])
    f = _nearest(found)
    return (f[3], (f[0], f[1])) if f else (None, None)


def _chambers(text, lo, hi):
    return [(m.start(), m.end(), rank, code or ORDINALS[m.group(1).lower()])
            for rank, (rx, code) in enumerate(CHAMBERS) for m in rx.finditer(text, lo, hi)]


def _nearest(found):
    if not found:
        return None
    # La plus proche ; parmi celles qui la chevauchent, la plus précise : « 1re civ. » est
    # la première chambre civile, pas « une chambre civile ».
    last = max(found, key=lambda f: f[1])
    return min((f for f in found if f[0] < last[1] and last[0] < f[1]), key=lambda f: f[2])


_ENDS = [None, []]      # [texte, fins de phrase] : calculées une fois par document


def _sentence_start(text, start, floor=0):
    """Le début de la phrase où se trouve `start`, sans remonter de plus de WINDOW, ni
    avant `floor`. Les fins de phrase sont relevées une fois pour tout le texte : les
    chercher devant chaque numéro rendait un document piégé (des milliers de fois la même
    citation) plus de deux fois plus lent à lire."""
    if _ENDS[0] is not text:
        _ENDS[:] = [text, [m.end() for m in RE_SENTENCE_END.finditer(text)]]
    ends = _ENDS[1]
    i = bisect.bisect_right(ends, start) - 1
    return max(floor, start - WINDOW, ends[i] if i >= 0 else 0)


def _court_in_sentence(text, start, rx):
    """La dernière mention de la juridiction `rx` avant `start`, dans la même phrase."""
    lo = max(0, start - WINDOW)
    for end in RE_SENTENCE_END.finditer(text, lo, start):
        lo = end.end()
    found = list(rx.finditer(text, lo, start))
    return found[-1] if found else None


def unnumbered(text, used):
    """Les décisions citées sans numéro : une date qu'aucun numéro n'a prise, précédée de
    près, dans la même phrase, par une juridiction. Renvoie [(juridiction, date, span)]."""
    found = [(m, _iso(m)) for m in RE_DATE_WORDS.finditer(text)]
    found += [(m, _iso(m, False)) for m in RE_DATE_DIGITS.finditer(text)]
    out = []
    for m, day in found:
        if not day or m.start() in used:
            continue
        lo = max(0, m.start() - UNNUMBERED_GAP - 40)
        for end in RE_SENTENCE_END.finditer(text, lo, m.start()):
            lo = end.end()
        # La plus proche ; à égalité, la plus longue : « T. com. » et non le « com. » de la
        # chambre commerciale.
        marks = [(x.end(), -x.start(), court) for court, rx in MARK_ANY
                 for x in rx.finditer(text, lo, m.start())]
        if not marks:
            continue
        end, start, court = max(marks)
        start = -start
        if m.start() - end > UNNUMBERED_GAP or RE_NOT_A_DECISION.search(text, end, m.start()):
            continue
        # « Le Conseil d'État a jugé le 5 juin 2009 que ce 12 mars 2019... » : la juridiction
        # appartient à la première date, pas à celle qui suit.
        if RE_DATE_WORDS.search(text, end, m.start()) or RE_DATE_DIGITS.search(text, end, m.start()):
            continue
        out.append((court, day, (start, m.end())))
    return out


def order_of(text, start, default):
    """Le marqueur le plus PROCHE EN AMONT décide. Renvoie « judicial », « administrative »,
    ou le nom d'une juridiction hors champ (« CEDH »...).

    Une citation française se lit « Conseil d'État du 5 juin 2009, n° 308850 » : la
    juridiction précède le numéro. Chercher un marqueur « quelque part autour » ferait
    gagner la juridiction de la citation SUIVANTE. Et seulement dans la MÊME phrase :
    « T. confl., ..., n° 00012. Requête n° 45678/12 » ne rattache pas la requête au Tribunal
    des conflits."""
    lo = _sentence_start(text, start)
    before = text[lo:start]
    marks = [("judicial", MARK_JUDICIAL), ("administrative", MARK_ADMIN)] + MARK_OTHER
    nearest = max(((m.end(), name) for name, rx in marks for m in rx.finditer(before)),
                  default=None)
    return nearest[1] if nearest else default


def extract(text):
    """Renvoie (citations, remarques). Une remarque signale ce qui n'a pas pu être lu."""
    try:
        return _extract(text)
    finally:
        _ENDS[:] = [None, []]   # ne pas garder la pièce en mémoire, même après une erreur


def _extract(text):
    citations, undated, set_aside = [], [], []
    appeals = list(RE_APPEAL.finditer(text))
    appeal_numbers = {m.group(1) for m in appeals}
    conflicts = [m for m in RE_CONFLICTS.finditer(text)
                 if order_of(text, m.start(), None) == CONFLICTS]
    taken = {m.start() for m in conflicts}
    requests = [m for m in RE_REQUEST.finditer(text)
                if m.group(1) not in appeal_numbers and m.start() not in taken]
    constit = [m for m in RE_CONSTIT.finditer(text)
               if m.group(2) in CONSTIT_ALONE or order_of(text, m.start(), None) == CONSTIT]
    eu = [m for m in RE_EU.finditer(text)
          if m.group(1) == "C" or order_of(text, m.start(), None) == EU]
    caa = list(RE_CAA.finditer(text))
    rgs = list(RE_RG.finditer(text))
    tcom = [(m, court) for m in RE_TCOM_NUMBER.finditer(text)
            for court in [_court_in_sentence(text, m.start(), RE_TCOM_COURT)] if court]
    used, date_places = set(), {}
    dates = assign_dates(text, [m.span() for m in
                                appeals + requests + rgs + conflicts + constit + eu + caa]
                         + [m.span() for m, _ in tcom], used, date_places)
    seen = Seen()       # (numéro, date) : un même numéro cité à deux dates = deux citations

    def add(order, court, number, m):
        d = dates.get(m.start())
        if seen.again((order, number, d), m.span()):
            return
        citations.append({"kind": "decision", "order": order, "court": court,
                          "number": number, "cited_date": d, "span": m.span()})
        seen[(order, number, d)] = citations[-1]

    for m in conflicts:
        add("conflicts", "T. confl.", re.sub(r"\s", "", m.group(1) or m.group(2)).upper(), m)
    for m in constit:
        c = len(citations)
        add("constitutional", "Cons. const.", m.group(1), m)
        if len(citations) > c:
            citations[-1]["nature"] = m.group(2)       # « DC » : affiché, pas cherché
    for m in eu:
        add("eu", "CJUE" if m.group(1) == "C" else "Trib. UE",
            f"{m.group(1)}-{int(m.group(2))}/{m.group(3)}", m)
    for m in caa:
        add("caa", "CAA", m.group(1), m)
    for m, court in tcom:
        link = RE_TCOM_CITY.match(text, court.end())
        city = _place(link.group(0), _city(text[link.end():]))
        d = dates.get(m.start())
        if seen.again(("tcom", city, m.group(1), d), m.span()):
            continue
        citations.append({"kind": "decision", "order": "lower", "jurisdiction": "tcom",
                          "court": f"T. com. {city}".strip(), "place": city,
                          "number": m.group(1), "cited_date": d, "span": m.span()})
        seen[("tcom", city, m.group(1), d)] = citations[-1]

    unattached = []     # numéros sans juridiction nommée dans la phrase : montrés, pas envoyés
    for i, m in enumerate(appeals):
        number, d = m.group(1), dates.get(m.start())
        # La juridiction la plus proche en amont doit être judiciaire (pas seulement nommée
        # quelque part dans la phrase : « La Cour de cassation et la CEDH, n° 16-26694 »
        # place le numéro près de la CEDH, audit du 01/10/2026).
        named = (order_of(text, m.start(), None) == "judicial"
                 or MARK_APPEAL.search(text, _sentence_start(text, m.start()), m.start()))
        if named and seen.again((number, d), m.span()):
            continue                # une reprise : sa chambre a déjà été lue
        chamber, chamber_at = _cited_chamber(
            text, m.start(), m.end(), appeals[i + 1].start() if i + 1 < len(appeals) else None)
        if not chamber and not named:
            unattached.append(number)
            continue
        if seen.again((number, d), m.span()):
            continue
        citations.append({"kind": "decision", "order": "judicial", "court": "Cass",
                          "number": number, "cited_date": d, "span": m.span(),
                          "chamber": chamber, "_chamber_at": chamber_at})
        seen[(number, d)] = citations[-1]
        if not d:
            undated.append(number)

    for m in requests:
        number = m.group(1)
        # Sans juridiction nommée dans la phrase, « n° 308850 » n'est pas une requête du
        # Conseil d'État : « la pièce n° 308850 signée le 5 juin 2009 » n'est pas une
        # citation, et pourrait être « confirmée » (audit du 01/10/2026).
        order = order_of(text, m.start(), None)
        if order is None and not RE_SLASH_YEAR.match(text, m.end()):
            unattached.append(number)
            continue
        order = order or "administrative"
        if order == "judicial":
            set_aside.append(number)    # un n° à 5-7 chiffres près de « Cass. » : douteux
            continue
        d = dates.get(m.start())
        slash = RE_SLASH_YEAR.match(text, m.end())
        if order != "administrative" or slash:
            # Hors champ : montré, jamais envoyé dans ArianeWeb.
            if slash:
                number += slash.group(0)
            span = (m.start(), slash.end() if slash else m.end())
            if seen.again(("other", number, d), span):
                continue
            citations.append({"kind": "decision", "order": "ta" if order == "TA" else "other",
                              "court": order if order != "administrative"
                              else "juridiction non nommée",
                              "number": number, "cited_date": d, "span": span})
            seen[("other", number, d)] = citations[-1]
            continue
        if seen.again((number, d), m.span()):
            continue
        citations.append({"kind": "decision", "order": "administrative", "court": "CE",
                          "number": number, "cited_date": d, "span": m.span()})
        seen[(number, d)] = citations[-1]
        if not d:
            undated.append(number)

    remarks = []
    if undated:
        remarks.append(f"{len(undated)} numéro(s) sans date lisible à côté : "
                       f"{', '.join(undated)}. Leur date ne peut pas être contrôlée.")
    if unattached:
        remarks.append(f"{len(unattached)} numéro(s) en forme de décision, sans juridiction "
                       f"nommée dans la phrase : {', '.join(unattached[:12])}"
                       f"{'...' if len(unattached) > 12 else ''}. Non vérifiés : une citation "
                       "nomme sa juridiction (« CE », « Cass. soc. », « pourvoi n° »...).")
    if set_aside:
        remarks.append(f"{len(set_aside)} numéro(s) écarté(s), à 5-7 chiffres mais près d'une "
                       f"juridiction judiciaire : {', '.join(set_aside)}. À vérifier à la main.")
    lower, lower_remarks = extract_lower_courts(text, rgs, dates)
    by_number = {}
    for c in citations + lower:
        if c["cited_date"] and c["number"]:
            by_number.setdefault(c["number"], set()).add(c["cited_date"])
    for number, days in by_number.items():
        if len(days) > 1:
            remarks.append(f"n° {number} cité à {len(days)} dates différentes "
                           f"({', '.join(sorted(days))}) : chacune est vérifiée.")
    citations += lower
    remarks += lower_remarks
    numbered_days = {c["cited_date"] for c in citations}
    for court, day, span in unnumbered(text, used):
        # Déjà citée avec son numéro à cette date : c'est la même décision, reprise.
        if day in numbered_days:
            continue
        if not seen.again(("unnumbered", court, day), span):
            citations.append({"kind": "decision", "order": "unnumbered", "court": court,
                              "number": None, "cited_date": day, "span": span})
            seen[("unnumbered", court, day)] = citations[-1]

    articles, article_remarks = extract_articles(text)
    # Dans l'ordre du document, celui des numéros (pas du début de leur bloc) : c'est l'ordre
    # dans lequel l'avocat relira.
    both = sorted(citations + articles, key=lambda c: c.get("core", c["span"])[0])
    # Le passage entre guillemets qui suit une décision, pour le chercher dans son texte
    # (decision_quotes.py). Articles et décisions concourent : un passage va à la citation
    # la plus proche. Celui des articles est déjà rattaché, entre articles seulement.
    for i, quote in assign_quotes(text, [c.get("core", c["span"]) for c in both]).items():
        if both[i]["kind"] == "decision" and both[i].get("number"):
            both[i]["quote"] = quote
    _decision_blocks(text, [c for c in both if c["kind"] == "decision" and c.get("number")],
                     date_places)
    _apart(both)
    return both, remarks + article_remarks


# Le surlignage d'une décision : un bloc d'un seul tenant (« CE, 30 novembre 2018,
# n° 402517 »), mais seulement s'il suit un MODÈLE autorisé. Le bloc est fait des morceaux
# que le programme a retenus (la juridiction la plus proche, la chambre lue, la date
# rattachée, le numéro), séparés seulement par des mots de liaison (« du », « pourvoi »,
# « n° »...). Le moindre autre mot, chiffre ou juridiction entre deux morceaux, et c'est le
# numéro seul, comme avant. On n'interdit pas ce qui serait dangereux : on n'autorise que ce
# qui est sûr. Interdire laissait toujours passer un cas oublié (audits du 01/10/2026).

# Les juridictions nommées, et celle que chacune désigne.
# Pour le bloc, la Cour de justice et le Tribunal de l'Union sont deux juridictions : « Trib.
# UE » n'entre pas dans le bloc d'un numéro C-, ni « CJUE » dans celui d'un T- (audit du
# 01/10/2026). La CJCE est la Cour de justice sous son ancien nom ; le TPICE, le Tribunal.
_EU_NAMES = [
    ("CJUE", re.compile(r"\b(?:CJUE|CJCE|Cour\s+de\s+justice\s+(?:de\s+l['’]\s*Union"
                        r"|des\s+Communautés))", re.I)),
    ("Trib. UE", re.compile(r"\b(?:TPICE|Trib\.\s?UE|Tribunal\s+de\s+l['’]\s*Union)", re.I)),
]
_COURT_NAMES = ([(name, rx) for name, rx in MARK_ANY if name != EU] + _EU_NAMES
                + [("Cass.", rx) for rx, _ in CHAMBERS])
# Les mots de liaison permis entre deux morceaux retenus d'une décision.
_LINK = re.compile(
    r"(?:[\s,.:;()]|\b(?:du|de|des|la|le|les|l['’]|en\s+date\s+du|pourvoi|arr[êe]t|décision|"
    r"rendue?|requête|req\.|RG|R\.G\.)(?![\w'’])|\bn[°º]\.?|\bno\b)*", re.I)
# Une ville après une cour d'appel, un tribunal, une CAA : « CA Paris », « CAA de Nancy »,
# « CA Aix-en-Provence », « TJ Le Mans ». Un seul lieu : un mot, ou des mots liés par des
# traits d'union. « CA Paris Dupont » ou « CAA de Paris Le Conseil » : le mot de trop n'est
# pas un mot de liaison, le bloc revient au numéro (audit du 01/10/2026).
_CITY = re.compile(r"\s*(?:de\s+|d['’]\s*|du\s+|des\s+)?(?:(?:Le|La|Les)\s+|L['’]\s*)?"
                   r"[A-ZÀ-Þ][^\W\d_'’-]*(?:['’-][^\W\d_]+)*(?:\s+de\s+La\s+Réunion)?")


def _accepted(c):
    """Les noms de juridiction qui peuvent ouvrir le bloc de cette citation."""
    order = c.get("order")
    if order == "lower":
        return {"ca": {"CA"}, "tj": {"TJ"}, "tcom": {"T. com."}}.get(c.get("jurisdiction"),
                                                                     set())
    return {"judicial": {"Cass."}, "administrative": {"CE"}, "caa": {"CAA"},
            "constitutional": {CONSTIT}, "eu": {c.get("court")}, "conflicts": {CONFLICTS},
            "ta": {"TA"}}.get(order, {c.get("court")} if order == "other" else set())


def _court_piece(text, lo, hi, accepted):
    """(début, fin) de la juridiction nommée juste avant `hi`, si c'est l'une de `accepted` ;
    les noms collés de la même juridiction (« Cass. » puis « soc. ») en font un seul. None
    sinon : la juridiction la plus proche n'est pas celle de la citation."""
    marks = sorted({(m.start(), m.end(), name) for name, rx in _COURT_NAMES
                    for m in rx.finditer(text, lo, hi)}, key=lambda f: (f[1], f[0]))
    if not marks:
        return None
    # La plus proche, et les noms qui la chevauchent : « T. com. » se lit aussi « com. »
    # (chambre commerciale) ; c'est le nom de la citation qui compte, s'il y est.
    last = marks[-1][1]
    near = [f for f in marks if f[1] > marks[-1][0]]
    mine = [f for f in near if f[2] in accepted]
    if not mine:
        return None
    first = min(f[0] for f in mine)
    if any(f[2] not in accepted and f[0] < first for f in near):
        return None                     # une autre juridiction déborde sur celle-ci
    for a, b, name in reversed([f for f in marks if f not in near]):
        if a >= first:
            continue                    # contenu dans le nom déjà retenu
        if name not in accepted:
            if b > first:
                return None             # une autre juridiction mêlée à celle-ci
            break
        if b > first:
            first = a                   # deux noms qui se chevauchent : « Cass. soc »
        elif re.fullmatch(r"[\s,.]*", text[b:first]):
            first = a
        else:
            break
    return first, last


def _block(text, lo, start, end, c, day, chamber_at):
    """Le bloc de la décision dont le numéro est text[start:end], s'il suit le modèle ;
    sinon None."""
    pieces = [(start, end)]
    if day and day[0] >= lo:
        pieces.append(day)
    if chamber_at and chamber_at[0] >= lo:
        pieces.append(chamber_at)
    # La juridiction se cherche devant la date ou le numéro ; la chambre peut la précéder
    # (« La chambre sociale de la Cour de cassation »).
    first = min(p[0] for p in pieces if p != chamber_at)
    court = _court_piece(text, lo, first, _accepted(c))
    city = None
    if court:
        pieces.append(court)
        if c.get("order") in ("lower", "caa"):
            m = _CITY.match(text, court[1])
            # Une ville, pas une juridiction déguisée en ville (« CAA de Nancy CE »).
            if (m and m.end() > court[1]
                    and m.end() <= min(p[0] for p in pieces if p[0] >= court[1])
                    and not any(rx.search(text, court[1], m.end()) for _, rx in _COURT_NAMES)):
                city = (court[1], m.end())
                pieces.append(city)
    # Les morceaux qui se chevauchent (« Cass. soc. » et la chambre « soc. ») n'en font qu'un.
    merged = []
    for a, b in sorted(pieces):
        if merged and a <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], b))
        else:
            merged.append((a, b))
    for (_, b), (a, _) in zip(merged, merged[1:]):
        if not _LINK.fullmatch(text, b, a):
            return None                 # autre chose qu'un mot de liaison entre deux morceaux
    first, last = merged[0][0], merged[-1][1]
    if PAGE in text[first:last]:
        return None                     # sur deux pages : le numéro seul, sur sa page
    # Une seule chambre dans le bloc : celle qui a été lue.
    # Le « com. » de « T. com. » fait partie du nom du tribunal : pas une chambre.
    inside_name = c.get("order") != "judicial" and court
    for rx, _ in CHAMBERS:
        for m in rx.finditer(text, first, last):
            if chamber_at and m.start() < chamber_at[1] and chamber_at[0] < m.end():
                continue
            if inside_name and court[0] <= m.start() and m.end() <= court[1]:
                continue
            return None
    return first, last


def _decision_blocks(text, decisions, date_places):
    """Chaque décision, et chacune de ses reprises, reçoit son bloc s'il suit le modèle. Un
    bloc ne remonte jamais avant le précédent : « CE, 5 juin 2009, n° 308850 et n° 402517 »
    laisse le « CE » au premier."""
    previous = 0
    places = sorted([(c["span"], c, None) for c in decisions]
                    + [(span, c, i) for c in decisions
                       for i, span in enumerate(c.get("repeats", []))], key=lambda p: p[0][0])
    for (start, end), c, i in places:
        lo = _sentence_start(text, start, min(previous, start))
        if i is None:
            chamber_at = c.get("_chamber_at")
        else:
            # Une reprise : sa chambre à elle, qui n'entre dans le bloc que si c'est celle
            # du verdict (« Soc. » reprise en « Civ. 2e » : le numéro seul).
            code, chamber_at = _cited_chamber(text, start, end)
            if code != c.get("chamber"):
                chamber_at = None
        span = _block(text, lo, start, end, c, date_places.get(start), chamber_at)
        if not span or span == (start, end):
            previous = max(previous, end)
            continue
        previous = max(previous, span[1])
        if i is None:
            c["span"], c["core"] = span, (start, end)
        else:
            c["repeats"][i] = span
            c.setdefault("repeat_cores", {})[i] = (start, end)
    for c in decisions:
        c.pop("_chamber_at", None)


def _apart(citations):
    """Deux surlignages ne se touchent jamais : un bloc qui empiète sur une autre citation
    (ou sur une reprise) revient à son numéro. Vérifié sur le résultat final, quel que soit le
    chemin qui y a mené : les modèles disent ce qu'un bloc peut contenir, cette règle garantit
    qu'aucun mot ne porte deux couleurs (audit du 01/10/2026)."""
    places = [(c, None) for c in citations] + [(c, i) for c in citations
                                               for i in range(len(c.get("repeats", [])))]

    def span(place):
        c, i = place
        return tuple(c["span"] if i is None else c["repeats"][i])

    def core(place):
        c, i = place
        if i is None:
            return tuple(c.get("core", c["span"]))
        return tuple(c.get("repeat_cores", {}).get(i, c["repeats"][i]))

    changed = True
    while changed:
        changed = False
        places.sort(key=lambda p: span(p)[0])
        hit, reach, holder = [], -1, None
        for place in places:
            a, b = span(place)
            if a < reach:
                hit += [place, holder]
            if b > reach:
                reach, holder = b, place
        for c, i in hit:
            if span((c, i)) != core((c, i)):
                if i is None:
                    c["span"] = core((c, i))
                else:
                    c["repeats"][i] = core((c, i))
                changed = True


# Articles de codes

# Un numéro d'article : lettre facultative (L, R, D, A, avec ou sans point, étoile des
# articles réglementaires), puis des chiffres séparés par des tirets, puis des suffixes.
# Le CGI et le Code des douanes en empilent (point E de l'audit du 30/09/2026) :
# « 46 quater-0 ZZ bis », « 199 undecies B », « 238 bis-0 I », « 302 bis ZA ». Avant, tout
# s'arrêtait au premier : « 199 undecies B » était vérifié comme « 199 », un article qui
# existe, et le rapport disait « en vigueur » d'un autre article.
#   Une majuscule n'est un suffixe que seule ou par deux, jamais suivie d'une lettre, ni
#   d'un point puis d'une minuscule : « 700 CPC » (sigle), « 1240 C. civ. », « 12 Trav. »
#   n'en sont pas ; « 238 bis-0 I. » en fin de phrase, si. « C. » n'en est jamais un : c'est
#   l'abréviation de « Code » (« 1240 C. Civ. »). Et jamais insensible à la casse : sinon le
#   « du » de « 81 A du CGI » en serait un.
LATIN = (r"(?:bis|ter|quater|quinquies|sexies|septies|octies|nonies|novies|decies|undecies|"
         r"duodecies|terdecies|quaterdecies|quindecies|sexdecies|septdecies|octodecies|"
         r"novodecies|vicies|unvicies|duovicies|tervicies|quatervicies|quinvicies|sexvicies|"
         r"septvicies|octovicies|novovicies|tricies)")
# Une majuscule finale est un suffixe (« 199 undecies B »), même suivie d'un point devant
# « du », « de », « des » (« 199 undecies B. du CGI » : sans ça, le B tombait et le
# programme vérifiait l'article 199 undecies, audit du 01/10/2026). Devant un autre mot en
# minuscule, c'est une abréviation (« C. civ. ») : pas un suffixe.
SUFFIX = (rf"(?:\s{LATIN}\b|-0\b"
          r"|\s(?-i:(?!C\.)[A-Z]{1,2})(?!\w)"
          r"(?!\.\s*(?!(?:du|de|des|d['’])(?![a-zà-ÿ]))[a-zà-ÿ]))")
NUM = rf"(?:[LRDA]\.?\s?\*?\s?)?(?:1er|\d+(?:[-‑.]\d+)*){SUFFIX}*\b"
RE_ARTICLES = re.compile(
    r"\bart(?:icle)?s?\.?\s+(" + NUM + r"(?:\s*(?:,|et|à|ou)\s*" + NUM + r")*)", re.I)
RE_ONE_NUM = re.compile(NUM, re.I)
RE_SAME_CODE = re.compile(r"^\W{0,3}du code précité|^\W{0,3}(?:du|dudit|de ce)\s+(?:même\s+)?"
                          r"code\b|^\W{0,3}dudit code", re.I)
RE_QUOTE = re.compile(r"«\s*([^»]{20,})\s*»|“([^”]{20,})”|\"([^\"]{20,})\"")
RE_OTHER_TEXT = re.compile(r"\W{0,3}(?:\w+\s+){0,2}(?:de\s+la\s+|du\s+|de\s+l['’]\s*)?"
                           r"(?:loi|décret|ordonnance|convention|directive|règlement|arrêté|"
                           r"accord|traité|constitution)\b", re.I)
RE_CONVENTION = re.compile(
    r"^\W{0,3}(?:de\s+la\s+|du\s+|de\s+l['’]\s*)?(?:convention\s+collective|CCNT?\b)", re.I)
RE_ATTACHED = re.compile(
    r"^\W{0,3}(?:de\s+l['’]\s*|du\s+)(?:avenant|accord\s+(?:de\s+branche|collectif|national))",
    re.I)
RE_SAME_CONVENTION = re.compile(
    r"^\W{0,3}(?:de\s+ladite\s+convention|de\s+la\s+même\s+(?:convention|CCN)\b"
    r"|de\s+la\s+(?:même\s+)?(?:convention|CCN)"
    r"(?:\s+collective)?(?:\s+nationale)?\s+(?:précitée|susvisée|susmentionnée))", re.I)
RE_IDCC = re.compile(r"\bIDCC\s*(?:n[°ºo]\s*)?:?\s*(\d{1,4})\b", re.I)
IDCC_WINDOW = 250
CODE_AFTER = 70     # un nom de code doit suivre le numéro de près
CODE_BEFORE = 25    # ou le précéder de très près (« C. trav., art. L. 1152-1 »)
QUOTE_AFTER = 200
QUOTE_BEFORE = 15   # « ... » (art. L. 1234-5) : le texte précède, collé


# « Costello-Roberts c. Royaume-Uni », « T. com. Paris », « Cass. Soc. » : le point d'une
# abréviation n'est pas une fin de phrase. Sans ces exceptions, la date citée avant les noms
# des parties n'atteignait jamais le numéro cité après, et « T. com. Paris, 9 janvier 2026 »
# perdait sa juridiction.
ABBREVIATIONS_WITH_DOT = ["c", "com", "soc", "civ", "crim", "cass", "confl", "const", "cons",
                          "trib", "ass", "sect", "ch", "req", "art", "t", "m", "plén"]
RE_SENTENCE_END = re.compile(
    "".join(rf"(?<!\b(?i:{a}))" for a in ABBREVIATIONS_WITH_DOT)
    + r"[.;!?]\s+(?=[A-ZÀ-ÖØ-Þ«])")


def nearest_idcc(text, start, end, taken=()):
    """(position, IDCC) : l'IDCC écrit dans la MÊME PHRASE que la citation, le plus proche,
    hors ceux déjà pris (`taken`, leurs positions) ; (None, None) s'il n'y en a pas. Jamais
    déduit d'un nom, jamais repris d'une phrase voisine (sauf « ladite convention »)."""
    lo, hi = max(0, start - IDCC_WINDOW), min(len(text), end + IDCC_WINDOW)
    for m in RE_SENTENCE_END.finditer(text, lo, start):
        lo = m.end()
    m = RE_SENTENCE_END.search(text, end, hi)
    hi = m.start() + 1 if m else hi
    found = [(abs(m.start() - start), m.start(), m.group(1))
             for m in RE_IDCC.finditer(text, lo, hi) if m.start() not in taken]
    return min(found)[1:] if found else (None, None)


def normalize_number(raw):
    """Comme l'écrit Légifrance : « L. 3121-2 » -> « L3121-2 », « 1er » -> « 1 »,
    « 46 Quater-0 ZZ  bis » -> « 46 quater-0 ZZ bis » (une espace entre les suffixes)."""
    n = unicodedata.normalize("NFKC", raw).replace("‑", "-")
    n = re.sub(r"^([LRDA])[\s.*]+", r"\1", n, flags=re.I)   # « L. » : le point du préfixe seul
    n = " ".join(n.split())                                  # « 25.1 » garde son point
    n = re.sub(LATIN, lambda m: m.group(0).lower(), n, flags=re.I)
    if n.lower() == "1er":                                   # Légifrance écrit « 1 »
        return "1"
    return n[0].upper() + n[1:] if n[0].isalpha() else n


def assign_quotes(text, spans):
    """Rattache chaque passage entre guillemets à UNE seule citation d'article, la plus
    proche : collé avant (« ... » (art. X)) ou peu après (art. X : « ... »). Renvoie
    {indice de la citation: texte cité}."""
    best = {}
    for m in RE_QUOTE.finditer(text):
        body = " ".join(next(g for g in m.groups() if g).split())
        candidates = []
        for i, (start, end) in enumerate(spans):
            if (m.end() <= start and start - m.end() <= QUOTE_BEFORE
                    and not RE_SENTENCE_END.search(text, m.end() - 1, start)):
                # « ... » (C. civ., art. X) : collé, sans fin de phrase entre les deux
                candidates.append((start - m.end(), i))
            elif m.start() >= end and m.start() - end <= QUOTE_AFTER:
                candidates.append((m.start() - end, i))
        if candidates:
            dist, i = min(candidates)
            if i not in best or dist < best[i][0]:
                best[i] = (dist, body)
    return {i: body for i, (_, body) in best.items()}


# Lois, ordonnances et décrets non codifiés : « loi n° 89-462 du 6 juillet 1989 », « loi
# 89-462 », « loi du 6 juillet 1989 », « décret n°67-223 ». Un numéro ou une date est exigé :
# « la loi » seule ne désigne rien.
_TEXT_REF = (r"(?P<nature>loi(?:\s+organique)?|ordonnance|d[ée]cret(?:-loi)?)"
             r"(?:\s*n[°ºo]\s*(?P<num>\d{2,4}-\d{1,5})|\s+(?P<num2>\d{2,4}-\d{1,5}))?"
             r"(?:\s*,?\s+du\s+(?P<day>1er|\d{1,2})\s+(?P<month>" + "|".join(MONTHS) +
             r")\s+(?P<year>\d{4}))?")
RE_TEXT_AFTER = re.compile(r"^\W{0,3}(?:de\s+la\s+|du\s+|de\s+l['’]\s*)?" + _TEXT_REF, re.I)
RE_TEXT_BEFORE = re.compile(r"(?:^|\W)" + _TEXT_REF + r"[\s,;:]*$", re.I)
RE_SAME_TEXT = re.compile(r"^\W{0,3}(?:de\s+la\s+(?:même\s+)?|de\s+ladite\s+|de\s+cette\s+|du\s+"
                          r"(?:même\s+)?|dudit\s+|de\s+ce\s+)(?P<nature>loi|ordonnance|d[ée]cret)"
                          r"(?:\s+(?:précitée?|susvisée?))?\b", re.I)
TEXT_BEFORE = 100
TEXT_NATURES = {"loi": "LOI", "loi organique": "LOI", "ordonnance": "ORDONNANCE",
                "décret": "DECRET", "decret": "DECRET", "décret-loi": "DECRET",
                "decret-loi": "DECRET"}


def _text_ref(m):
    """{nature, number, date} d'un texte nommé, ou None s'il n'a ni numéro ni date."""
    if not m:
        return None
    number = m.group("num") or m.group("num2")
    day = _iso(re.match(r"(\d{1,2})(?:er)?\s+(\S+)\s+(\d{4})",
                        f"{1 if m.group('day').lower() == '1er' else m.group('day')} "
                        f"{m.group('month')} {m.group('year')}")) if m.group("day") else None
    if not number and not day:
        return None
    nature = TEXT_NATURES[" ".join(m.group("nature").lower().split())]
    return {"text_nature": nature, "text_number": number, "text_date": day}


MONTH_NAMES = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
               "septembre", "octobre", "novembre", "décembre"]


def in_words(iso):
    """« 1989-07-06 » -> « 6 juillet 1989 », comme dans les titres de Légifrance."""
    year, month, day = iso.split("-")
    return f"{'1er' if day == '01' else int(day)} {MONTH_NAMES[int(month) - 1]} {year}"


def _text_label(ref):
    """« Loi n° 89-462 du 6 juillet 1989 », pour le rapport."""
    name = {"LOI": "Loi", "ORDONNANCE": "Ordonnance", "DECRET": "Décret"}[ref["text_nature"]]
    return (name + (f" n° {ref['text_number']}" if ref["text_number"] else "")
            + (f" du {in_words(ref['text_date'])}" if ref["text_date"] else ""))


class Seen(dict):
    """Les citations déjà relevées, par clé. Une citation reprise plus loin dans le document
    n'est vérifiée qu'une fois ; les places de ses reprises sont gardées (« repeats ») pour
    que le PDF annoté les marque aussi."""

    def again(self, key, span, core=None):
        """True si `key` est déjà relevée : la reprise est notée, rien d'autre à faire.
        `core` : le numéro seul, quand `span` couvre aussi le code ou la juridiction."""
        if key in self:
            repeats = self[key].setdefault("repeats", [])
            if core and tuple(core) != tuple(span):
                self[key].setdefault("repeat_cores", {})[len(repeats)] = core
            repeats.append(span)
            return True
        return False


def _word_start(text, start, end):
    """Le premier caractère de mot à partir de `start` (avant `end`)."""
    while start < end and not text[start].isalnum():
        start += 1
    return start


# Entre un article et son code : des mots de liaison, et au plus un alinéa ; ou une
# parenthèse (« art. 1240 (C. civ.) »).
_TO_CODE = re.compile(r"\s*,?\s*(?:(?:alinéa|al\.)\s*(?:\d{1,2}|1er|premier)\s*,?\s*)?"
                      r"(?:du|de\s+la|de\s+l['’]|des|de|au)?\s*|\s*\(\s*", re.I)
# Entre « convention collective » et son IDCC : rien, ou « nationale », et une parenthèse
# (« convention collective nationale (IDCC 1979 »). Pas de nom : un programme ne distingue
# pas « des hôtels, cafés, restaurants » de « des salariés contestent le licenciement », et
# peindre une phrase sous la couleur de l'article serait mentir. L'IDCC reste dans le rapport
# (audits du 01/10/2026).
_CONVENTION_NAME = re.compile(r"(?:\s+nationale)?\s*,?\s*\(?\s*", re.I)


def _convention_name(text, lo, hi):
    return bool(_CONVENTION_NAME.fullmatch(text, lo, hi))


# Un article qui a déjà son code ou sa loi écrit devant lui (« C. civ., art. 1240 », « loi
# n° 89-462..., article 22 »), et que l'article d'avant n'a pas pris, ne prend un code ou un
# texte qui le suit que si « du », « de la », « des »... l'y rattachent (« alinéa 2 du Code
# du travail »). Après une virgule, « et », « ainsi que », « notamment », un alinéa, un
# tiret, c'est celui de la citation suivante : « C. civ., art. 1240, C. trav., art.
# L. 1152-1 » cherchait le 1240 dans le Code du travail, « loi n° 89-462..., article 22,
# ainsi que C. civ., art. 1240 » l'article 22 dans le Code civil (audits du 01/10/2026).
_LINKED = re.compile(r"\W{0,3}(?:(?:alinéa|al\.)\s*(?:\d{1,2}|1er|premier)\s*,?\s*)?"
                     r"(?:du|des|de\s+la|de\s+l['’]|de|au|aux)\s*", re.I)


def _fit(text, reach, core, count):
    """Le bloc d'un article (article et code, loi ou convention), s'il n'y a qu'un numéro et
    que le bloc tient sur une page ; sinon le numéro seul."""
    if count == 1 and PAGE not in text[reach[0]:reach[1]]:
        return reach
    return core


def extract_articles(text):
    """Renvoie (citations d'articles, remarques).

    « span » couvre l'article ET ce à quoi il est rattaché (« article 1240 du Code civil »,
    « C. trav., art. L. 1152-1 », « article 22 de la loi n° 89-462 ») : le PDF annoté le
    surligne d'un seul tenant, et un rattachement absurde se voit sur la page. « core » :
    l'article seul, pour le retrouver si le bloc entier ne se retrouve pas sur la page."""
    matches = list(RE_ARTICLES.finditer(text))
    quotes = assign_quotes(text, [(m.start(), m.end()) for m in matches])
    citations, seen, no_code, attached = [], Seen(), [], []
    last_code = last_idcc = last_text = None
    idcc_taken = set()      # les IDCC déjà rattachés à un article (leur position)
    taken_until = 0         # la fin du bloc peint de l'article précédent
    used_until = 0          # la fin du code ou du texte qu'il a pris, peint ou non
    for index, m in enumerate(matches):
        # Le code, le texte ou la convention se cherchent dans la même phrase : « L'article
        # 1240. Cette solution ne figure pas au code de commerce » ne cite pas le Code de
        # commerce (audit du 01/10/2026).
        stop = RE_SENTENCE_END.search(text, m.end(), m.end() + CODE_AFTER)
        after = text[m.end(): stop.start() + 1 if stop else m.end() + CODE_AFTER]
        before = text[max(0, m.start() - CODE_BEFORE): m.start()]
        found_numbers = list(RE_ONE_NUM.finditer(m.group(1)))
        numbers = [normalize_number(x.group(0)) for x in found_numbers]
        quote = quotes.get(index) if len(numbers) == 1 else None
        # Ce que surligne chaque numéro : l'article entier s'il est seul ; sinon chacun son
        # numéro (« articles 1240 et 1241 » : deux verdicts, jamais peints l'un sur l'autre).
        cores = ([m.span()] if len(numbers) == 1 else
                 [(m.start(1) + x.start(), m.start(1) + x.end()) for x in found_numbers])

        if RE_ATTACHED.match(after):
            attached.extend(numbers)            # avenant, accord : pas le texte de base
            taken_until = m.end()
            used_until = m.end()
            continue
        same = RE_SAME_CONVENTION.match(after)
        named = same or RE_CONVENTION.match(after)
        if named:
            reach = (m.start(), m.end() + named.end())
            if same and last_idcc:
                idcc = last_idcc
            else:
                # Un IDCC déjà rattaché à l'article précédent n'est repris que par « la même
                # convention » : « article 5 de la convention collective (IDCC 1979) et
                # article 99 de la convention collective » ne dit pas laquelle est la seconde.
                where, idcc = nearest_idcc(text, m.start(), m.end(), idcc_taken)
                if idcc:
                    idcc_taken.add(where)
                    # Le bloc va jusqu'à l'IDCC qui a servi, s'il suit la convention et que
                    # rien d'autre ne les sépare que son nom (« des hôtels, cafés,
                    # restaurants (IDCC 1979 »).
                    told = RE_IDCC.match(text, where)
                    if where >= reach[1] and _convention_name(text, reach[1], where):
                        reach = (reach[0], told.end())
            last_idcc = idcc or last_idcc
            taken_until = reach[1]
            used_until = reach[1]
            for number, core in zip(numbers, cores):
                span = _fit(text, reach, core, len(numbers))
                if seen.again(("idcc", idcc, number), span, core):
                    continue
                citations.append({"kind": "convention_article", "order": "legislation",
                                  "court": f"IDCC {idcc}" if idcc else "convention collective",
                                  "idcc": idcc, "number": number, "cited_date": None,
                                  "quote": quote, "span": span, "core": core})
                seen[("idcc", idcc, number)] = citations[-1]
            continue

        # Le code nommé après l'article : avant toute autre mention d'article (sinon il
        # appartient à la citation suivante), sans autre texte nommé entre les deux
        # (« article 22 de la loi du 6 juillet 1989 » n'est pas un article de code).
        found = find_code(after)
        found_before = find_code(before, last=True)
        text_before = (None if found_before else
                       RE_TEXT_BEFORE.search(text, max(0, m.start() - TEXT_BEFORE), m.start()))
        # Ce que l'article a à lui, écrit devant : un code collé, ou une loi, un décret, une
        # ordonnance juste avant ; et que l'article précédent n'a pas déjà pris.
        written_before = bool(found_before
                              and re.fullmatch(r"[\s,;:]*", before[found_before[2]:])
                              and m.start() - len(before) + found_before[1] >= used_until)
        own_before = written_before or bool(
            text_before and _text_ref(text_before)
            and _word_start(text, text_before.start(), m.start()) >= used_until)
        code_after = (found and not RE_ARTICLES.search(after[:found[1]])
                      and not RE_OTHER_TEXT.search(after[:found[1]]))
        if code_after and own_before and not _LINKED.fullmatch(after, 0, found[1]):
            code_after = None
        # « art. 1241 du même code, C. trav., art. L. 1152-1 » : le « même code » l'emporte
        # sur le code de la citation suivante (audit du 01/10/2026). Pas « du Code du
        # travail », qui se lit aussi « du code ».
        same = RE_SAME_CODE.search(after)
        same_code = bool(same and last_code and not (found and found[1] < same.end()))
        if same_code:
            code_after = None

        # Un article de loi, d'ordonnance ou de décret non codifié.
        named = RE_TEXT_AFTER.match(after)
        if (named and own_before
                and not _LINKED.fullmatch(after, 0, named.start("nature"))):
            named = None
        ref = _text_ref(named)
        reach = (m.start(), m.end() + named.end()) if ref else m.span()
        same = RE_SAME_TEXT.match(after)
        if not ref and same and last_text and (TEXT_NATURES[same.group("nature").lower()]
                                               == last_text["text_nature"]):
            ref = last_text
            reach = (m.start(), m.end() + same.end())
        # Le texte nommé juste avant, sauf si l'article a son code après lui : « article 22
        # de la loi n° 89-462 du 6 juillet 1989, article 1240 du Code civil » cherchait
        # l'article 1240 dans la loi de 1989. Un code qui n'est pas rattaché a été écarté plus
        # haut : « loi n° 89-462..., article 22, C. civ., art. 1240 » garde la loi (audits du
        # 01/10/2026).
        if not ref and not code_after and not same_code and text_before:
            named = text_before
            ref = _text_ref(named)
            if ref:
                reach = (_word_start(text, named.start(), m.start()), m.end())
                if reach[0] < taken_until:
                    reach = m.span()    # le texte est déjà dans le bloc de l'article précédent
        if ref:
            last_text = ref
            taken_until = reach[1]
            used_until = max(m.end(), reach[1])
            for number, core in zip(numbers, cores):
                span = _fit(text, reach, core, len(numbers))
                key = ("text", ref["text_nature"], ref["text_number"], ref["text_date"], number)
                if seen.again(key, span, core):
                    continue
                citations.append({"kind": "text_article", "order": "legislation",
                                  "court": _text_label(ref), **ref, "number": number,
                                  "cited_date": None, "quote": quote, "span": span,
                                  "core": core})
                seen[key] = citations[-1]
            continue

        code = None
        same = RE_SAME_CODE.search(after)
        other = RE_OTHER_TEXT.match(after)
        used = m.end()
        if code_after:
            code = found[0]
            used = m.end() + found[2]
            # Le bloc va jusqu'au code s'il n'en est séparé que par « du », « de la »,
            # « , alinéa 2, du »... : « article 1240, CE 5 juin 2009, du Code civil » laisse
            # l'article seul.
            reach = m.span()
            if _TO_CODE.fullmatch(after, 0, found[1]):
                reach = (m.start(), m.end() + found[2])
                if "(" in after[:found[1]] and after[found[2]:found[2] + 1] == ")":
                    reach = (reach[0], reach[1] + 1)    # la parenthèse fermée avec le code
        elif same and last_code:
            code = last_code
            used = m.end() + same.end()
            reach = (m.start(), m.end() + same.end())
        elif written_before or not other or RE_ARTICLES.search(after, 0, other.end()):
            # (Un texte qui suit sans lui être rattaché est celui de la citation suivante :
            # « C. civ., art. 1240, article 31 du décret ... » laissait le 1240 sans code.)
            # Code placé avant : il doit être collé à l'article (« C. trav., art. L. 1152-1 »).
            found = find_code(before, last=True)
            if found and re.fullmatch(r"[\s,;:]*", before[found[2]:]):
                code = found[0]
                reach = (m.start() - len(before) + found[1], m.end())
                if reach[0] < taken_until:
                    # « article 1240 du Code civil, art. 1241 » : le code est déjà dans le
                    # bloc du 1240 ; le 1241 garde son numéro seul.
                    reach = m.span()
        used_until = used
        if not code:
            no_code.extend(numbers)
            taken_until = m.end()
            continue
        last_code = code
        taken_until = reach[1]
        for number, core in zip(numbers, cores):
            span = _fit(text, reach, core, len(numbers))
            if seen.again((code, number), span, core):
                continue
            citations.append({"kind": "article", "order": "legislation", "court": code,
                              "code": code, "number": number, "cited_date": None,
                              "quote": quote, "span": span, "core": core})
            seen[(code, number)] = citations[-1]
    remarks = []
    if no_code:
        remarks.append(f"{len(no_code)} article(s) cité(s) sans code reconnu : "
                       f"{', '.join(no_code[:12])}{'...' if len(no_code) > 12 else ''}. "
                       "Ni code ni texte identifiable à côté : une loi ou un décret cité sans "
                       "numéro ni date, un arrêté, ou un code que ce programme ne reconnaît "
                       "pas encore. Non vérifiés.")
    if attached:
        remarks.append(f"{len(attached)} article(s) d'avenant ou d'accord collectif : "
                       f"{', '.join(attached[:12])}. Seul le texte de base des conventions "
                       "est vérifié.")
    return citations, remarks


# Cours d'appel et tribunaux judiciaires

# Un RG : deux chiffres (l'année), une barre, quatre ou cinq chiffres. On l'exige précédé de
# « RG » ou « n° » : sinon « 03/2019 » (un mois) passerait pour un numéro.
RE_RG = re.compile(r"(?:\bRG|\bR\.G\.|n[°º])\s*(?:n[°º]\s*)?:?\s*(\d{2}/\d{4,5})\b")
RE_LOWER_COURT = re.compile(
    r"\b(?P<kind>CA|cour\s+d['’]\s*appel|TJ|TGI|tribunal\s+judiciaire|"
    r"tribunal\s+de\s+grande\s+instance)\b\s*(?P<link>de\s+|d['’]\s*|du\s+|des\s+)?", re.I)
CITY_LINKS = {"en", "de", "du", "des", "sur", "les", "la", "le", "lès", "d", "l"}


def _place(link, city):
    """La ville avec son article : « tribunal judiciaire du Mans » -> « Le Mans », « des
    Sables-d'Olonne » -> « Les Sables-d'Olonne ». Sans « du » ni « des » lus, ces tribunaux
    n'étaient pas reconnus (01/10/2026)."""
    word = link.split()[-1].lower() if link.strip() else ""
    if city and word in ("du", "des") and not re.match(r"(?:Le|La|Les)\s|L['’]", city):
        return ("Le " if word == "du" else "Les ") + city
    return city


def _city(text):
    """Le nom de ville qui suit « CA » ou « tribunal judiciaire de » : mots à majuscule,
    reliés par des tirets ou par en, de, sur... Vide si rien de tel."""
    words = re.findall(r"[\wÀ-ÿ]+|['’-]|\s+", text[:60])
    out, pending = [], []
    for w in words:
        if w.isspace() or w in "-'’":
            pending.append(w)
            continue
        if w[0].isupper():
            out += pending + [w]
            pending = []
        elif w.lower() in CITY_LINKS and out:
            pending.append(w)
        else:
            break
    return "".join(out).strip()


def extract_lower_courts(text, rgs, dates):
    citations, seen, no_court = [], Seen(), []
    for m in rgs:
        number = m.group(1)
        lo = max(0, m.start() - WINDOW)
        for end in RE_SENTENCE_END.finditer(text, lo, m.start()):
            lo = end.end()
        courts = list(RE_LOWER_COURT.finditer(text, lo, m.start()))
        city = (_place(courts[-1].group("link") or "", _city(text[courts[-1].end():]))
                if courts else "")
        if not courts or not city:
            no_court.append(number)
            continue
        kind = courts[-1].group("kind").lower()
        jurisdiction = "ca" if kind.startswith(("ca", "cour")) else "tj"
        d = dates.get(m.start())
        if seen.again((jurisdiction, city, number, d), m.span()):
            continue
        label = ("CA " if jurisdiction == "ca" else "TJ ") + city
        citations.append({"kind": "decision", "order": "lower", "court": label,
                          "jurisdiction": jurisdiction, "place": city, "number": number,
                          "cited_date": d, "span": m.span()})
        seen[(jurisdiction, city, number, d)] = citations[-1]
    remarks = []
    if no_court:
        remarks.append(f"{len(no_court)} numéro(s) RG sans cour d'appel ni tribunal judiciaire "
                       f"reconnu dans la même phrase : {', '.join(no_court[:12])}. Un RG seul "
                       "n'identifie pas une décision : non vérifiés.")
    return citations, remarks

