"""Relève les citations de jurisprudence française dans un texte, par expressions régulières.

POURQUOI PAS UN MODÈLE
  Un modèle qui extrait les citations les comprend, et un modèle qui comprend corrige en
  silence : il rétablit la bonne date, rattache le bon arrêt. Il gommerait exactement ce
  qu'on cherche. Pour relever ce qu'un texte DIT, il faut un outil incapable de savoir ce
  qu'il DEVRAIT dire.

CE QU'IL SAIT LIRE
  administratif : CE / CAA / TA ... n° 308850            (5 à 7 chiffres après « n° »)
  judiciaire    : Cass. / Civ. 2e / Soc. ... 17-28.268 ou 17-28268
  dates en toutes lettres (« 5 juin 2009 ») et en chiffres (05/06/2009)

CE QU'IL NE FAIT JAMAIS
  Deviner. Un numéro sans date lisible sort sans date, et le contrôle de date est annoncé
  impossible. Tout ce qu'il n'a pas su rattacher est signalé : un trou est un trou.
"""
import re

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
    if words:
        day, month, year = m.group(1), MONTHS[m.group(2).lower()], m.group(3)
    else:
        day, month, year = m.group(1), int(m.group(2)), m.group(3)
    return f"{year}-{month:02d}-{int(day):02d}"


def nearest_date(text, start, end):
    """La date la plus proche du numéro, dans la fenêtre. Aucune si rien de lisible."""
    origin = max(0, start - WINDOW)
    zone = text[origin: end + WINDOW]
    pos = start - origin
    found = [(_iso(m), abs(m.start() - pos)) for m in RE_DATE_WORDS.finditer(zone)]
    found += [(_iso(m, False), abs(m.start() - pos)) for m in RE_DATE_DIGITS.finditer(zone)]
    return min(found, key=lambda f: f[1])[0] if found else None


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
    seen, citations, undated, set_aside = set(), [], [], []

    for m in RE_APPEAL.finditer(text):
        number = m.group(1)
        if number in seen:
            continue
        seen.add(number)
        d = nearest_date(text, m.start(), m.end())
        citations.append({"order": "judicial", "court": "Cass",
                          "number": number, "cited_date": d})
        if not d:
            undated.append(number)

    for m in RE_REQUEST.finditer(text):
        number = m.group(1)
        if number in seen:
            continue
        if order_of(text, m.start(), "administrative") == "judicial":
            set_aside.append(number)    # un n° à 5-7 chiffres près de « Cass. » : douteux
            continue
        seen.add(number)
        d = nearest_date(text, m.start(), m.end())
        citations.append({"order": "administrative", "court": "CE",
                          "number": number, "cited_date": d})
        if not d:
            undated.append(number)

    remarks = []
    if undated:
        remarks.append(f"{len(undated)} numéro(s) sans date lisible à côté : "
                       f"{', '.join(undated)}. Leur date ne peut pas être contrôlée.")
    if set_aside:
        remarks.append(f"{len(set_aside)} numéro(s) écarté(s), à 5-7 chiffres mais près d'une "
                       f"juridiction judiciaire : {', '.join(set_aside)}. À vérifier à la main.")
    return citations, remarks
