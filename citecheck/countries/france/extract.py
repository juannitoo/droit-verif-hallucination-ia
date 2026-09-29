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

MARK_ADMIN = re.compile(r"\b(CE|C\.E\.|Conseil d['’]État|Conseil d['’]Etat|CAA|TA)\b", re.I)
# Les abréviations se terminent par un point ou une fin de mot : sans ça, « Com » attrapait
# le « com » de « communication », et une décision du Conseil d'État était écartée sans bruit.
MARK_JUDICIAL = re.compile(
    r"\b(?:(?:Cass|Civ|Soc|Com|Crim)(?:\.|\b)|Cour de cassation"
    r"|chambre (?:civile|sociale|commerciale))",
    re.I)

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


def assign_dates(text, spans):
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
                best[start] = (gap, day)
    return {start: day for start, (_, day) in best.items()}


def order_of(text, start, default):
    """Le marqueur le plus PROCHE EN AMONT décide.

    Une citation française se lit « Conseil d'État du 5 juin 2009, n° 308850 » : la
    juridiction précède le numéro. Chercher un marqueur « quelque part autour » ferait
    gagner la juridiction de la citation SUIVANTE."""
    before = text[max(0, start - WINDOW):start]
    judicial = max((m.end() for m in MARK_JUDICIAL.finditer(before)), default=-1)
    admin = max((m.end() for m in MARK_ADMIN.finditer(before)), default=-1)
    if judicial < 0 and admin < 0:
        return default
    return "judicial" if judicial > admin else "administrative"


def extract(text):
    """Renvoie (citations, remarques). Une remarque signale ce qui n'a pas pu être lu."""
    citations, undated, set_aside = [], [], []
    appeals = list(RE_APPEAL.finditer(text))
    appeal_numbers = {m.group(1) for m in appeals}
    requests = [m for m in RE_REQUEST.finditer(text) if m.group(1) not in appeal_numbers]
    rgs = list(RE_RG.finditer(text))
    dates = assign_dates(text, [m.span() for m in appeals + requests + rgs])
    seen = set()        # (numéro, date) : un même numéro cité à deux dates = deux citations

    for m in appeals:
        number, d = m.group(1), dates.get(m.start())
        if (number, d) in seen:
            continue
        seen.add((number, d))
        citations.append({"kind": "decision", "order": "judicial", "court": "Cass",
                          "number": number, "cited_date": d, "span": m.span()})
        if not d:
            undated.append(number)

    for m in requests:
        number = m.group(1)
        if order_of(text, m.start(), "administrative") == "judicial":
            set_aside.append(number)    # un n° à 5-7 chiffres près de « Cass. » : douteux
            continue
        d = dates.get(m.start())
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
        if c["cited_date"]:
            by_number.setdefault(c["number"], set()).add(c["cited_date"])
    for number, days in by_number.items():
        if len(days) > 1:
            remarks.append(f"n° {number} cité à {len(days)} dates différentes "
                           f"({', '.join(sorted(days))}) : chacune est vérifiée.")
    citations += lower
    remarks += lower_remarks
    articles, article_remarks = extract_articles(text)
    # Dans l'ordre du document : c'est l'ordre dans lequel l'avocat relira.
    both = sorted(citations + articles, key=lambda c: c["span"][0])
    return both, remarks + article_remarks


# Articles de codes

# Un numéro d'article : lettre facultative (L, R, D, A, avec ou sans point, étoile des
# articles réglementaires), puis des chiffres séparés par des tirets, puis bis/ter...
NUM = (r"(?:[LRDA]\.?\s?\*?\s?)?(?:1er|\d+(?:[-‑.]\d+)*)"
       r"(?:\s(?:bis|ter|quater|quinquies))?\b")
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


RE_SENTENCE_END = re.compile(r"[.;!?]\s+(?=[A-ZÀ-ÖØ-Þ«])")


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
    """« L. 3121-2 » -> « L3121-2 », comme l'écrit Légifrance."""
    n = unicodedata.normalize("NFKC", raw).replace("‑", "-")
    n = re.sub(r"^([LRDA])[\s.*]+", r"\1", n, flags=re.I)   # « L. » : le point du préfixe seul
    n = re.sub(r"\s+", "", n)                                 # « 25.1 » garde son point
    n = re.sub(r"(bis|ter|quater|quinquies)$", r" \1", n, flags=re.I)
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
                       "Les lois et décrets non codifiés ne sont pas vérifiés.")
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

