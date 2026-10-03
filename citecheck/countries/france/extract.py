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
                  rendue « à vérifier à la main » ; de même « l'arrêt rendu le 31 janvier
                  2025 par la cour d'appel de Lyon », la juridiction après la date. Jamais
                  cherchée : il faudrait envoyer le nom des parties, qui vient du document
  dates en toutes lettres (« 5 juin 2009 ») et en chiffres (05/06/2009)
  articles      : « article L. 3121-2 du Code du travail », « art. 1240 C. civ. »,
                  « C. trav., art. L. 1152-1 », « articles L. 1234-1 et L. 1234-5 du ... »,
                  « du même code » ; et le texte cité entre guillemets juste à côté
  conventions   : « article 21 de la convention collective nationale des HCR (IDCC
                  1979) » ; l'IDCC est lu à proximité, jamais déduit du nom
  autres textes : conventions internationales, textes de l'Union, arrêtés, textes locaux,
                  code ou Constitution sans article : relevés en gris, jamais vérifiés

CE QU'IL NE FAIT JAMAIS
  Deviner. Un numéro sans date lisible sort sans date, et le contrôle de date est annoncé
  impossible. Tout ce qu'il n'a pas su rattacher est signalé : un trou est un trou.
"""
import bisect
import re
import unicodedata
from datetime import date

from ...reader import PAGE
from .codes import find_code, find_codes

MONTHS = {"janvier": 1, "février": 2, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5,
          "juin": 6, "juillet": 7, "août": 8, "aout": 8, "septembre": 9, "octobre": 10,
          "novembre": 11, "décembre": 12, "decembre": 12}
# Les mois abrégés de la doctrine et des conclusions (« Soc., 7 avr. 2022 », « 17 juill.
# 2019 ») : sans eux, la date de l'arrêt n'était pas lue, donc pas contrôlée.
SHORT_MONTHS = {"janv.": 1, "févr.": 2, "fevr.": 2, "fév.": 2, "fev.": 2, "avr.": 4,
                "juil.": 7, "juill.": 7, "sept.": 9, "oct.": 10, "nov.": 11, "déc.": 12,
                "dec.": 12}
DATE_MONTHS = {**MONTHS, **SHORT_MONTHS}

# Numéro de pourvoi : deux chiffres, tiret, deux chiffres, point facultatif, trois chiffres.
RE_APPEAL = re.compile(r"\b(\d{2}-\d{2}\.?\d{3})\b")
# « Soc, 6 mai 2009 numéro 07 44 485 » : des espaces à la place du tiret et du point, admis
# seulement derrière « numéro », « n° » ou « pourvoi » (vraies décisions du 02/10/2026).
RE_APPEAL_SPACED = re.compile(r"(?:\bnuméro|\bn[°ºo]|\bpourvoi)\s*(\d{2})\s(\d{2})\s(\d{3})\b",
                              re.I)


class _Spaced:
    """Un pourvoi écrit « 07 44 485 », lu comme « 07-44.485 » (mêmes méthodes qu'un résultat
    de RE_APPEAL)."""

    def __init__(self, m):
        self._m = m

    def start(self, _=0):
        return self._m.start(1)

    def end(self, _=0):
        return self._m.end(3)

    def span(self, _=0):
        return self.start(), self.end()

    def group(self, _=0):
        return "{}-{}.{}".format(*self._m.groups())
# Numéro de requête administrative : 5 à 7 chiffres précédés d'un marqueur n°.
RE_REQUEST = re.compile(r"n[°ºo]\s*(\d{5,7})\b", re.I)
RE_DATE_WORDS = re.compile(
    r"\b(\d{1,2})(?:er)?\s+(" + "|".join(map(re.escape, DATE_MONTHS)) + r")\s+(\d{4})\b",
    re.I)
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
MARK_JAF = re.compile(r"\bjuge\s+aux\s+affaires\s+familiales\b", re.I)
# Pour les décisions citées sans numéro : toute juridiction, suivie de près d'une date.
MARK_ANY = [("CE", MARK_ADMIN), ("Cass.", MARK_JUDICIAL),
            # « confirmée par arrêt de la Cour de ce siège en date du 27 mars 2015 »
            ("CA", re.compile(r"\bCA\b|\b[Cc]our\s+d['’]\s*appel\b|\b[Cc]our\s+de\s+ce\s+siège\b")),
            ("CNDA", re.compile(r"\bCNDA\b|\b[Cc]our\s+nationale\s+du\s+droit\s+d['’]\s*asile\b")),
            ("TJ", re.compile(r"\b(?:TJ|TGI)\b|\b[Tt]ribunal\s+(?:judiciaire|de\s+grande\s+"
                              r"instance)\b")),
            ("T. com.", RE_TCOM_COURT),
            # « conseil des prud'hommes », « Conseil de Prudhommes »
            ("CPH", re.compile(r"\bCPH\b|\b[Cc]onseil\s+des?\s+[Pp]rud['’]?\s*hommes\b")),
            ("T. corr.", re.compile(r"\b[Tt]ribunal\s+correctionnel\b")),
            # Le juge aux affaires familiales siège au tribunal judiciaire : « le jugement
            # rendu par le juge aux affaires familiales de [Localité 1] le 15 décembre 2023 ».
            ("TJ", MARK_JAF),
            # « Par jugement du 8 juillet 2021, le tribunal de Lisieux » : un tribunal nommé par
            # sa ville seule, ou un ancien tribunal (d'instance, de police).
            ("Tribunal", re.compile(r"\b[Tt]ribunal\s+(?:d['’]\s*instance|de\s+police"
                                    r"|de\s+proximité|de\s+(?!(?i:commerce|grande)\b)"
                                    r"(?=[A-ZÀ-Þ]))")),
            ] + MARK_OTHER
UNNUMBERED_GAP = 60   # entre la juridiction et la date : « CE, Ass., sect., »
# « la Cour de cassation applique la loi du 6 juillet 1989 » : la date est celle d'un texte.
RE_NOT_A_DECISION = re.compile(r"\b(?:loi|décret|ordonnance|arrêté|circulaire|directive|"
                               r"règlement|convention|accord|avenant|article|art\.)", re.I)
RE_EU = re.compile(r"\b([CT])\s?[-‑–]\s?(\d{1,4})/(\d{2})\b")
# La date d'un texte, juste avant elle : « la loi du 8 août 2016 », « décret n° 2016-1234 du
# 29 septembre 2016 ». Ce n'est pas la date de la décision voisine.
# (« ordonnance n° 58-1067 du 7 novembre 1958 » est un texte ; « ordonnance n° 2602422 du 5
# mai 2026 », sans tiret, la décision d'un juge : sa date est celle de la décision.)
RE_TEXT_DATE = re.compile(
    r"\b(?:(?:loi|décret|arrêté|circulaire|directive|règlement|avenant|accord)s?"
    r"(?:\s+organique)?(?:\s+n[°º]\s*[\d-]+)?"
    r"|ordonnances?(?:\s+n[°º]\s*\d{2,4}-[\d-]+)?)\s+(?:du|en\s+date\s+du)\s+$", re.I)
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
        day, month, year = m.group(1), DATE_MONTHS[m.group(2).lower()], m.group(3)
    else:
        day, month, year = m.group(1), int(m.group(2)), m.group(3)
    iso = f"{year}-{month:02d}-{int(day):02d}"
    try:
        date.fromisoformat(iso)
    except ValueError:
        return None
    return iso


# Une date d'événement, pas celle d'une décision : elle ne dispute pas sa date à l'arrêt cité
# dans la même phrase (« antérieures au 9 juin 2018, ce que rappelle la jurisprudence (Cass.
# soc., 30 juin 2021, n° 19-10.161) » : la date de l'arrêt n'était plus lue).
RE_EVENT_DATE = re.compile(r"\b(?:au|avant\s+le|après\s+le|depuis\s+le|compter\s+du"
                           r"|jusqu['’]au|dès\s+le|entre\s+le)\s+$", re.I)


RE_GLUED_DATE = re.compile(
    r"(?:/\d{1,2})?\s*,?\s*(?:du|en\s+date\s+du)\s+(\d{1,2})(?:er)?\s+("
    + "|".join(map(re.escape, DATE_MONTHS)) + r")\s+(\d{4})\b", re.I)
# Collée devant, à la manière des recueils : « rendu sur renvoi après cassation (Com., 4
# octobre 2023, pourvoi n° 22-18.358) », la date de l'arrêt attaqué plus haut dans la phrase
# ne lui dispute pas la sienne (vraies décisions du 02/10/2026).
RE_GLUED_BEFORE = re.compile(
    r"\b(\d{1,2})(?:er)?\s+(" + "|".join(map(re.escape, DATE_MONTHS)) + r")\s+(\d{4})"
    r"\s*,\s*(?:pourvoi\s+)?(?:n[°ºo]\s*)?$", re.I)
RE_NEGATED = re.compile(r"\b(?:non|pas|ni|ou|plutôt|sauf)\b", re.I)
# Entre un numéro et la date qui le suit, une autre décision : la date est la sienne. « a
# formé le pourvoi n° A 24-17.185 contre l'arrêt rendu le 14 mai 2024 par la cour d'appel de
# Pau » (le pourvoi était daté du jour de l'arrêt d'appel), « N° RG 25/00171 ... Décision
# déférée à la Cour : Jugement du Conseil de Prud'hommes de Basse-Terre - section commerce -
# du 12 Décembre 2024 » (vraies décisions, relues par Grok le 03/10/2026).
RE_AGAINST = re.compile(r"\bcontre\s+(?:l['’]\s*|le\s+|la\s+|un\s+|une\s+)"
                        r"(?:arrêt|jugement|ordonnance|décision)\b", re.I)
RE_DECISION_OF = re.compile(r"\b(?:arrêt|jugement|ordonnance|décision)\s+(?:rendue?\s+par\s+"
                            r"(?:le|la|l['’])|du|de\s+la|de\s+l['’])\s*", re.I)


def _other_decision(text, lo, hi):
    """Vrai si une autre décision est nommée dans text[lo:hi] : « contre l'arrêt », ou une
    décision suivie de sa juridiction (« Jugement du Conseil de Prud'hommes »)."""
    if RE_AGAINST.search(text, lo, hi):
        return True
    return any(rx.match(text, d.end(), hi) for d in RE_DECISION_OF.finditer(text, lo, hi)
               for _, rx in MARK_ANY)


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
        if RE_EVENT_DATE.search(text, max(0, m.start() - 30), m.start()):
            continue                        # « les demandes antérieures au 9 juin 2018 »
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
            if m.start() >= end and _other_decision(text, end, m.start()):
                continue                    # la date d'une autre décision, nommée entre eux
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
    # « n° 2602422 du 5 mai 2026, ... le titre émis le 29 janvier 2026 » : la date collée au
    # numéro par « du » est la sienne, sans dispute possible (décisions du 02/10/2026). La
    # dispute ne joue que si aucune date n'est collée (« arrêt du 1er janvier 1900 (et non du
    # 21 mars 2019), n° 17-28.268 »).
    for start, end in starts:
        glued = RE_GLUED_DATE.match(text, end)
        if not glued:
            glued = RE_GLUED_BEFORE.search(text, max(0, start - 50), start)
            # « arrêt du 1er janvier 1900 et non du 21 mars 2019, n° 17-28.268 » : écartée.
            if glued and RE_NEGATED.search(text, _sentence_start(text, start), glued.start()):
                glued = None
        day = glued and _iso(glued)
        if day:
            if start in best and best[start][1] != day and used is not None:
                used.add(best[start][2])
            best[start] = (0, day, glued.start(1), glued.end())
            disputed.discard(start)
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


RE_EU_ACT = re.compile(r"(?:\d/|\b(?:règlement|directive|décision|traité)s?\s*\(?)\s*$",
                       re.I)


RE_UNNUMBERED_GAP = re.compile(
    r"(?:[\s,.;:()–-]"
    r"|\b(?:du|de|des|d['’]|la|en\s+date\s+du|statuant\s+au\s+contentieux|et"
    r"|chambres?|ch\.|sect(?:ion|\.)|ass(?:emblée|\.)|plén(?:ière|\.)?|réunies|mixte"
    r"|civ(?:ile|\.)?|soc(?:iale|\.)?|com(?:merciale|\.)?|crim(?:inelle|\.)?"
    r"|correctionnelle|sociale|formation|départage|référés?|juge|avis"
    # les sections d'un conseil de prud'hommes : « de Basse-Terre - section commerce - du »
    r"|commerce|industrie|agriculture|activités\s+diverses|encadrement"
    r"|\d{1,2}(?:e|è|ème|ère|re|er)|1re|1ère|Gde|grande"
    # « Le Conseil d'État a jugé le 5 juin 2009 »
    r"|a\s+(?:jugé|statué|décidé|retenu|rappelé)(?:\s*,)?\s+le)(?![\w'’])"
    # un lieu pseudonymisé : « de [Localité 1] »
    r"|\[[^\]\n]{1,30}\]"
    # une ville : « CA Paris », « tribunal administratif de Toulon », « de BESANCON »
    r"|(?-i:[A-ZÀ-Þ][\w'’]*(?:-[\w'’]+)*))*", re.I)


# La juridiction écrite APRÈS la date, selon un seul modèle : une décision nommée, sa date,
# puis la juridiction qui l'a rendue. « contre l'arrêt rendu le 31 janvier 2025 par la cour
# d'appel de Lyon », « Par jugement du 12 décembre 2024, le conseil de prud'hommes de
# Basse-Terre », « l'arrêt rendu le 28 novembre 2024, entre les parties, par la cour d'appel
# de Lyon », « par un arrêt du 26 juin 2003, la cour administrative d'appel de Marseille »
# (vraies décisions du 02/10/2026). « Par jugement du 5 juillet 2019, la dissolution » ne
# nomme aucune juridiction : rien.
RE_DECISION_BEFORE = re.compile(
    r"\b(?:arrêt|jugement|ordonnance|décision)(?:\s+(?:attaquée?|contradictoire|déférée?"
    r"|de\s+non-conciliation|de\s+référé|rendue?))*\s+(?:le|du|en\s+date\s+du)\s+$", re.I)
RE_COURT_FOLLOWING = re.compile(
    r"\s*,?\s*(?:[-–]\s*)?(?:entre\s+les\s+parties\s*,\s*)?"
    r"(?:rendue?\s+en\s+formation\s+de\s+départage\s*,\s*)?"
    r"(?:par\s+(?:laquelle|lequel)\s+|par\s+)?(?:(?:le|la|l['’]|du|de\s+la|de\s+l['’])\s*)?"
    r"(?:(?:juge\s+des\s+référés|juge\s+aux\s+affaires\s+familiales"
    r"|(?:premier\s+)?(?:vice-)?présidente?|magistrate?\s+désignée?)"
    r"(?:\s+de\s+la\s+\d{1,2}(?:e|ème|è)\s+chambre)?\s+(?:du|de\s+la|de\s+l['’])\s*)?", re.I)
# « Selon l'arrêt attaqué (Lyon, 31 janvier 2025) » : un arrêt de cour d'appel, la ville
# devant la date, entre parenthèses.
RE_ATTACKED = re.compile(r"\barrêt\s+attaqué\s*\(\s*(?-i:[A-ZÀ-Þ])[\w'’-]*(?:\s+[\w'’-]+){0,3}"
                         r"\s*,\s*$", re.I)


RE_RENDERED_BY = re.compile(r"\b(?:arrêt|jugement|ordonnance|décision)\s+rendue?\s+par\s+"
                            r"(?:le|la|l['’])\s*$", re.I)


def _court_following(text, m):
    """(juridiction, début, fin) d'une décision citée par sa date puis sa juridiction (date
    `m`), selon les modèles ci-dessus ; sinon None."""
    before = RE_ATTACKED.search(text, max(0, m.start() - 60), m.start())
    if before and text[m.end():m.end() + 1] == ")":
        return "CA", before.start(), m.end() + 1
    before = RE_DECISION_BEFORE.search(text, max(0, m.start() - 80), m.start())
    if not before:
        return None
    link = RE_COURT_FOLLOWING.match(text, m.end())
    for court, rx in MARK_ANY:
        found = rx.match(text, link.end())
        if found:
            # Sa ville et sa formation entre parenthèses : « par la cour d'appel de Pau (2e
            # chambre, section 1) ».
            return court, before.start(), _city_end(text, found.end())
    return None


RE_FORMATION = re.compile(r"[^\S\f]*\([^()\f]{1,40}\)")   # pas sur deux pages


def _city_end(text, end):
    """La fin de la ville et de la formation écrites juste après la juridiction qui finit à
    `end` ; `end` s'il n'y en a pas."""
    city = RE_PLACEHOLDER.match(text, end) or _CITY.match(text, end)
    if not city or any(rx.search(text, end, city.end()) for _, rx in _COURT_NAMES):
        return end
    formation = RE_FORMATION.match(text, city.end())
    return formation.end() if formation else city.end()


def unnumbered(text, used):
    """Les décisions citées sans numéro : une date qu'aucun numéro n'a prise, précédée de
    près, dans la même phrase, par une juridiction. Renvoie [(juridiction, date, span)]."""
    found = [(m, _iso(m)) for m in RE_DATE_WORDS.finditer(text)]
    found += [(m, _iso(m, False)) for m in RE_DATE_DIGITS.finditer(text)]
    out = []
    for m, day in found:
        if not day:
            continue
        # (Une date disputée par un numéro voisin reste celle d'une décision ainsi désignée :
        # « Selon l'arrêt attaqué (Lyon, 28 novembre 2024), rendu sur renvoi après cassation
        # (Com., 4 octobre 2023, pourvoi n° 22-18.358) ». Prise par un numéro, elle est écartée
        # plus loin comme une reprise.)
        after = _court_following(text, m)
        if after:
            out.append((after[0], day, (after[1], after[2])))
            continue
        if m.start() in used:
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
        # Entre la juridiction et la date, seulement une ville, une formation ou des mots de
        # liaison : « Conseil d'État un courrier du 21 juillet 2026 », « cour administrative
        # d'appel de Paris, sur appel de M. L..., a annulé la décision du 11 juin 2019 » ne
        # citent aucune décision (décisions du 02/10/2026).
        if not RE_UNNUMBERED_GAP.fullmatch(text, end, m.start()):
            # « le jugement rendu par le conseil des prud'hommes de Basse-Terre le 12 décembre
            # 2024 » ; pas « Mme [G] a saisi le Conseil de prud'hommes de Besançon le 31 mars
            # 2014 », une saisine (vraies décisions du 02/10/2026).
            on = re.search(r"\s+le\s+$", text[end:m.start()])
            if not (on and RE_UNNUMBERED_GAP.fullmatch(text, end, end + on.start())
                    and RE_RENDERED_BY.search(text, max(0, start - 40), start)):
                continue
        # « directive 2008/115/CE du 16 décembre 2008 », « règlement (CE) n° 44/2001 » : le
        # « CE » de la Communauté européenne, pas le Conseil d'État (audit visuel du
        # 02/10/2026).
        if RE_EU_ACT.search(text, max(0, start - 30), start):
            continue
        # « Le Conseil d'État a jugé le 5 juin 2009 que ce 12 mars 2019... » : la juridiction
        # appartient à la première date, pas à celle qui suit.
        if RE_DATE_WORDS.search(text, end, m.start()) or RE_DATE_DIGITS.search(text, end, m.start()):
            continue
        out.append((court, day, (start, m.end())))
    return out


# La juridiction écrite APRÈS le numéro, selon un seul modèle, celui des visas des décisions
# administratives : « Par une ordonnance n° 2602422 du 5 mai 2026, le juge des référés du
# tribunal administratif de Nice », « l'ordonnance n° 2508419 du 6 mai 2026 par laquelle la
# présidente du tribunal administratif de Melun », « un jugement n° 1908677/4 du 25 novembre
# 2022, le tribunal administratif de Montreuil » (décisions du 02/10/2026). Elle l'emporte sur
# une juridiction nommée avant, qui est celle d'une autre procédure (« sa requête devant la
# cour administrative d'appel de Paris tendant à l'annulation de l'ordonnance n° 2508419 ...
# par laquelle la présidente du tribunal administratif de Melun »).
_DAY = r"(?:1er|\d{1,2})\s+(?:" + "|".join(map(re.escape, DATE_MONTHS)) + r")\s+\d{4}"
RE_COURT_AFTER = re.compile(
    r"(?:/\d{1,2})?(?:\s+du\s+" + _DAY + r")?"
    r"(?:\s*,\s*enregistrée?\s+(?:le\s+même\s+jour|le\s+" + _DAY + r")\s+au\s+"
    r"(?:secrétariat\s+du\s+contentieux\s+du\s+Conseil\s+d['’]\s*[ÉE]tat"
    r"|greffe\s+de\s+(?:la\s+cour|ce\s+tribunal)))?"
    r"\s*,?\s*(?:par\s+(?:laquelle|lequel)\s+|rendue?\s+le\s+" + _DAY + r"\s+par\s+)?"
    r"(?:(?:le|la|l['’])\s*)?"
    r"(?:(?:juge\s+des\s+référés|(?:premier\s+)?(?:vice-)?présidente?|magistrate?\s+désignée?)"
    r"(?:\s+de\s+la\s+\d{1,2}(?:e|ème|è)\s+chambre)?\s+(?:du|de\s+la|de\s+l['’])\s*)?"
    r"(?P<court>tribunal\s+administratif|cour\s+administrative\s+d['’]\s*appel"
    r"|Conseil\s+d['’]\s*[ÉE]tat|ce\s+tribunal)\b", re.I)
# « M. B... a demandé au tribunal administratif de Nice ... Par un jugement n° 2200015 du 18
# juillet 2024, ce tribunal a rejeté sa demande » : « ce tribunal » est le dernier nommé, s'il
# l'est tout près (vraies décisions du 02/10/2026).
RE_LAST_TRIBUNAL = re.compile(r"\btribunal\s+(administratif|judiciaire|de\s+commerce"
                              r"|correctionnel|de\s+grande\s+instance)\b", re.I)
THIS_TRIBUNAL_BACK = 600


def court_after(text, end):
    """« TA », « CAA » ou « administrative » (le Conseil d'État) si le modèle ci-dessus suit
    le numéro qui finit à `end` ; sinon None."""
    m = RE_COURT_AFTER.match(text, end)
    if not m:
        return None
    court = m.group("court").lower()
    if court.startswith("ce "):
        named = list(RE_LAST_TRIBUNAL.finditer(text, max(0, end - THIS_TRIBUNAL_BACK), end))
        return "TA" if named and named[-1].group(1).lower() == "administratif" else None
    return "TA" if court.startswith("tribunal") else "CAA" if court.startswith("cour") \
        else "administrative"


RE_JOINED = re.compile(r"\s*(?:,|et)\s+(\d{3,6}/\d{2,4})\b")


def _joined(text, end):
    """Les requêtes jointes écrites à la suite de celle qui finit à `end`."""
    out = []
    m = RE_JOINED.match(text, end)
    while m:
        out.append(m)
        m = RE_JOINED.match(text, m.end())
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


def extract(text, unverified=False, whole_texts=False):
    """Renvoie (citations, remarques). Une remarque signale ce qui n'a pas pu être lu.
    `unverified` : ajoute ce qui est relevé sans pouvoir être vérifié (« unverified »), pour
    le rapport et le PDF annoté. `whole_texts` : ajoute les lois, ordonnances et décrets
    cités en entier (« text »), dont on vérifiera qu'ils existent."""
    try:
        return _extract(text, unverified, whole_texts)
    finally:
        _ENDS[:] = [None, []]   # ne pas garder la pièce en mémoire, même après une erreur


def _extract(text, with_unverified=False, whole_texts=False):
    citations, undated, set_aside = [], [], []
    appeals = sorted(list(RE_APPEAL.finditer(text))
                     + [_Spaced(m) for m in RE_APPEAL_SPACED.finditer(text)],
                     key=lambda m: m.start())
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
        order = court_after(text, m.end()) or order_of(text, m.start(), None)
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
            # « n° 28859/11 et 28473/12 » : une affaire jointe, sans « n° » devant la seconde
            # requête (vraies décisions du 02/10/2026).
            more = [(x.group(1), x.span(1)) for x in _joined(text, span[1])] if slash else []
            for number, span in [(number, span)] + more:
                if seen.again(("other", number, d), span):
                    continue
                citations.append({"kind": "decision",
                                  "order": "ta" if order == "TA" else "other",
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
    lower, lower_remarks, lower_unverified = extract_lower_courts(text, rgs, dates)
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
    late_repeats = []
    for court, day, span in unnumbered(text, used):
        # Déjà citée avec son numéro à cette date : c'est la même décision, reprise. Elle n'est
        # marquée comme reprise que si la cour et sa ville sont celles du numéro : « un arrêt
        # n° RG 23/07760 rendu le 28 novembre 2024 par la cour d'appel de Lyon », puis
        # « l'arrêt attaqué (Lyon, 28 novembre 2024) » (vraies décisions, relues par Grok le
        # 03/10/2026). Sinon, comme avant, rien.
        if day in numbered_days:
            words = text[span[0]:span[1]].lower()
            same = [c for c in lower if c["cited_date"] == day and c.get("place")
                    and LOWER_COURTS.get(c.get("jurisdiction")) == court
                    and c["place"].lower() in words]
            if len(same) == 1:
                late_repeats.append((same[0], span))
            continue
        if not seen.again(("unnumbered", court, day), span):
            citations.append({"kind": "decision", "order": "unnumbered", "court": court,
                              "number": None, "cited_date": day, "span": span})
            seen[("unnumbered", court, day)] = citations[-1]

    articles, article_remarks, unverified, text_used, named_used = extract_articles(text)
    if with_unverified:
        articles += unverified + lower_unverified
    if whole_texts:
        articles += extract_texts(text, text_used)
        if with_unverified:
            articles += extract_other_texts(text, named_used)
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
    # (Après les blocs : une reprise sans numéro est déjà entière. Jamais sur une autre citation.)
    taken = [tuple(s) for c in both for s in [c["span"]] + c.get("repeats", [])]
    for c, (a, b) in late_repeats:
        if not any(x < b and a < y for x, y in taken):
            c.setdefault("repeats", []).append((a, b))
            taken.append((a, b))
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
# (Le juge aux affaires familiales n'ouvre pas un bloc : « TRIBUNAL JUDICIAIRE DE LYON - JUGE
# AUX AFFAIRES FAMILIALES Jugement de divorce du 18 février 2025, RG n° 23/04512 » garde la
# date et le numéro.)
_COURT_NAMES = ([(name, rx) for name, rx in MARK_ANY if name != EU and rx is not MARK_JAF]
                + _EU_NAMES
                + [("Cass.", rx) for rx, _ in CHAMBERS])
# Les mots de liaison permis entre deux morceaux retenus d'une décision.
_LINK = re.compile(
    r"(?:[\s,.:;()]|\b(?:du|de|des|la|le|les|l['’]|en\s+date\s+du|pourvoi|arr[êe]t|décision|"
    r"rendue?|requête|req\.|RG|R\.G\.|avis|section|sect\.|G(?:de|rande)\s+ch(?:ambre|\.)?"
    r"|numéro)"
    r"(?![\w'’])|\bn[°º]\.?|\bno\b)*", re.I)
# Une ville après une cour d'appel, un tribunal, une CAA : « CA Paris », « CAA de Nancy »,
# « CA Aix-en-Provence », « TJ Le Mans ». Un seul lieu : un mot, ou des mots liés par des
# traits d'union. « CA Paris Dupont » ou « CAA de Paris Le Conseil » : le mot de trop n'est
# pas un mot de liaison, le bloc revient au numéro (audit du 01/10/2026).
_CITY = re.compile(r"\s*(?:de\s+|d['’]\s*|du\s+|des\s+)?(?:(?:Le|La|Les)\s+|L['’]\s*)?"
                   r"[A-ZÀ-Þ][^\W\d_'’-]*(?:['’-][^\W\d_]+)*(?:\s+de\s+La\s+Réunion)?")


# Un lieu pseudonymisé à la place de la ville : « juge aux affaires familiales de [Localité 1] ».
RE_PLACEHOLDER = re.compile(r"\s*(?:de\s+|d['’]\s*)?\[[^\]\n]{1,30}\]", re.I)


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


AFTER_ORDERS = {"ta": "TA", "caa": "CAA", "administrative": "administrative"}
LOWER_COURTS = {"ca": "CA", "tj": "TJ"}
# La cour écrite après le RG et sa date : « un arrêt n° RG 23/07760 rendu le 28 novembre 2024
# par la cour d'appel de Lyon (3e chambre A) ».
RE_BY_COURT = re.compile(r"\s*,?\s*par\s+(?:la|le|l['’])\s*", re.I)
# Les parties, entre la date et le numéro d'un arrêt de la CEDH : « CEDH, arrêt du 15 mars
# 2012, Solomakhin c. Ukraine, n° 24429/03 ».
# (« Dubská et Krejzová », sans « c. » : des noms propres seulement.)
RE_PARTIES = re.compile(r"\s*,\s*(?-i:[A-ZÀ-Þ][\w'’.-]*)(?:\s+(?:e\.a\.|et\s+autres"
                        r"|(?:et\s+)?(?-i:[A-ZÀ-Þ][\w'’.-]*)))*(?:\s+c\.\s+(?-i:[A-ZÀ-Þ][\w'’-]*)"
                        r"(?:\s+[\w'’-]+){0,3})?\s*,\s*")


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
        if c.get("order") in ("lower", "caa", "ta"):
            m = _CITY.match(text, court[1])
            # Une ville, pas une juridiction déguisée en ville (« CAA de Nancy CE »).
            if (m and m.end() > court[1]
                    and m.end() <= min(p[0] for p in pieces if p[0] >= court[1])
                    and not any(rx.search(text, court[1], m.end()) for _, rx in _COURT_NAMES)):
                city = (court[1], m.end())
                pieces.append(city)
    # La juridiction écrite après le numéro, selon le modèle de court_after : « n° 2602422 du
    # 5 mai 2026, le juge des référés du tribunal administratif de Nice ».
    after = RE_COURT_AFTER.match(text, end)
    if after and court_after(text, end) == AFTER_ORDERS.get(c.get("order")):
        pieces.append((end, _city_end(text, after.end())))
    elif c.get("order") == "lower" and not court:
        tail = max(b for _, b in pieces)
        by = RE_BY_COURT.match(text, tail)
        named = by and [m for name, rx in _COURT_NAMES if name in _accepted(c)
                        for m in [rx.match(text, by.end())] if m]
        if named:
            pieces.append((tail, _city_end(text, named[0].end())))
    # Les morceaux qui se chevauchent (« Cass. soc. » et la chambre « soc. ») n'en font qu'un.
    merged = []
    for a, b in sorted(pieces):
        if merged and a <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], b))
        else:
            merged.append((a, b))
    for (_, b), (a, _) in zip(merged, merged[1:]):
        if not (_LINK.fullmatch(text, b, a)
                or c.get("order") == "other" and RE_PARTIES.fullmatch(text, b, a)):
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
# « L 3251- 2 », « R 4624 -31 » : le tiret d'un article de code coupé par une espace, au
# passage à la ligne du PDF (vraies décisions du 02/10/2026 : l'article L. 761 était lu). Avec
# la lettre seulement : « article 3 - Durée » est un titre d'article.
NUM = (rf"(?:[LRDA]\.?\s?\*?\s?(?:\d+(?:[-‑.]\d+|\s?[-‑]\s?\d+)*)"
       rf"|(?:1er|\d+(?:[-‑.]\d+)*)){SUFFIX}*\b")
# « articles 620, alinéa 1, et 1015 du code de procédure civile » : un alinéa dans la liste
# (vraies décisions du 02/10/2026). Son numéro n'est pas un article (_LIST_PARA, retiré).
# « articles 12, I, 2°, et 14, I, B, de la loi n° 2021-1040 » : un paragraphe en chiffres
# romains, suivi de ses subdivisions (vraies décisions, relues par Grok le 03/10/2026).
_SUBDIV = r"(?-i:[IVX]{1,4})(?:\s*,\s*(?:\d{1,2}°|(?-i:[A-Z])(?![\w'’])))*(?![\w'’])"
_LIST_PARA = (r"\s*,\s*(?:(?:alinéas\s*\d{1,2}(?:\s*(?:,|et)\s*\d{1,2})+"
              r"|(?:alinéa|al\.?|§)\s*(?:\d{1,2}|1er|premier))\b|" + _SUBDIV + ")")
# « l'article préliminaire du code de procédure pénale » : un article sans numéro, relevé,
# jamais envoyé (PRELIMINARY).
ITEM = rf"(?:{NUM}|préliminaire\b)"
# « à l'article "L 3141-3 ouvre droit » : un guillemet ouvrant devant le numéro.
RE_ARTICLES = re.compile(
    r"\bart(?:icle)?s?\.?\s+\"?(" + ITEM + r"(?:(?:" + _LIST_PARA + r"\s*,?)?\s*(?:,|et|à|ou)\s*"
    + ITEM + r")*)", re.I)
RE_ONE_NUM = re.compile(ITEM, re.I)
RE_LIST_PARA = re.compile(_LIST_PARA, re.I)


def _list_numbers(group):
    """Les numéros d'une liste d'articles, sans ceux de ses alinéas."""
    paras = [p.span() for p in RE_LIST_PARA.finditer(group)]
    return [x for x in RE_ONE_NUM.finditer(group)
            if not any(a <= x.start() < b for a, b in paras)]
# « du même code », « dudit code », « de ce code », « du code précité ». « du code » tout
# court seulement s'il finit le visa : « L'article 6 du code de déontologie des avocats »
# n'est pas un article du code cité avant (audit du 02/10/2026).
RE_SAME_CODE = re.compile(r"^\W{0,3}(?:du\s+code\s+(?:précité|susvisé)\b"
                          r"|(?:du\s+même|dudit|de\s+ce(?:\s+même)?)\s+code\b"
                          r"|du\s+code(?=\s*(?:[,.;:)]|$)))", re.I)
RE_QUOTE = re.compile(r"«\s*([^»]{20,})\s*»|“([^”]{20,})”|\"([^\"]{20,})\"")
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
CODE_NAME = 100     # et se lit en entier (« Code de la Légion d'honneur, de la Médaille... »)
CODE_BEFORE = 25    # ou le précéder de très près (« C. trav., art. L. 1152-1 »)
QUOTE_AFTER = 200
QUOTE_BEFORE = 15   # « ... » (art. L. 1234-5) : le texte précède, collé


# « Costello-Roberts c. Royaume-Uni », « T. com. Paris », « Cass. Soc. » : le point d'une
# abréviation n'est pas une fin de phrase. Sans ces exceptions, la date citée avant les noms
# des parties n'atteignait jamais le numéro cité après, et « T. com. Paris, 9 janvier 2026 »
# perdait sa juridiction.
ABBREVIATIONS_WITH_DOT = ["c", "com", "soc", "civ", "crim", "cass", "confl", "const", "cons",
                          "trib", "ass", "sect", "ch", "req", "art", "t", "m", "plén",
                          "s", "ss", "suiv", "v", "adde", "comp", "cf"]
# « ... du 20 novembre 1989. 2°/ que ... », « ... remplies. 2° Sous le n° ... » : la branche
# suivante d'un moyen commence une phrase, comme chaque tiret d'une liste (« ... ; - elle
# méconnaît l'article ... »). « Vu l'article 700 du code de procédure civile, Vu le décret ... » : chaque « Vu »
# est un visa à part (vraies décisions du 02/10/2026).
RE_SENTENCE_END = re.compile(
    "(?:" + "".join(rf"(?<!\b(?i:{a}))" for a in ABBREVIATIONS_WITH_DOT)
    + r"[.;!?]\s+(?=[A-ZÀ-ÖØ-Þ«]|\d{1,2}°)|;\s+(?=[-–]\s)|,\s+(?=Vu\s))")


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
    n = re.sub(r"\s*-\s*", "-", n)                           # « L3251- 2 » -> « L3251-2 »
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
             r"(?:\s*(?:n[°ºo]|numéro)\s*(?P<num>\d{2,4}-\d{1,5})|\s+(?P<num2>\d{2,4}-\d{1,5}))?"
             r"(?:\s*,?\s+du\s+(?P<day>1er|\d{1,2})\s+(?P<month>" + "|".join(MONTHS) +
             r")\s+(?P<year>\d{4}))?")
# (« 37, alinéa 2, de la loi n° 91-647 du 10 juillet 1991 » : un alinéa entre les deux.)
# (« 14, I, B, de la loi n° 2021-1040 » : un paragraphe et ses subdivisions.)
RE_TEXT_AFTER = re.compile(r"^\W{0,3}(?:(?:alinéa|al\.?)\s*(?:\d{1,2}|1er|premier)\s*,?\s*"
                           r"|" + _SUBDIV + r"\s*,\s*)?"
                           r"(?:de\s+la\s+|du\s+|de\s+l['’]\s*)?" + _TEXT_REF, re.I)
# « loi n° 89-462 du 6 juillet 1989 modifiée, article 22 », « ..., dite loi Mermaz, article
# 22 » : la loi reste celle de l'article (audit du 02/10/2026).
RE_TEXT_BEFORE = re.compile(r"(?:^|\W)" + _TEXT_REF
                            + r"(?:\s*,?\s*(?:modifi[ée]e?s?|dite?\s+[^,;:.\d]{1,40}))?"
                            r"[\s,;:]*$", re.I)
RE_SAME_TEXT = re.compile(r"^\W{0,3}(?:de\s+la\s+(?:même\s+)?|de\s+ladite\s+|de\s+cette\s+(?:même\s+)?|du\s+"
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


# La Constitution et la Déclaration de 1789 : des textes sans numéro, aux identifiants
# Légifrance fixes (sonde probes/constitution.py, 02/10/2026). « article 61-1 de la
# Constitution », « article 16 de la Déclaration de 1789 », « article 6 de la Déclaration des
# droits de l'homme et du citoyen ». Pas la Constitution de 1946 ou de 1848, ni la
# Déclaration universelle des droits de l'homme : non vérifiées, gris.
BLOCK = {
    "constitution": {"text_nature": "CONSTITUTION", "text_number": None,
                     "text_date": "1958-10-04", "text_id": "LEGITEXT000006071194"},
    "ddhc": {"text_nature": "DDHC", "text_number": None, "text_date": "1789-08-26",
             "text_id": "LEGITEXT000006071192"},
}
BLOCK_TITLES = {"CONSTITUTION": "Constitution du 4 octobre 1958",
                "DDHC": "Déclaration des droits de l'homme et du citoyen de 1789"}
RE_BLOCK_AFTER = re.compile(
    r"^\s*(?:,\s*(?:alinéa|al\.?)\s*(?:\d{1,2}|1er|premier)\s*,?\s*)?(?:de\s+la\s+|de\s+l['’]\s*)"
    r"(?:(?P<constitution>Constitution(?:\s+(?:du\s+4\s+octobre\s+|de\s+)1958)?)"
    r"(?!\s+(?:du\s+\d|de\s+1[78]\d\d|de\s+19[0-4]\d))"
    r"|(?P<ddhc>Déclaration\s+(?:de\s+1789|du\s+26\s+août\s+1789|des\s+droits\s+de\s+"
    r"l['’]\s*[Hh]omme\s+et\s+du\s+[Cc]itoyen(?:\s+(?:de\s+|du\s+26\s+août\s+)1789)?)"
    r"|DDHC))\b")


def _text_label(ref):
    """« Loi n° 89-462 du 6 juillet 1989 », pour le rapport."""
    if ref["text_nature"] in BLOCK_TITLES:
        return BLOCK_TITLES[ref["text_nature"]]
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


# Entre « convention collective » et son IDCC : rien, ou « nationale », et une parenthèse
# (« convention collective nationale (IDCC 1979 »). Pas de nom : un programme ne distingue
# pas « des hôtels, cafés, restaurants » de « des salariés contestent le licenciement », et
# peindre une phrase sous la couleur de l'article serait mentir. L'IDCC reste dans le rapport
# (audits du 01/10/2026).
_CONVENTION_NAME = re.compile(r"(?:\s+nationale)?\s*,?\s*\(?\s*", re.I)


def _convention_name(text, lo, hi):
    return bool(_CONVENTION_NAME.fullmatch(text, lo, hi))


# Le rattachement d'un article à son texte : une LISTE BLANCHE (audit du 02/10/2026).
# Jusqu'ici, le programme prenait le code le plus proche, puis on interdisait les cas qui
# tournaient mal ; chaque audit trouvait une tournure oubliée (« et non le Code pénal »,
# « ou de la loi », « (Code du travail) »). Désormais, un article n'est vérifié que si son
# texte est écrit selon un modèle autorisé, qu'il n'en a qu'un, et que la suite de la
# phrase n'en nomme aucun autre. Sinon il n'est pas vérifié : un verdict bleu doit être sûr.
#   Devant : « C. civ., art. 1240 », « loi n° 89-462 du 6 juillet 1989, article 22 ».
#   Derrière : « article 1240 du Code civil », « article 1240, alinéa 2, du Code civil »,
#   « art. 1240 C. civ. », « art. 1240 (C. civ.) », « article 22 de la loi n° 89-462 du 6
#   juillet 1989 », « article 1241 du même code », « article 23 de la même loi ».
_PREP = r"(?:du|des|de\s+la|de\s+l['’]|de|aux|au|dudit|du\s+même|de\s+ce(?:\s+même)?)"
# « alinéa 2 », « al. 1er », « al 2 », « § 1 », « , II, » (« article L. 442-1, II, du code de commerce »).
_PARA = (r"(?:(?:alinéa|al\.?)\s*(?:\d{1,2}|1er|premier)|§\s*\d{1,2}"
         r"|" + _SUBDIV + r"(?=\s*,))")
# « articles L. 145-1 et suivants du code de commerce », « art. 1240 et s. C. civ. ».
_FOLLOWING = r"(?:\s*et\s+(?:suivants|suiv\.|s\.)|\s+ss\.)?"
# Entre l'article et le code qui le suit : « du », un alinéa, une parenthèse fermée juste
# après le code (vérifié à part), ou un simple espace. Un saut de page compte comme un espace :
# dans un PDF, il coupe souvent un visa.
_CODE_LINK = re.compile(
    rf"{_FOLLOWING}\s*(?:,\s*{_PARA}\s*,?\s*|{_PARA}\s*,?\s*)?{_PREP}\s*"
    rf"|{_FOLLOWING}\s*\(\s*(?:{_PREP}\s*)?"
    rf"|{_FOLLOWING}\s+", re.I)
_BARE = re.compile(rf"{_FOLLOWING}\s*", re.I)
# Entre l'article et la loi qui le suit.
_TEXT_LINK = re.compile(rf"\s*(?:,\s*{_PARA}\s*,?\s*)?(?:de\s+la|du|de\s+l['’])\s*", re.I)
# Entre le code ou la loi écrit devant et l'article.
_BEFORE_LINK = re.compile(r"\s*[,;:]?\s*")
# Un autre texte nommé dans la suite de la phrase : l'article n'est plus sûr (« article 22
# du Code civil ou de la loi du 6 juillet 1989 », « article 1240, et non le Code pénal »).
# (« du même code », « dudit code » ne nomment rien de nouveau ; « dite loi Pinel » est le
# nom de la même loi ; « modifiée par la loi ... » n'est pas un autre texte pour l'article.)
# (« de cette loi », « dans sa rédaction issue de la loi ... » : la même loi, ou celle qui a
# modifié l'article, pas un autre texte pour lui.)
_SAME_OR_AMENDING = (["dite ", "dit ", "par la ", "par le ", "par l'", "par l’", "cette ",
                      "même ", "ladite ", "présente "]
                     + [f"{w} {p}" for w in ("issue", "issu", "résultant")
                        for p in ("de la ", "de l'", "de l’", "du ")]
                     # « dans sa rédaction antérieure à l'ordonnance du 24 février 2016 »
                     + ["antérieure à la ", "antérieure à l'", "antérieure à l’",
                        "antérieure au "])
# (« délibéré conformément à la loi », dans l'en-tête de chaque arrêt de la Cour de
# cassation, « la loi pénale », « déterminés par un décret en Conseil d'État », « le champ
# d'application de la loi », « ordonnance du 7 novembre 1958 portant loi organique » (son
# titre) : aucun autre texte désigné, vraies décisions du 02/10/2026.)
_NO_TEXT_BEFORE = ["conformément à la ", "champ d'application de la ",
                   "champ d’application de la ", "portant "]


def _behind(words):
    """Les regards en arrière qui écartent ces mots, chaque espace pouvant être un saut de
    ligne : dans un PDF, « dans sa rédaction issue du » finit souvent une ligne."""
    out = []
    for w in words:
        variants = [""]
        for ch in w:
            variants = [v + c for v in variants for c in ((" ", "\n") if ch == " " else (ch,))]
        out += [f"(?<!{re.escape(v)})" for v in variants]
    return "".join(out)


# Une ordonnance ou un règlement n'est un texte que désigné : « ordonnance n° 58-1067 »,
# « ordonnance du 7 novembre 1958 », « règlement (UE) 2016/679 ». « Par une ordonnance
# motivée » (celle du juge), « la charge du règlement », « un règlement au fond de
# l'affaire » ne nomment aucun texte (décisions administratives du 02/10/2026).
_DESIGNATED = (r"(?=\s*(?:\(|n[°ºo]|numéro|\d|du\s+(?:\d|1er|premier)|de\s+\d{4}|portant"
               r"|relati|organique|(?-i:UE|CE|CEE)\b|européen|du\s+Parlement|du\s+Conseil"
               r"|de\s+la\s+Commission|délégué|d['’]exécution|intérieur|sanitaire"
               r"|de\s+copropriété|national|général|départemental|communal|municipal|local"
               r"|d['’]urbanisme|de\s+voirie|type))")
_ANY_TEXT = re.compile(_behind(["même ", "dudit "]) + r"(?<!\bce )(?<!\bce\n)\bcodes?\b"
                       r"|" + _behind(_SAME_OR_AMENDING + _NO_TEXT_BEFORE)
                       + r"\b(?:lois?|décrets?)\b(?!\s+pénale\b)"
                       r"(?!\s+en\s+Conseil\s+d['’]\s*[ÉE]tat\b(?!\s*n[°ºo]|\s+du\s+\d))"
                       r"|" + _behind(_SAME_OR_AMENDING) + r"\b(?:ordonnances?|règlements?)\b"
                       + _DESIGNATED +
                       r"|\b(?:conventions?|CCNT?|IDCC|directives?|traités?|constitution"
                       r"|chartes?|pactes?|protocoles?)\b|\b(?:conv|ann)\."
                       # « annexe III », « l'annexe au décret » ; pas « les aménagements
                       # annexes implantés sur la propriété »
                       r"|\bannexes?\b(?=\s*(?:[IVX]+\b|\d|n[°ºo]|au\b|aux\b|à\s|du\b|des\b"
                       r"|de\s+la\b|de\s+l['’]|,|\)))"
                       r"|\b(?:arrêté)s?\s+(?:\(|n[°ºo]|du\b|UE\b|CE\b)"
                       r"|\b(?-i:CESDH|EDH|RGPD|TFUE|TUE|PIDCP|DDHC)\b"
                       # la Convention, pas la Cour : « (CEDH, 25 mars 1993, n° ...) »
                       r"|\b(?-i:CEDH)\b(?!\s*,\s*(?:\d|Gde|Grande|plén|sect))", re.I)
# Un autre article juste après : « ..., C. trav., art. L. 1152-1 », « ... et l'article 5 ».
_NEXT_ARTICLE = re.compile(r"[\s,;:]*(?:(?:et|ou)\b\s*)?(?:l['’]\s*)?\bart(?:icle)?s?\b", re.I)
# « article 22 de la loi du 6 juillet 1989 ou du 24 mars 2014 », « article 8 du Code civil ou
# la Convention » : une autre lecture. « ou » suffit toujours ; « et », devant un sigle ou
# un « du » (audit du 02/10/2026).
# « et aux articles 338-1 et suivants du code de procédure civile », « ou à l'article 1241 » :
# l'article suivant, qui a son propre code, pas une autre lecture de celui-ci.
_ALTERNATIVE = re.compile(r"\s*,?\s*(?:ou\b|(?:et|ni)\s+(?:du|de|des|d['’]|au|aux)\b"
                          r"|et\s+(?:l[ae]s?\s+|l['’]\s*)?(?-i:[A-Z]{2,})\b)"
                          r"(?!\s*(?:à\s+|aux\s+|de\s+)?(?:l['’]\s*)?art(?:icle)?s?\b)"
                          # « au titre de l'article 700 ... et aux entiers dépens »
                          r"(?!\s*(?:entiers\s+)?dépens\b)", re.I)
# Un « du » laissé en suspens juste avant le code écrit devant l'article suivant.
_DANGLING = re.compile(r"\b(?:du|des|de\s+la|de\s+l['’]|de|au|aux)\s*$", re.I)
# « de la convention collective » : rattachée à l'article, sans virgule.
_CONVENTION_LINK = re.compile(r"\s*(?:de\s+ladite|de\s+la(?:\s+même)?|du|de\s+l['’])\s*"
                              r"(?:convention|CCN)", re.I)
# Entre la convention et son IDCC : un mot qui écarte ou propose un autre IDCC.
_NOT_THIS = re.compile(r"\b(?:non|pas|ni|ou|sauf|hors|excepté|exclu\w*|autres?|plutôt)\b",
                       re.I)


def _texts_in(text):
    """Les lois, décrets, ordonnances identifiables nommés dans `text`."""
    out = []
    for m in re.finditer(r"(?:^|\W)" + _TEXT_REF, text, re.I):
        ref = _text_ref(m)
        if ref:
            out.append((ref["text_nature"], ref["text_number"], ref["text_date"]))
    return out


def _has_code(text, lo, hi):
    """True si text[lo:hi] nomme un code. (Sans lettre majuscule ni « code », inutile de lancer
    la grande expression des codes : la plupart des bouts testés sont « , » ou « . ».)"""
    if lo >= hi or not _MAYBE_CODE.search(text, lo, hi):
        return False
    return bool(find_code(text[lo:hi]))


_MAYBE_CODE = re.compile(r"[A-Z]|(?i:code|livre|\bc\s?\.)")


def _code_follows(text, end):
    """True si un code ou une loi suit de près la fin d'un article, selon un modèle autorisé
    (« art. 1241 dudit code », « article 31 du décret n° 2016-334 »)."""
    after = text[end:end + CODE_NAME]
    named = RE_TEXT_AFTER.match(after)
    if RE_SAME_CODE.search(after) or (named and _text_ref(named) and _TEXT_LINK.fullmatch(
            after, 0, named.start("nature"))):
        return True
    found = find_code(after)
    return bool(found and found[1] <= CODE_AFTER and _CODE_LINK.fullmatch(after, 0, found[1])
                and not RE_SENTENCE_END.search(after, 0, found[1]))


def _same_zone(text, start):
    """(fenêtre, trois phrases) pour « du même code », « de la même loi » : SAME_BACK
    caractères en arrière, et le début de la phrase d'il y a deux phrases, sans remonter plus
    loin que la fenêtre. « Le Code pénal s'applique. » des pages plus haut ne dit pas
    sûrement lequel (audit du 02/10/2026)."""
    floor = max(0, start - SAME_BACK)
    ends = [x.end() for x in RE_SENTENCE_END.finditer(text, floor, start)]
    return floor, (ends[-3] if len(ends) >= 3 else floor)


SAME_BACK = 1000


def _written_before(text, start):
    """Ce qui est écrit juste devant l'article qui commence à `start` : (code, début) pour un
    code collé, (ref, début) pour une loi, un décret, une ordonnance collé ; sinon None."""
    before = text[max(0, start - CODE_BEFORE): start]
    found = find_code(before, last=True)
    if found:
        if _BEFORE_LINK.fullmatch(before, found[2]):
            return "code", found[0], start - len(before) + found[1]
        return None
    m = RE_TEXT_BEFORE.search(text, max(0, start - TEXT_BEFORE), start)
    ref = _text_ref(m)
    if ref:
        return "text", ref, _word_start(text, m.start(), start)
    return None


def _fit(text, reach, core, count):
    """Le bloc d'un article (article et code, loi ou convention), s'il n'y a qu'un numéro et
    que le bloc tient sur une page ; sinon le numéro seul."""
    if count == 1 and PAGE not in text[reach[0]:reach[1]]:
        return reach
    return core


class _Number:
    """Un numéro qui continue une liste d'articles, lu comme un article (mêmes méthodes
    qu'un résultat de RE_ARTICLES)."""

    def __init__(self, m, loose=False):
        self._m = m
        self.loose = loose      # derrière un texte qui n'est ni un code ni une loi

    def start(self, group=0):
        return self._m.start(1)

    def end(self, group=0):
        return self._m.end(1)

    def span(self, group=0):
        return self._m.span(1)

    def group(self, group=0):
        return self._m.group(1)


# « articles L. 761-1 du code de justice administrative et 37 de la loi du 10 juillet 1991 » :
# le second numéro, sans « article » devant, a son propre texte derrière lui (audit visuel du
# 02/10/2026). Seulement après « articles » au pluriel et un code ou une loi rattaché.
# « articles 111-4, 111-5 et 432-14 du code pénal, 591 et 593 du code de procédure pénale » :
# une liste entière, et autant de listes que la phrase en enchaîne (vraies décisions du
# 02/10/2026).
RE_CONTINUED = re.compile(r"\s*(?:,\s*et|,|et)\s+(" + ITEM + r"(?:\s*(?:,|et|à)\s*" + ITEM
                          + r")*)(?=\s*(?:,\s*" + _PARA + r"\s*,\s*)?\s+(?:de\s+la|du|de\s+l['’]|des)\s)",
                          re.I)
# Derrière un autre texte (une convention, une directive, la Déclaration...) : « articles 6 de
# la convention européenne des droits de l'homme, préliminaire, 495-14, 591 et 593 du code de
# procédure pénale », « articles 8 de la Convention ... et 3 de la convention relative aux
# droits de l'enfant » (vraies décisions du 02/10/2026). La suite n'est lue que si un texte la
# suit aussitôt ; elle est ensuite rattachée comme tout article.
RE_TEXT_HEAD = re.compile(r"\s*(?:,\s*" + _PARA + r"\s*,\s*)?\s*(?:de\s+la|du|de\s+l['’]|des)\s*"
                          r"(?:même\s+|ladite\s+|dudit\s+)?"
                          r"(?:codes?|conventions?|directives?|règlements?|chartes?|pactes?"
                          r"|traités?|protocoles?|déclarations?|constitution|lois?|décrets?"
                          r"|ordonnances?|arrêtés?|accords?|délibérations?"
                          r"|(?-i:[A-Z]{2,})\b|C\.)"
                          # « articles 1134, alinéa 1er, dans sa rédaction antérieure à celle
                          # issue de l'ordonnance n° 2016-131 du 10 février 2016, et 1869 du
                          # code civil »
                          r"|\s*(?:,\s*" + _PARA + r"\s*)?,\s*dans\s+(?:sa|leur)\s+rédaction\b",
                          re.I)
CONTINUED_GAP = 250


def _continued(text, matches):
    out = []
    for m in matches:
        if not m.group(0).lower().startswith("articles"):
            continue
        end = m.end()
        while True:
            after = text[end:end + CODE_NAME]
            found = find_code(after)
            named = RE_TEXT_AFTER.match(after)
            if found and _CODE_LINK.fullmatch(after, 0, found[1]) and found[1] <= CODE_AFTER:
                end += found[2]
            elif named and _text_ref(named) and _TEXT_LINK.fullmatch(after, 0,
                                                                       named.start("nature")):
                end += named.end()
            else:
                more = _after_other_text(text, end)
                if not more:
                    break
                out.append(_Number(more, loose=True))
                end = more.end(1)
                continue
            more = RE_CONTINUED.match(text, end)
            if not more:
                break
            out.append(_Number(more))
            end = more.end(1)
    return out


def _after_other_text(text, end):
    """La suite d'une liste d'articles derrière un texte qui n'est ni un code ni une loi, dans
    la même phrase, sans autre « article » entre les deux ; sinon None."""
    if not RE_TEXT_HEAD.match(text, end):
        return None
    stop = RE_SENTENCE_END.search(text, end, end + CONTINUED_GAP)
    hi = stop.start() if stop else min(len(text), end + CONTINUED_GAP)
    more = RE_CONTINUED.search(text, end, hi)
    if (not more or re.search(r"\bart(?:icle)?s?\b", text[end:more.start()], re.I)
            or not RE_TEXT_HEAD.match(text, more.end(1))):
        return None
    return more


RE_OWN_ARTICLE = re.compile(r"\s*[:\-–]\s")
RE_OWN_ARTICLE_BEFORE = re.compile(r"(?:^|[.;:\n\f]\s*|\s{2,})$")


def extract_articles(text):
    """Renvoie (citations d'articles, remarques, relevés non vérifiés, places des lois qui ont
    servi à un article, places de tous les codes et textes qui ont servi à un article).

    « span » couvre l'article ET ce à quoi il est rattaché (« article 1240 du Code civil »,
    « C. trav., art. L. 1152-1 », « article 22 de la loi n° 89-462 ») : le PDF annoté le
    surligne d'un seul tenant, et un rattachement absurde se voit sur la page. « core » :
    l'article seul, pour le retrouver si le bloc entier ne se retrouve pas sur la page."""
    # « Article 1er : L'arrêté est annulé. Article 2 : ... » : le dispositif du jugement
    # lui-même, pas une citation (audit visuel du 02/10/2026).
    matches = [m for m in RE_ARTICLES.finditer(text)
               if not (RE_OWN_ARTICLE.match(text, m.end()) and m.group(0)[0] == "A"
                       and re.fullmatch(r"1er|\d{1,2}", m.group(1).strip())
                       and RE_OWN_ARTICLE_BEFORE.search(text, max(0, m.start() - 3),
                                                        m.start()))]
    matches = sorted(matches + _continued(text, matches), key=lambda m: m.start())
    quotes = assign_quotes(text, [(m.start(), m.end()) for m in matches])
    citations, seen, no_code, attached, doubtful = [], Seen(), [], [], []
    unchecked = []          # (numéro, place, pourquoi) : relevés, jamais envoyés
    ranges = []             # (« 131-6 à 131-11 », place, code ou texte) : jamais envoyés
    text_used = []          # où sont écrites les lois qui ont servi à un article
    named_used = []         # où sont écrits les codes et textes qui ont servi à un article
    last_code = last_idcc = last_text = None
    code_at = text_at = -1  # où commence l'article qui a pris last_code, last_text
    codes_of = {}           # numéro -> codes auxquels il a déjà été rattaché
    last_kind = None        # ce qu'a pris l'article précédent : "code", "text" ou None
    idcc_taken = set()      # les IDCC déjà rattachés à un article (leur position)
    used_until = 0          # la fin du code ou du texte pris par l'article précédent
    prev_start = 0          # le début de l'article précédent
    contested_at = None     # un code collé derrière une virgule, que personne n'a pris
    ahead = None            # (début de l'article suivant, ce qui est écrit devant lui)
    marks = [[], [], 0]     # codes déjà lus : leurs débuts, leurs titres, lu jusqu'où

    def codes_between(lo, hi):
        """Les codes nommés dans text[lo:hi], chacun lu une seule fois : les zones de « du
        même code » avancent avec le texte, sans revenir en arrière."""
        starts, titles, done = marks
        if hi > done:
            at = max(lo, done)
            for title, s, _ in find_codes(text[at:hi]):
                starts.append(at + s)
                titles.append(title)
            marks[2] = hi
        return [(starts[i], titles[i])
                for i in range(bisect.bisect_left(starts, lo), bisect.bisect_left(starts, hi))]
    for index, m in enumerate(matches):
        gap_start, prev_start = prev_start, m.start()
        # Le code, le texte ou la convention se cherchent dans la même phrase : « L'article
        # 1240. Cette solution ne figure pas au code de commerce » ne cite pas le Code de
        # commerce (audit du 01/10/2026).
        stop = RE_SENTENCE_END.search(text, m.end(), m.end() + CODE_NAME)
        after = text[m.end(): stop.start() + 1 if stop else m.end() + CODE_NAME]
        found_numbers = _list_numbers(m.group(1))
        numbers = [normalize_number(x.group(0)) for x in found_numbers]
        quote = quotes.get(index) if len(numbers) == 1 else None
        # Ce que surligne chaque numéro : l'article entier s'il est seul ; sinon chacun son
        # numéro (« articles 1240 et 1241 » : deux verdicts, jamais peints l'un sur l'autre).
        cores = ([m.span()] if len(numbers) == 1 else
                 [(m.start(1) + x.start(), m.start(1) + x.end()) for x in found_numbers])
        # « articles 131-6 à 131-11 du code pénal » : un intervalle. Ses bornes seules ne
        # disent rien des articles entre elles : tout l'intervalle est non vérifié (gris),
        # jamais deux bleus qui feraient croire l'ensemble vérifié (Jean, 02/10/2026).
        ranged = {}
        for i in range(len(found_numbers) - 1):
            if m.group(1)[found_numbers[i].end():found_numbers[i + 1].start()].strip() == "à":
                ranged[i] = i + 1

        def kept(court):
            """(numéro, place) à vérifier ; les intervalles partent en non vérifié."""
            skip = set(ranged) | set(ranged.values())
            for i, j in ranged.items():
                ranges.append((f"{numbers[i]} à {numbers[j]}", (cores[i][0], cores[j][1]),
                               court))
            for k, n in enumerate(numbers):
                if n == "Préliminaire":
                    skip.add(k)
                    unchecked.append((n, cores[k], PRELIMINARY))
            return [(n, c) for k, (n, c) in enumerate(zip(numbers, cores)) if k not in skip]

        def unsure(contested=None):
            # Un code collé derrière une virgule (« art. 1240, C. trav., art. ... ») n'est à
            # personne de sûr : ni à cet article, ni au suivant (contested_at).
            # Pareil pour tout code écrit derrière un article douteux, avant l'article suivant
            # (« C. civ., art. 1240 au C. trav., art. L. 1152-1 »).
            nonlocal used_until, contested_at, last_kind
            doubtful.extend(numbers)
            unchecked.extend((n, c, UNSURE) for n, c in zip(numbers, cores))
            # (« article 1241 du même code, C. trav., art. ... » : la place du code est déjà prise
            # par « du même code », le « C. trav. » est celui de l'article suivant.)
            loose = None if RE_SAME_CODE.search(after) else find_code(after)
            contested_at = contested or (m.end() + loose[1] if loose
                                         and not RE_ARTICLES.search(after[:loose[1]]) else None)
            used_until, last_kind = m.end(), None

        if RE_ATTACHED.match(after):
            attached.extend(numbers)            # avenant, accord : pas le texte de base
            unchecked.extend((n, c, ATTACHED) for n, c in zip(numbers, cores))
            used_until, last_kind = m.end(), None
            continue
        if len({n[0].isdigit() for n in numbers if n != "Préliminaire"}) > 1:
            # « articles 1240 et L. 1152-1 du Code du travail » : un numéro nu et un numéro en
            # L., R. ou D. ne sont pas toujours du même code (audit du 02/10/2026).
            unsure()
            continue

        # La suite de la phrase qui appartient à cet article : jusqu'à la fin de la phrase,
        # ou jusqu'au code ou à la loi écrit devant l'article suivant.
        limit = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        end = RE_SENTENCE_END.search(text, m.end(), limit)
        rest_end = end.start() if end else limit
        # Devant : un code ou une loi collé, que l'article précédent n'a pas pris (déjà lu
        # par l'article précédent, comme ce qui est écrit devant son suivant).
        # (La suite d'une liste derrière un autre texte n'a rien devant elle : ce qui précède
        # est le texte du numéro d'avant, « articles 6 de la convention ..., 591 et 593 du code
        # de procédure pénale ».)
        follows = getattr(m, "loose", False)
        written = (None if follows else ahead[1] if ahead and ahead[0] == m.start()
                   else _written_before(text, m.start()))
        ahead = None
        if not end and index + 1 < len(matches):
            ahead = (limit, _written_before(text, limit))
            if ahead[1]:
                rest_end = max(m.end(), ahead[1][2])

        mine_before = reused = None
        if written:
            if written[2] < used_until:
                reused = written          # « article 1240 du Code civil, art. 1241 »
            elif written[2] == contested_at:
                unsure()                  # « art. 1240, C. trav., art. L. 1152-1 »
                continue
            else:
                mine_before = written

        # Ce qui précède, dans la phrase, depuis ce que l'article d'avant a pris : aucun autre
        # code ni texte (« C. pén. et C. trav., art. L. 1152-1 », « loi du 6 juillet 1989 et
        # loi du 24 mars 2014, article 22 » : l'article est peut-être celui des deux).
        head_start = m.start() if follows else max(used_until, m.start() - WINDOW)
        for sentence in RE_SENTENCE_END.finditer(text, head_start, m.start()):
            head_start = sentence.end()
        head_end = mine_before[2] if mine_before else m.start()
        named_before = ([] if head_start >= head_end else
                        [x.group(0) for x in _ANY_TEXT.finditer(text, head_start, head_end)])
        code_before = _has_code(text, head_start, head_end)
        crowded_head = bool(named_before) or code_before
        # Pour une convention, un IDCC écrit plus tôt n'est pas un autre texte (deux IDCC
        # différents sont traités plus bas).
        crowded_for_convention = crowded_head and not (
            not code_before
            and all(re.fullmatch(r"IDCC|conventions?|CCNT?", w, re.I) for w in named_before))

        # Une convention collective, rattachée par « de la ».
        same = RE_SAME_CONVENTION.match(after)
        named = same or RE_CONVENTION.match(after)
        if named and _CONVENTION_LINK.match(after):
            if mine_before or crowded_for_convention:
                unsure()                  # « C. civ., art. 1240 de la convention... »
                continue
            # Deux IDCC dans la phrase, devant ou derrière : « (IDCC 1979 ou IDCC 1486) »,
            # « IDCC 1979 ou IDCC 1486, article 5 de la convention collective ».
            if len({int(x.group(1)) for x in RE_IDCC.finditer(text, head_start, rest_end)
                    if x.start() not in idcc_taken}) > 1:
                unsure()
                continue
            reach = (m.start(), m.end() + named.end())
            taken = reach[1]          # jusqu'à l'IDCC qui a servi, même s'il n'est pas peint
            if same and last_idcc:
                idcc = last_idcc
            else:
                # Un IDCC déjà rattaché à l'article précédent n'est repris que par « la même
                # convention » : « article 5 de la convention collective (IDCC 1979) et
                # article 99 de la convention collective » ne dit pas laquelle est la seconde.
                where, idcc = nearest_idcc(text, m.start(), m.end(), idcc_taken)
                if idcc:
                    told = RE_IDCC.match(text, where)
                    # « et non l'IDCC 1979 », « ou IDCC 1486 », ou un IDCC déjà dépassé par
                    # l'article précédent : pas sûr que ce soit le sien.
                    between = (text[reach[1]:where] if where >= reach[1]
                               else text[told.end():m.start()])
                    if where < head_start or _NOT_THIS.search(between):
                        unsure()
                        continue
                    idcc_taken.add(where)
                    if where >= reach[1]:
                        taken = told.end()
                        if _convention_name(text, reach[1], where):
                            reach = (reach[0], told.end())
            last_idcc = idcc or last_idcc
            used_until, last_kind = taken, None
            for number, core in kept(f"IDCC {idcc}" if idcc else "convention collective"):
                span = _fit(text, reach, core, len(numbers))
                if seen.again(("idcc", idcc, number), span, core):
                    continue
                citations.append({"kind": "convention_article", "order": "legislation",
                                  "court": f"IDCC {idcc}" if idcc else "convention collective",
                                  "idcc": idcc, "number": number, "cited_date": None,
                                  "quote": quote, "span": span, "core": core})
                seen[("idcc", idcc, number)] = citations[-1]
            continue

        # Derrière : un code, une loi, « du même code », « de la même loi », selon un modèle.
        mine_after = None                 # (genre, valeur, fin dans `after`, fin peinte)
        found = find_code(after)
        same_code = RE_SAME_CODE.search(after)
        if same_code and found and found[1] < same_code.end():
            same_code = None              # « de ce code du travail » nomme un code
        # « article 46 quater-0 ZZ. du CGI » : le point est celui du suffixe.
        lo = 1 if after.startswith(".") and m.group(1)[-1:].isalpha() else 0
        # « art. 1240, C. civ. » : derrière une virgule, le code n'est celui de l'article que si
        # aucun autre article ne le suit (sinon : « art. 1240, C. trav., art. L. 1152-1 »).
        comma = bool(found and re.fullmatch(r"\s*,\s*", after[lo:found[1]])
                     and not _NEXT_ARTICLE.match(after, found[2]))
        # « art. 1240 C. trav., art. L. 1152-1 » : un code derrière un simple espace, suivi
        # d'un autre article qui n'a pas le sien, peut être celui de l'un ou de l'autre (comme
        # avec la virgule). « art. 222-33 C. pén., art. 1240 C. civ. » reste sûr.
        bare = bool(found and _BARE.fullmatch(after, lo, found[1])
                    and _NEXT_ARTICLE.match(after, found[2])
                    and not (index + 1 < len(matches)
                             and _code_follows(text, matches[index + 1].end())))
        # « art. 46 du CGI, annexe III », « article 46 du CGI (annexe III) » : le code ou son
        # annexe. Seul « de l'annexe III au CGI » dit l'annexe sans détour.
        annex = bool(found and (re.match(r"\s*[,(]?\s*ann(?:exe|\.)", after[found[2]:], re.I)
                                or found[0].startswith("Code général des impôts, annexe")
                                and not re.match(r"ann", after[found[1]:found[2]], re.I)))
        if annex or bare:
            unsure()
            continue
        if (found and found[1] <= CODE_AFTER and not same_code
                and (comma or _CODE_LINK.fullmatch(after, lo, found[1]))):
            painted = found[2]
            if "(" in after[:found[1]]:
                # « art. 1240 (C. civ.) » ; pas « art. 1240 (C. trav., art. L. 1152-1) »,
                # qui ouvre une autre citation.
                painted = found[2] + 1 if after[found[2]:found[2] + 1] == ")" else None
            if painted:
                mine_after = ("code", found[0], painted, painted)
        named = RE_TEXT_AFTER.match(after)
        if named and _text_ref(named) and _TEXT_LINK.fullmatch(after, 0, named.start("nature")):
            if mine_after:
                unsure()
                continue
            mine_after = ("text", _text_ref(named), named.end(), named.end())
        block = RE_BLOCK_AFTER.match(after)
        if block and not mine_after:
            mine_after = ("text", BLOCK[block.lastgroup], block.end(), block.end())
        via_same = False                  # « du même code », « de la même loi »
        same_text = RE_SAME_TEXT.match(after)
        if (same_code or same_text) and not mine_after:
            # Le texte repris, selon l'une de deux lectures sûres, sinon non vérifié :
            #   1. celui de l'article précédent, dans cette phrase ou les deux d'avant, si aucun
            #      autre n'est nommé depuis (« l'article 1719 du code civil ..., et l'article
            #      1720 du même code ») ;
            #   2. sinon, le seul texte nommé dans la fenêtre (« Le Code du travail est
            #      applicable. L'article L. 1152-1 du même code »). « Le Code civil et le Code
            #      pénal s'appliquent. L'article 222-33 du même code » : lequel ?
            window, guard = _same_zone(text, m.start())
            prev_counts = gap_start >= guard or (
                last_kind and not RE_SENTENCE_END.search(text, gap_start, m.start()))
        if same_code and not mine_after:
            codes = codes_between(window, m.start())
            named_codes = {title for _, title in codes}
            value = None
            # (Un article sans code entre les deux, « (anciennement article 1382) », ne
            # nomme rien : il ne coupe pas le lien.)
            if (last_code and code_at >= guard
                    and {title for at, title in codes if at >= code_at} <= {last_code}):
                value = last_code
            else:
                if last_kind == "code" and prev_counts:
                    named_codes.add(last_code)
                if len(named_codes) == 1:
                    value = named_codes.pop()
                elif (re.search(r"précité|susvisé", same_code.group(0), re.I)
                      and len(numbers) == 1 and len(codes_of.get(numbers[0], ())) == 1):
                    # « l'article L. 423-23 du code précité » : ce même article a déjà été
                    # cité, avec un seul code.
                    value = next(iter(codes_of[numbers[0]]))
            if not value:
                unsure()
                continue
            mine_after = ("code", value, same_code.end(), same_code.end())
            via_same = True
        if same_text and not mine_after:
            nature = TEXT_NATURES[same_text.group("nature").lower()]
            key = last_text and (last_text["text_nature"], last_text["text_number"],
                                 last_text["text_date"])
            value = None
            if (last_text and text_at >= guard
                    and set(_texts_in(text[text_at:m.start()])) <= {key}):
                value = last_text
            else:
                refs = set(_texts_in(text[window:m.start()]))
                if last_kind == "text" and prev_counts:
                    refs.add(key)
                if len(refs) == 1:
                    ref = refs.pop()
                    value = last_text if ref == key else dict(zip(
                        ("text_nature", "text_number", "text_date"), ref))
            if not value or value["text_nature"] != nature:
                unsure()
                continue
            mine_after = ("text", value, same_text.end(), same_text.end())
            via_same = True

        # Un seul texte : devant ou derrière, pas les deux (sauf le même code, écrit deux
        # fois), et aucun autre dans la suite de la phrase.
        if mine_before and mine_after and not (mine_before[0] == mine_after[0] == "code"
                                               and mine_before[1] == mine_after[1]):
            unsure()
            continue
        if not mine_before and not mine_after:
            if reused:
                unsure()                  # le texte de l'article d'avant, sans plus
                continue
            # Un code ou un texte nommé tout près, mais pas selon un modèle : non vérifié.
            loose = find_code(after)
            if loose and loose[1] <= CODE_AFTER or _ANY_TEXT.search(text, m.end(), rest_end):
                unsure()
                continue
            no_code.extend(numbers)
            unchecked.extend((n, c, NO_TEXT) for n, c in zip(numbers, cores))
            used_until, last_kind = m.end(), None
            continue
        # (« les dispositions du code de l'entrée ... méconnaissent le droit garanti par
        # l'article 16 de la Déclaration de 1789 » : écrite en toutes lettres derrière lui, la
        # Constitution ou la Déclaration ne peut être lue comme un code nommé avant.)
        block_after = (mine_after and not mine_before and mine_after[0] == "text"
                       and mine_after[1]["text_nature"] in BLOCK_TITLES)
        if crowded_head and not via_same and not block_after:
            unsure()                      # un autre texte nommé juste avant
            continue
        tail = m.end() + (mine_after[2] if mine_after else 0)
        # (« et aux » se lit avec ce qui suit : « et aux articles 338-1 » annonce l'article
        # suivant, pas un autre code pour celui-ci.)
        alternative = _ALTERNATIVE.match(text, tail, min(len(text), rest_end + 40))
        if tail < rest_end and (_has_code(text, tail, rest_end)
                                or _ANY_TEXT.search(text, tail, rest_end)
                                or alternative and alternative.end() <= rest_end):
            unsure()                      # un autre texte nommé dans la suite de la phrase
            continue
        if rest_end < limit and _DANGLING.search(text, tail, rest_end):
            # « C. civ., art. 1240. du Code du travail, art. L. 1152-1 » : le code qui suit
            # le « du » peut être celui-ci ou celui de l'article suivant. Ni l'un ni l'autre.
            unsure(contested=rest_end)
            continue

        kind, value = (mine_after or mine_before)[:2]
        start = mine_before[2] if mine_before else m.start()
        reach = (start, m.end() + mine_after[3] if mine_after else m.end())
        if kind == "text" and not via_same:
            # La loi qui a servi à l'article : elle n'est pas vérifiée une seconde fois
            # comme texte cité en entier.
            text_used.append((start, m.start()) if mine_before else (m.end(), reach[1]))
        named_used.append((start, m.start()) if mine_before else (m.end(), reach[1]))
        used_until, last_kind = max(m.end(), reach[1]), kind
        if kind == "text":
            last_text, text_at = value, m.start()
            for number, core in kept(_text_label(value)):
                span = _fit(text, reach, core, len(numbers))
                key = ("text", value["text_nature"], value["text_number"], value["text_date"],
                       number)
                if seen.again(key, span, core):
                    continue
                citations.append({"kind": "text_article", "order": "legislation",
                                  "court": _text_label(value), **value, "number": number,
                                  "cited_date": None, "quote": quote, "span": span,
                                  "core": core})
                seen[key] = citations[-1]
            continue
        last_code, code_at = value, m.start()
        for number in numbers:
            codes_of.setdefault(number, set()).add(value)
        for number, core in kept(value):
            span = _fit(text, reach, core, len(numbers))
            if seen.again((value, number), span, core):
                continue
            citations.append({"kind": "article", "order": "legislation", "court": value,
                              "code": value, "number": number, "cited_date": None,
                              "quote": quote, "span": span, "core": core})
            seen[(value, number)] = citations[-1]
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
    if doubtful:
        remarks.append(f"{len(doubtful)} article(s) dont le code ou le texte n'est pas "
                       f"certain : {', '.join(doubtful[:12])}"
                       f"{'...' if len(doubtful) > 12 else ''}. La phrase ne le rattache pas à "
                       "un seul texte de façon sûre (deux textes nommés, ou un code qui peut "
                       "être celui de l'article voisin). Non vérifiés : à vérifier à la main.")
    if ranges:
        remarks.append(f"{len(ranges)} intervalle(s) d'articles : "
                       f"{', '.join(r[0] for r in ranges[:12])}. Les articles compris entre "
                       "les bornes ne sont pas vérifiés un par un : non vérifiés.")
    out = _unverified(unchecked, seen)
    for label, place, court in ranges:
        key = ("range", court, label)
        if seen.again(key, place):
            continue
        out.append({"kind": "unverified", "order": "unverified", "court": court,
                    "what": "range", "number": label, "cited_date": None, "reason": RANGE,
                    "span": place})
        seen[key] = out[-1]
    return citations, remarks, out, text_used, named_used


# Ce qui est relevé sans être vérifié : sur le PDF annoté, en gris avec son « ? », pour que
# le lecteur sache où regarder à la main. Sans rectangle, « vu mais pas sûr » ne se
# distinguait pas de « pas vu du tout ». Seul le numéro est peint : aucun texte n'a été
# retenu pour lui.
UNSURE = ("le code ou le texte de cet article n'est pas certain (deux textes nommés, ou un "
          "code qui peut être celui de l'article voisin) : non vérifié, à vérifier à la main")
NO_TEXT = ("ni code ni texte reconnu à côté de cet article (un texte cité sans numéro ni date, "
           "un traité, une convention internationale, un arrêté...) : non vérifié")
ATTACHED = ("article d'un avenant ou d'un accord collectif : seul le texte de base des "
            "conventions est vérifié")
RANGE = ("intervalle d'articles : les articles compris entre les bornes ne sont pas vérifiés "
         "un par un : non vérifié, à vérifier à la main")
PRELIMINARY = ("article préliminaire, sans numéro : non vérifié, à vérifier à la main")
NO_COURT = ("numéro RG sans cour d'appel ni tribunal judiciaire reconnu dans la phrase (les "
            "jugements de prud'hommes, par exemple, ne sont pas publiés) : non vérifié")


# Les lois, ordonnances et décrets cités en entier : « la loi n° 91-647 du 10 juillet 1991
# relative à l'aide juridique », « dans sa rédaction issue de la loi n° 2018-217 du 29 mars
# 2018 ». Une IA invente volontiers un numéro de loi, ou donne la bonne loi avec la mauvaise
# date : on vérifie que le texte existe (texts.check_text). Un numéro ou une date est exigé ;
# une ordonnance sans numéro est le plus souvent celle d'un juge (« l'ordonnance du 26 juin
# 2023 a fixé... ») : écartée.
RE_WHOLE_TEXT = re.compile(r"\b" + _TEXT_REF, re.I)


# Sauf dans la formule des versions : « dans sa rédaction antérieure à celle issue de
# l'ordonnance du 10 février 2016 » est un texte, jamais celle d'un juge (vraies décisions du
# 02/10/2026).
RE_VERSION_OF = re.compile(r"(?:rédaction|version)\s+(?:antérieure\s+à\s+(?:celle\s+)?)?"
                           r"(?:issue\s+de\s+|résultant\s+de\s+)?l['’]\s*$", re.I)


def extract_texts(text, used):
    """Les textes cités en entier, hors ceux qui ont servi à un article (`used`)."""
    out, seen = [], Seen()
    for m in RE_WHOLE_TEXT.finditer(text):
        ref = _text_ref(m)
        if not ref or (ref["text_nature"] == "ORDONNANCE" and not ref["text_number"]
                       and not RE_VERSION_OF.search(text, max(0, m.start() - 60), m.start())):
            continue
        span = (m.start("nature"), m.end())
        if any(a < span[1] and span[0] < b for a, b in used):
            continue
        key = ("text", ref["text_nature"], ref["text_number"], ref["text_date"])
        if seen.again(key, span):
            continue
        out.append({"kind": "text", "order": "legislation", "court": _text_label(ref), **ref,
                    "number": ref["text_number"], "cited_date": None, "span": span})
        seen[key] = out[-1]
    return out


# Les autres textes cités, que ce programme ne vérifie pas encore : relevés en gris, pour que
# le lecteur sache qu'ils sont là (vraies décisions du 02/10/2026, relues par Grok : « Vu : -
# le code de l'urbanisme », « la Charte des droits fondamentaux », « le règlement (UE)
# 2017/1001 », « l'arrêté du 4 août 2004 relatif aux commissions de réforme »...). Un seul
# relevé par texte ; ses autres mentions sont des reprises. Liste fermée : un nom inconnu
# n'est pas deviné.
_D = (r"(?:1er|\d{1,2})\s+(?:" + "|".join(map(re.escape, MONTHS)) + r")\s+\d{4}")
_APOS = r"['’]\s*"
OTHER_TEXTS = [(re.compile(rx, re.I), label) for rx, label in [
    (r"\bconvention\s+(?:européenne\s+(?:de\s+sauvegarde\s+)?des\s+droits\s+de\s+l" + _APOS
     + r"homme|de\s+sauvegarde\s+des\s+droits\s+de\s+l" + _APOS + r"homme)"
     r"(?:\s+et\s+des\s+libertés\s+fondamentales)?|\b(?-i:CESDH|CSDH)\b",
     "Convention européenne des droits de l'homme"),
    (r"\bconvention\s+(?:internationale\s+)?relative\s+aux\s+droits\s+de\s+l" + _APOS
     + r"enfant", "Convention internationale relative aux droits de l'enfant"),
    (r"\bcharte\s+des\s+droits\s+fondamentaux(?:\s+de\s+l" + _APOS + r"Union\s+européenne)?",
     "Charte des droits fondamentaux de l'Union européenne"),
    (r"\bpacte\s+international\s+relatif\s+aux\s+droits\s+civils\s+et\s+politiques",
     "Pacte international relatif aux droits civils et politiques"),
    (r"\bpacte\s+international\s+relatif\s+aux\s+droits\s+économiques,?\s+sociaux\s+et"
     r"\s+culturels", "Pacte international relatif aux droits économiques, sociaux et culturels"),
    (r"\bdéclaration\s+universelle\s+des\s+droits\s+de\s+l" + _APOS + r"homme",
     "Déclaration universelle des droits de l'homme"),
    (r"\bconvention\s+sur\s+les\s+droits\s+de\s+l" + _APOS + r"homme\s+et\s+la\s+biomédecine",
     "Convention sur les droits de l'homme et la biomédecine"),
    (r"\bconvention\s+sur\s+l" + _APOS + r"élimination\s+de\s+toutes\s+les\s+formes\s+de"
     r"\s+discrimination\s+à\s+l" + _APOS + r"égard\s+des\s+femmes",
     "Convention sur l'élimination de toutes les formes de discrimination à l'égard des femmes"),
    (r"\bconvention\s+n[°º]\s*(\d{1,3})\s+de\s+l" + _APOS
     + r"(?:OIT|Organisation\s+internationale\s+du\s+travail)",
     "Convention n° {} de l'Organisation internationale du travail"),
    (r"\bconvention\s+d" + _APOS + r"application\s+de\s+l" + _APOS
     + r"accord\s+de\s+Schengen", "Convention d'application de l'accord de Schengen"),
    (r"\btraité\s+sur\s+le\s+fonctionnement\s+de\s+l" + _APOS + r"Union\s+européenne"
     r"|\b(?-i:TFUE)\b", "Traité sur le fonctionnement de l'Union européenne"),
    (r"\btraité\s+sur\s+l" + _APOS + r"Union\s+européenne|\b(?-i:TUE)\b",
     "Traité sur l'Union européenne"),
    # Avec sa majuscule : « la constitution d'une société » n'en est pas une.
    (r"\b(?-i:Constitution)\b(?!\s+(?:du\s+27\s+octobre\s+1946|de\s+1946|de\s+1848))",
     "Constitution du 4 octobre 1958"),
    # « la Constitution, notamment son Préambule », « le Préambule de la Constitution de 1946 »
    # (Le « Préambule » d'un contrat n'en est pas un.)
    (r"\b(?-i:Préambule)\s+(?:de\s+la\s+Constitution|de\s+1946)\b"
     r"|(?<=\bson\s)(?-i:Préambule)\b", "Préambule de la Constitution"),
    (r"\bdéclaration\s+des\s+droits\s+de\s+l" + _APOS + r"homme\s+et\s+du\s+citoyen"
     r"|\bDéclaration\s+de\s+1789\b|\b(?-i:DDHC)\b",
     "Déclaration des droits de l'homme et du citoyen de 1789"),
    # « règlement (UE) 2017/1001 », « Directive 2001/20/CE », « règlement (CE) n° 507/2006 »
    (r"\b(règlement|directive)\s*(\(\s*(?:UE|CE|CEE|Euratom)\s*\)|(?:UE|CE|CEE)\b)?\s*"
     r"(?:n[°º]\s*)?(\d{2,4}/\d{1,4}(?:/(?:UE|CE|CEE))?)\b", "{} {} {}"),
    # « l'arrêté du 4 août 2004 », « arrêté interministériel du 1er octobre 2025 », « un arrêté
    # n° 2024-3958 du 24 octobre 2024 », « l'arrêté du maire de Six-Fours-les-Plages du 1er
    # octobre 2021 »
    (r"\barrêté(?:\s+(?:interministériel|ministériel|préfectoral|municipal))?"
     r"(?:\s+n[°º]\s*[\w/-]+)?(?:\s+du\s+(?:maire|préfet|ministre)\b[^,;.\d]{0,60}?)?"
     r"\s+du\s+(" + _D + r")", "Arrêté du {}"),
    # « les dispositions du plan local d'urbanisme approuvé le 10 avril 2015 »
    (r"\bplan\s+local\s+d" + _APOS + r"urbanisme\s+(?:approuvé|adopté)\s+(?:le|par\s+"
     r"(?:une\s+)?délibération\s+du)\s+(" + _D + r")", "Plan local d'urbanisme approuvé le {}"),
    (r"\bloi\s+du\s+pays\s+(?:n[°º]\s*([\d-]+)\s+)?du\s+(" + _D + r")", "Loi du pays du {1}"),
    (r"\bdélibération\s+n[°º]\s*([\w/.-]*\d[\w/.-]*)(?:\s+du\s+" + _D + r")?",
     "Délibération n° {}"),
    (r"\baccord\s+(?:d" + _APOS + r"entreprise\s+|collectif\s+|d" + _APOS
     + r"établissement\s+)?du\s+(" + _D + r")", "Accord du {}"),
]]
# Un code juste derrière un article est celui de l'article, même non retenu (« l'article
# 1134 ancien du code civil ») : pas un code cité seul.
RE_ARTICLE_TAIL = re.compile(r"(?:\d|\b1er|\bpréliminaire|\bsuivants|\bs\.|\bancien)\W{0,3}"
                             r"(?:(?:alinéa|al\.?)\s*\S+\s*,?\s*)?(?:du|de\s+la|de\s+l['’]|des"
                             r"|au|aux|dudit|du\s+même|de\s+ce|\()\s*$", re.I)
# « la méconnaissance des articles UC 1, 2, 3, 6, 7 et 13 du règlement du plan local
# d'urbanisme » : des articles d'un règlement local, jamais publiés dans une base nationale.
RE_PLU_ARTICLES = re.compile(r"\barticles?\s+(?-i:((?:[1-9]?AU|U|N|A)[A-Z]{0,2})\s*(\d{1,2})"
                             r"((?:\s*(?:,|et)\s*\d{1,2}\b)*))"
                             r"(?=[^.;]{0,80}\b(?:plan\s+local\s+d['’]\s*urbanisme|PLU|POS)\b)",
                             re.I)
OTHER_TEXT = "texte cité, que ce programme ne vérifie pas : non vérifié, à vérifier à la main"
PLU_ARTICLE = ("article d'un plan local d'urbanisme, que ce programme ne vérifie pas : non "
               "vérifié, à vérifier à la main")
WHOLE_CODE = "code cité sans article : rien à vérifier, relevé pour mémoire"


def extract_other_texts(text, used):
    """Les codes cités sans article et les textes de la liste ci-dessus, hors ceux qui ont
    servi à un article (`used`) : relevés non vérifiés."""
    found = []
    for title, start, end in find_codes(text):
        if (RE_ARTICLE_TAIL.search(text, max(0, start - 40), start)
                or re.match(r"\s*,?\s*art(?:icle)?s?\b", text[end:end + 12], re.I)):
            continue
        found.append((start, end, title, WHOLE_CODE))
    for rx, label in OTHER_TEXTS:
        for m in rx.finditer(text):
            words = [" ".join((g or "").split()) for g in m.groups()]
            if words and label.startswith("{} "):
                words[0] = words[0].capitalize()
            found.append((m.start(), m.end(), " ".join(label.format(*words).split()),
                          OTHER_TEXT))
    for m in RE_PLU_ARTICLES.finditer(text):
        numbers = [m.group(2)] + re.findall(r"\d{1,2}", m.group(3))
        found.append((m.start(), m.end(), "Plan local d'urbanisme, article"
                      + ("s " if len(numbers) > 1 else " ")
                      + ", ".join(f"{m.group(1)} {n}" for n in numbers), PLU_ARTICLE))
    out, seen = [], Seen()
    for start, end, label, why in sorted(found):
        if any(a < end and start < b for a, b in used):
            continue
        key = ("other text", label)
        if seen.again(key, (start, end)):
            continue
        out.append({"kind": "unverified", "order": "unverified", "court": label,
                    "what": "text", "number": None, "cited_date": None, "reason": why,
                    "span": (start, end)})
        seen[key] = out[-1]
    return out


def _unverified(found, seen, what="article"):
    """Les citations « unverified » : (numéro, place, pourquoi), une par numéro et raison ;
    ses reprises gardent leur place."""
    out = []
    for number, place, why in found:
        key = ("unverified", number, why)
        if seen.again(key, place):
            continue
        out.append({"kind": "unverified", "order": "unverified", "court": None, "what": what,
                    "number": number, "cited_date": None, "reason": why, "span": place})
        seen[key] = out[-1]
    return out


# Cours d'appel et tribunaux judiciaires

# Un RG : deux chiffres (l'année), une barre, quatre ou cinq chiffres. On l'exige précédé de
# « RG » ou « n° » : sinon « 03/2019 » (un mois) passerait pour un numéro.
RE_RG = re.compile(r"(?:\bRG|\bR\.G\.|n[°º])\s*(?:n[°º]\s*)?:?\s*(\d{2}/\d{4,5})\b")
RE_LOWER_COURT = re.compile(
    r"\b(?P<kind>CA|cour\s+d['’]\s*appel|TJ|TGI|tribunal\s+judiciaire|"
    r"tribunal\s+de\s+grande\s+instance)\b\s*(?P<link>de\s+|d['’]\s*|du\s+|des\s+)?", re.I)
RE_RG_THEN_COURT = re.compile(
    r"\s*,?\s*(?:rendue?|prononcée?)\s+le\s+(\d{1,2})(?:er)?\s+("
    + "|".join(map(re.escape, DATE_MONTHS)) + r")\s+(\d{4})\s+par\s+(?:la|le)\s+", re.I)
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
    # (Toute autre ponctuation arrête la ville : « cour d'appel de Lyon. Selon » se lisait
    # « Lyon Selon », le point sauté.)
    words = re.findall(r"[\wÀ-ÿ]+|['’-]|\s+|.", text[:60], re.S)
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
    citations, seen, no_court, unchecked = [], Seen(), [], []
    for m in rgs:
        number = m.group(1)
        lo = max(0, m.start() - WINDOW)
        for end in RE_SENTENCE_END.finditer(text, lo, m.start()):
            lo = end.end()
        courts = list(RE_LOWER_COURT.finditer(text, lo, m.start()))
        d = dates.get(m.start())
        if not courts:
            # « un arrêt n° RG 23/07760 rendu le 28 novembre 2024 par la cour d'appel de
            # Lyon » : la cour derrière, collée, selon ce seul modèle.
            later = RE_RG_THEN_COURT.match(text, m.end())
            court = later and RE_LOWER_COURT.match(text, later.end())
            if court:
                courts, d = [court], _iso(later) or d
        city = (_place(courts[-1].group("link") or "", _city(text[courts[-1].end():]))
                if courts else "")
        if not courts or not city:
            no_court.append(number)
            unchecked.append((number, m.span(), NO_COURT))
            continue
        kind = courts[-1].group("kind").lower()
        jurisdiction = "ca" if kind.startswith(("ca", "cour")) else "tj"
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
    return citations, remarks, _unverified(unchecked, seen, "rg")

