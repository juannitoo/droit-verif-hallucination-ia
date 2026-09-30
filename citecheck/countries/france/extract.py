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
import re
import unicodedata
from datetime import date

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
RE_TCOM_CITY = re.compile(r"\s*,?\s*(?:de\s+|d['’]\s*|du\s+)?")
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


def assign_dates(text, spans, used=None):
    """Rattache chaque date à UN seul numéro de décision : le plus proche, dans la même
    phrase. Renvoie {début du numéro: date}.

    Avant (audit du 29/09/2026, K3) : chaque numéro prenait la date la plus proche, même
    celle de son voisin. « CE n° 308850 du 5 juin 2009 et n° 402517 » datait les deux du
    5 juin 2009, et le programme pouvait « confirmer » une association que le document n'a
    jamais faite."""
    starts = sorted(spans)
    best = {}
    dates = [(m, _iso(m)) for m in RE_DATE_WORDS.finditer(text)]
    dates += [(m, _iso(m, False)) for m in RE_DATE_DIGITS.finditer(text)]
    for m, day in dates:
        if not day:
            continue
        candidates = []
        for start, end in starts:
            gap = m.start() - end if m.start() >= end else start - m.end()
            if gap < 0 or gap > WINDOW:
                continue
            lo, hi = (end, m.start()) if m.start() >= end else (m.end(), start)
            if RE_SENTENCE_END.search(text, max(0, lo - 1), hi):
                continue                    # une fin de phrase les sépare
            candidates.append((gap, start))
        if candidates:
            gap, start = min(candidates)
            if start not in best or gap < best[start][0]:
                best[start] = (gap, day, m.start())
    if used is not None:
        used.update(where for _, _, where in best.values())
    return {start: day for start, (_, day, _) in best.items()}


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
    lo = max(0, start - WINDOW)
    for m in RE_SENTENCE_END.finditer(text, lo, start):
        lo = m.end()
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
                return None
            return min((f for f in found if f[0] < first[1] and first[0] < f[1]),
                       key=lambda f: f[2])[3]
    return _nearest(found)


def _chambers(text, lo, hi):
    return [(m.start(), m.end(), rank, code or ORDINALS[m.group(1).lower()])
            for rank, (rx, code) in enumerate(CHAMBERS) for m in rx.finditer(text, lo, hi)]


def _nearest(found):
    if not found:
        return None
    # La plus proche ; parmi celles qui la chevauchent, la plus précise : « 1re civ. » est
    # la première chambre civile, pas « une chambre civile ».
    last = max(found, key=lambda f: f[1])
    return min((f for f in found if f[0] < last[1] and last[0] < f[1]), key=lambda f: f[2])[3]


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
    lo = max(0, start - WINDOW)
    for end in RE_SENTENCE_END.finditer(text, lo, start):
        lo = end.end()
    before = text[lo:start]
    marks = [("judicial", MARK_JUDICIAL), ("administrative", MARK_ADMIN)] + MARK_OTHER
    nearest = max(((m.end(), name) for name, rx in marks for m in rx.finditer(before)),
                  default=None)
    return nearest[1] if nearest else default


def extract(text):
    """Renvoie (citations, remarques). Une remarque signale ce qui n'a pas pu être lu."""
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
    used = set()
    dates = assign_dates(text, [m.span() for m in
                                appeals + requests + rgs + conflicts + constit + eu + caa]
                         + [m.span() for m, _ in tcom], used)
    seen = set()        # (numéro, date) : un même numéro cité à deux dates = deux citations

    def add(order, court, number, m):
        d = dates.get(m.start())
        if (order, number, d) in seen:
            return
        seen.add((order, number, d))
        citations.append({"kind": "decision", "order": order, "court": court,
                          "number": number, "cited_date": d, "span": m.span()})

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
        city = _city(text[court.end():][len(RE_TCOM_CITY.match(text, court.end()).group(0)):])
        d = dates.get(m.start())
        if ("tcom", city, m.group(1), d) in seen:
            continue
        seen.add(("tcom", city, m.group(1), d))
        citations.append({"kind": "decision", "order": "lower", "jurisdiction": "tcom",
                          "court": f"T. com. {city}".strip(), "place": city,
                          "number": m.group(1), "cited_date": d, "span": m.span()})

    for m in appeals:
        number, d = m.group(1), dates.get(m.start())
        if (number, d) in seen:
            continue
        seen.add((number, d))
        citations.append({"kind": "decision", "order": "judicial", "court": "Cass",
                          "number": number, "cited_date": d, "span": m.span(),
                          "chamber": cited_chamber(
                              text, m.start(), m.end(),
                              min((a.start() for a in appeals if a.start() > m.start()),
                                  default=None))})
        if not d:
            undated.append(number)

    for m in requests:
        number = m.group(1)
        order = order_of(text, m.start(), "administrative")
        if order == "judicial":
            set_aside.append(number)    # un n° à 5-7 chiffres près de « Cass. » : douteux
            continue
        d = dates.get(m.start())
        slash = RE_SLASH_YEAR.match(text, m.end())
        if order != "administrative" or slash:
            # Hors champ : montré, jamais envoyé dans ArianeWeb.
            if slash:
                number += slash.group(0)
            if ("other", number, d) in seen:
                continue
            seen.add(("other", number, d))
            citations.append({"kind": "decision", "order": "ta" if order == "TA" else "other",
                              "court": order if order != "administrative"
                              else "juridiction non nommée",
                              "number": number, "cited_date": d,
                              "span": (m.start(), slash.end() if slash else m.end())})
            continue
        if (number, d) in seen:
            continue
        seen.add((number, d))
        citations.append({"kind": "decision", "order": "administrative", "court": "CE",
                          "number": number, "cited_date": d, "span": m.span()})
        if not d:
            undated.append(number)

    remarks = []
    if undated:
        remarks.append(f"{len(undated)} numéro(s) sans date lisible à côté : "
                       f"{', '.join(undated)}. Leur date ne peut pas être contrôlée.")
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
        if ("unnumbered", court, day) not in seen:
            seen.add(("unnumbered", court, day))
            citations.append({"kind": "decision", "order": "unnumbered", "court": court,
                              "number": None, "cited_date": day, "span": span})

    articles, article_remarks = extract_articles(text)
    # Dans l'ordre du document : c'est l'ordre dans lequel l'avocat relira.
    both = sorted(citations + articles, key=lambda c: c["span"][0])
    return both, remarks + article_remarks


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
SUFFIX = (rf"(?:\s{LATIN}\b|-0\b"
          r"|\s(?-i:(?!C\.)[A-Z]{1,2})(?!\w)(?!\.\s*[a-zà-ÿ]))")
NUM = rf"(?:[LRDA]\.?\s?\*?\s?)?(?:1er|\d+(?:[-‑.]\d+)*){SUFFIX}*\b"
RE_ARTICLES = re.compile(
    r"\bart(?:icle)?s?\.?\s+(" + NUM + r"(?:\s*(?:,|et|à|ou)\s*" + NUM + r")*)", re.I)
RE_ONE_NUM = re.compile(NUM, re.I)
RE_SAME_CODE = re.compile(r"^\W{0,3}(?:du|dudit|de ce)\s+(?:même\s+)?code\b|^\W{0,3}dudit code"
                          r"|^\W{0,3}du code précité", re.I)
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
    r"^\W{0,3}(?:de\s+ladite\s+convention|de\s+la\s+(?:même\s+)?(?:convention|CCN)"
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


def nearest_idcc(text, start, end):
    """L'IDCC écrit dans la MÊME PHRASE que la citation, le plus proche, ou None. Jamais
    déduit d'un nom, jamais repris d'une phrase voisine (sauf « ladite convention »)."""
    lo, hi = max(0, start - IDCC_WINDOW), min(len(text), end + IDCC_WINDOW)
    for m in RE_SENTENCE_END.finditer(text, lo, start):
        lo = m.end()
    m = RE_SENTENCE_END.search(text, end, hi)
    hi = m.start() + 1 if m else hi
    found = [(abs(m.start() - start), m.group(1)) for m in RE_IDCC.finditer(text, lo, hi)]
    return min(found)[1] if found else None


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


def extract_articles(text):
    """Renvoie (citations d'articles, remarques)."""
    matches = list(RE_ARTICLES.finditer(text))
    quotes = assign_quotes(text, [(m.start(), m.end()) for m in matches])
    citations, seen, no_code, attached = [], set(), [], []
    last_code = last_idcc = None
    for index, m in enumerate(matches):
        after = text[m.end(): m.end() + CODE_AFTER]
        before = text[max(0, m.start() - CODE_BEFORE): m.start()]
        numbers = [normalize_number(x) for x in RE_ONE_NUM.findall(m.group(1))]
        quote = quotes.get(index) if len(numbers) == 1 else None

        if RE_ATTACHED.match(after):
            attached.extend(numbers)            # avenant, accord : pas le texte de base
            continue
        same = RE_SAME_CONVENTION.match(after)
        if same or RE_CONVENTION.match(after):
            idcc = last_idcc if same and last_idcc else nearest_idcc(text, m.start(), m.end())
            last_idcc = idcc or last_idcc
            for number in numbers:
                if ("idcc", idcc, number) in seen:
                    continue
                seen.add(("idcc", idcc, number))
                citations.append({"kind": "convention_article", "order": "legislation",
                                  "court": f"IDCC {idcc}" if idcc else "convention collective",
                                  "idcc": idcc, "number": number, "cited_date": None,
                                  "quote": quote, "span": m.span()})
            continue

        code = None
        found = find_code(after)
        # Le code doit venir avant toute autre mention d'article (sinon il appartient à la
        # citation suivante), et aucun autre texte ne doit être nommé entre les deux
        # (« article 22 de la loi du 6 juillet 1989 » n'est pas un article de code).
        if (found and not RE_ARTICLES.search(after[:found[1]])
                and not RE_OTHER_TEXT.search(after[:found[1]])):
            code = found[0]
        elif RE_SAME_CODE.search(after) and last_code:
            code = last_code
        elif not RE_OTHER_TEXT.match(after):
            # Code placé avant : il doit être collé à l'article (« C. trav., art. L. 1152-1 »).
            found = find_code(before, last=True)
            if found and re.fullmatch(r"[\s,;:]*", before[found[2]:]):
                code = found[0]
        if not code:
            no_code.extend(numbers)
            continue
        last_code = code
        for number in numbers:
            if (code, number) in seen:
                continue
            seen.add((code, number))
            citations.append({"kind": "article", "order": "legislation", "court": code,
                              "code": code, "number": number, "cited_date": None,
                              "quote": quote, "span": m.span()})
    remarks = []
    if no_code:
        remarks.append(f"{len(no_code)} article(s) cité(s) sans code reconnu : "
                       f"{', '.join(no_code[:12])}{'...' if len(no_code) > 12 else ''}. "
                       "Ce sont souvent des articles de lois ou de décrets non codifiés, que "
                       "ce programme ne vérifie pas ; ou d'un code qu'il ne reconnaît pas "
                       "encore.")
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
    r"tribunal\s+de\s+grande\s+instance)\b\s*(?:de\s+|d['’]\s*)?", re.I)
CITY_LINKS = {"en", "de", "du", "des", "sur", "les", "la", "le", "lès", "d", "l"}


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
    citations, seen, no_court = [], set(), []
    for m in rgs:
        number = m.group(1)
        lo = max(0, m.start() - WINDOW)
        for end in RE_SENTENCE_END.finditer(text, lo, m.start()):
            lo = end.end()
        courts = list(RE_LOWER_COURT.finditer(text, lo, m.start()))
        city = _city(text[courts[-1].end():]) if courts else ""
        if not courts or not city:
            no_court.append(number)
            continue
        kind = courts[-1].group("kind").lower()
        jurisdiction = "ca" if kind.startswith(("ca", "cour")) else "tj"
        d = dates.get(m.start())
        if (jurisdiction, city, number, d) in seen:
            continue
        seen.add((jurisdiction, city, number, d))
        label = ("CA " if jurisdiction == "ca" else "TJ ") + city
        citations.append({"kind": "decision", "order": "lower", "court": label,
                          "jurisdiction": jurisdiction, "place": city, "number": number,
                          "cited_date": d, "span": m.span()})
    remarks = []
    if no_court:
        remarks.append(f"{len(no_court)} numéro(s) RG sans cour d'appel ni tribunal judiciaire "
                       f"reconnu dans la même phrase : {', '.join(no_court[:12])}. Un RG seul "
                       "n'identifie pas une décision : non vérifiés.")
    return citations, remarks

