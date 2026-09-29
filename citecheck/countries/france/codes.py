"""Reconnaître le nom d'un code dans un texte, en toutes lettres ou abrégé.

Les titres exacts sont ceux de Légifrance (/list/code, relevés le 29/09/2026) : les 76 codes
qu'elle donne en vigueur, sans exception, anciens codes presque vides compris (Code des
communes, Code rural (ancien)...) : une IA qui les cite est justement ce qu'on veut voir. Les
abréviations sont celles de l'usage (C. trav., CSS, CPC...). Une abréviation ambiguë n'est
pas reconnue plutôt que d'être devinée : « CT » ou « CP » ne désignent rien de sûr.
"""
import re

TITLES = [
    "Code civil", "Code de commerce", "Code de déontologie des architectes",
    "Code de justice administrative", "Code de justice militaire (nouveau)",
    "Code de l'action sociale et des familles", "Code de l'artisanat",
    "Code de l'aviation civile",
    "Code de l'entrée et du séjour des étrangers et du droit d'asile",
    "Code de l'environnement", "Code de l'expropriation pour cause d'utilité publique",
    "Code de l'organisation judiciaire", "Code de l'urbanisme", "Code de l'éducation",
    "Code de l'énergie",
    "Code de la Légion d'honneur, de la Médaille militaire et de l'ordre national du Mérite",
    "Code de la commande publique", "Code de la consommation",
    "Code de la construction et de l'habitation", "Code de la défense",
    "Code de la famille et de l'aide sociale", "Code de la justice pénale des mineurs",
    "Code de la mutualité", "Code de la propriété intellectuelle", "Code de la recherche",
    "Code de la route", "Code de la santé publique", "Code de la sécurité intérieure",
    "Code de la sécurité sociale", "Code de la voirie routière", "Code de procédure civile",
    "Code de procédure pénale", "Code des assurances", "Code des communes",
    "Code des communes de la Nouvelle-Calédonie", "Code des douanes",
    "Code des impositions sur les biens et services",
    "Code des instruments monétaires et des médailles", "Code des juridictions financières",
    "Code des pensions civiles et militaires de retraite",
    "Code des pensions de retraite des marins français du commerce, de pêche ou de plaisance",
    "Code des pensions militaires d'invalidité et des victimes de guerre",
    "Code des ports maritimes", "Code des postes et des communications électroniques",
    "Code des procédures civiles d'exécution",
    "Code des relations entre le public et l'administration", "Code des transports",
    "Code disciplinaire et pénal de la marine marchande",
    "Code du cinéma et de l'image animée", "Code du domaine de l'Etat",
    "Code du domaine de l'Etat et des collectivités publiques applicable à la collectivité "
    "territoriale de Mayotte", "Code du domaine public fluvial et de la navigation intérieure",
    "Code du patrimoine", "Code du service national", "Code du sport", "Code du tourisme",
    "Code du travail", "Code du travail maritime", "Code forestier (nouveau)",
    "Code général de la fonction publique",
    "Code général de la propriété des personnes publiques",
    "Code général des collectivités territoriales", "Code général des impôts",
    "Code général des impôts, annexe I", "Code général des impôts, annexe II",
    "Code général des impôts, annexe III", "Code général des impôts, annexe IV", "Code minier",
    "Code minier (nouveau)", "Code monétaire et financier", "Code pénal", "Code pénitentiaire",
    "Code rural (ancien)", "Code rural et de la pêche maritime", "Code électoral",
    "Livre des procédures fiscales",
]

# Un titre écrit seul qui désigne deux codes. « Code minier » tout court vise le plus souvent
# le code de 2011, mais c'est aussi le titre exact de l'ancien, en partie en vigueur. On ne
# choisit pas : on cherche dans les deux et on montre ce qu'on a trouvé.
AMBIGUOUS = {"Code minier": ["Code minier (nouveau)", "Code minier"]}
# Comment nommer chacun dans le rapport, quand le titre de Légifrance ne suffit pas.
LABELS = {"Code minier": "ancien Code minier"}

# Abréviations d'usage : (formes affichées à l'utilisateur, motif reconnu, titre exact).
# Les formes affichées sont ce que l'onglet « Ce qui est vérifié » montre : elles doivent
# correspondre au motif, un test le contrôle.
ABBREVIATIONS = [
    (["C. civ."], r"C\.\s*civ\.?", "Code civil"),
    (["C. com."], r"C\.\s*com\.?", "Code de commerce"),
    (["C. trav."], r"C\.\s*trav\.?", "Code du travail"),
    (["C. consom.", "C. conso."], r"C\.\s*consom\.?|C\.\s*conso\.?", "Code de la consommation"),
    (["CSS", "C. séc. soc."], r"CSS|C\.\s*s[ée]c\.\s*soc\.?", "Code de la sécurité sociale"),
    (["CPC", "C. pr. civ."], r"CPC|C\.\s*pr\.\s*civ\.?", "Code de procédure civile"),
    (["CPP", "C. pr. pén."], r"CPP|C\.\s*pr\.\s*p[ée]n\.?", "Code de procédure pénale"),
    (["C. pén."], r"C\.\s*p[ée]n\.?", "Code pénal"),
    (["CPCE", "C. pr. exéc."], r"CPCE|C\.\s*pr\.\s*ex[ée]c\.?",
     "Code des procédures civiles d'exécution"),
    (["CCH"], r"CCH", "Code de la construction et de l'habitation"),
    (["C. assur."], r"C\.\s*assur\.?", "Code des assurances"),
    (["CMF", "C. mon. fin."], r"CMF|C\.\s*mon\.\s*fin\.?", "Code monétaire et financier"),
    (["CGI"], r"CGI", "Code général des impôts"),
    (["CGCT"], r"CGCT", "Code général des collectivités territoriales"),
    (["CJA"], r"CJA", "Code de justice administrative"),
    (["C. urb."], r"C\.\s*urb\.?", "Code de l'urbanisme"),
    (["C. env."], r"C\.\s*env\.?", "Code de l'environnement"),
    (["CSP"], r"CSP", "Code de la santé publique"),
    (["CASF"], r"CASF", "Code de l'action sociale et des familles"),
    (["CRPA"], r"CRPA", "Code des relations entre le public et l'administration"),
    (["CESEDA"], r"CESEDA", "Code de l'entrée et du séjour des étrangers et du droit d'asile"),
    (["C. rur."], r"C\.\s*rur\.?", "Code rural et de la pêche maritime"),
    (["CPI"], r"CPI", "Code de la propriété intellectuelle"),
    (["COJ"], r"COJ", "Code de l'organisation judiciaire"),
    (["LPF"], r"LPF", "Livre des procédures fiscales"),
    (["C. route"], r"C\.\s*route", "Code de la route"),
    (["C. éduc."], r"C\.\s*[ée]duc\.?", "Code de l'éducation"),
    (["C. transp."], r"C\.\s*transp\.?", "Code des transports"),
    (["CGFP"], r"CGFP", "Code général de la fonction publique"),
]


def abbreviations_of(title):
    return [form for forms, _, t in ABBREVIATIONS if t == title for form in forms]


_ACCENTS = {"e": "[eéèêë]", "a": "[aàâ]", "i": "[iîï]", "o": "[oô]", "u": "[uùûü]",
            "c": "[cç]"}


def _loose(title):
    """Motif tolérant : accents facultatifs, apostrophes droites ou courbes, espaces
    multiples. « Code de la securite sociale » doit être reconnu."""
    out = []
    for ch in title:
        base = {"é": "e", "è": "e", "ê": "e", "à": "a", "â": "a", "î": "i", "ô": "o",
                "ù": "u", "û": "u", "ç": "c"}.get(ch.lower(), ch.lower())
        if ch == " ":
            out.append(r"\s+")
        elif ch in "'’":
            out.append(r"['’]\s*")
        elif base in _ACCENTS:
            out.append(_ACCENTS[base])
        else:
            out.append(re.escape(ch))
    return "".join(out)


def _build():
    global _PATTERNS, RE_CODE
    _PATTERNS = sorted(
        [(_loose(t), t) for t in TITLES] + [(p, t) for _, p, t in ABBREVIATIONS],
        key=lambda p: -len(p[0]))      # le plus long d'abord : « Code de procédure civile »
                                       # avant « Code civil »
    RE_CODE = re.compile(
        "|".join(f"(?P<c{i}>{p})" for i, (p, _) in enumerate(_PATTERNS)), re.I)


_build()


def learn(titles):
    """Ajoute à la reconnaissance les titres que Légifrance connaît et pas nous. Renvoie les
    nouveaux. On n'en retire jamais : un code disparu de Légifrance reste une citation à
    repérer. Les abréviations, elles, ne s'apprennent pas : elles viennent de l'usage."""
    new = sorted(set(titles) - set(TITLES))
    if new:
        TITLES.extend(new)
        _build()
    return new
# Les sigles (CSS, CPC...) ne valent qu'en majuscules et en mot entier.
_ACRONYM = re.compile(r"^[A-Z]{2,7}$")


def find_code(text, last=False):
    """Premier code nommé dans `text` (ou le dernier si `last`) : (titre exact, début, fin),
    ou None."""
    found = None
    for m in RE_CODE.finditer(text):
        i = int(m.lastgroup[1:])
        title = _PATTERNS[i][1]
        found = m.group(0)
        if _ACRONYM.match(found) and found != found.upper():
            continue
        before = text[m.start() - 1] if m.start() else " "
        after = text[m.end()] if m.end() < len(text) else " "
        if _ACRONYM.match(found) and (before.isalnum() or after.isalnum()):
            continue
        found = (title, m.start(), m.end())
        if not last:
            return found
    return found
