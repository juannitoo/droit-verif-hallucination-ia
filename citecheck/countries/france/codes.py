"""Reconnaître le nom d'un code dans un texte, en toutes lettres ou abrégé.

Les titres exacts sont ceux de Légifrance (/list/code, relevés le 29/09/2026) : les 76 codes
qu'elle donne en vigueur, sans exception, anciens codes presque vides compris (Code des
communes, Code rural (ancien)...) : une IA qui les cite est justement ce qu'on veut voir. Les
abréviations sont celles de l'usage (C. trav., CSS, CPC...). Une abréviation ambiguë n'est
pas reconnue plutôt que d'être devinée : « CT » ou « CP » ne désignent rien de sûr.

LES CODES ABROGÉS (point C de l'audit du 30/09/2026)
  Légifrance les liste à part : 32 codes, avec leur date d'abrogation. Une IA a appris
  l'ancien droit et les cite volontiers (« article 28 du Code des marchés publics », « article
  405 du Code pénal »). Sans eux, le programme répondait « article cité sans code reconnu »,
  ou « ne semble pas exister » dans le code actuel : deux réponses fausses. Reconnus, leurs
  articles sortent « plus en vigueur, abrogé le ... ».
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

# Les codes abrogés, titres exacts de Légifrance (/list/code, état ABROGE, 29/09/2026), avec
# la date de fin du code. La date qui compte pour un article reste celle de SES versions.
ABROGATED = {
    "Code de commerce (ancien)": "2000-09-21",
    "Code de déontologie de la police nationale": "2014-01-01",
    "Code de déontologie de la profession de commissaire aux comptes": "2007-03-27",
    "Code de déontologie des agents de police municipale": "2014-01-01",
    "Code de déontologie des chirurgiens-dentistes": "2004-08-08",
    "Code de déontologie des médecins": "1995-09-08",
    "Code de déontologie des professionnels de l'expertise comptable": "2012-04-01",
    "Code de déontologie des sages-femmes": "2004-08-08",
    "Code de déontologie médicale": "2004-08-08",
    "Code de déontologie vétérinaire": "2003-08-07",
    "Code de justice militaire": "2007-05-12",
    "Code de l'Office national interprofessionnel du blé": "2003-09-06",
    "Code de l'enseignement technique": "2000-06-22",
    "Code de l'industrie cinématographique": "2010-06-14",
    "Code de la consommation des boissons et des mesures contre l'alcoolisme applicable dans "
    "la collectivité territoriale de Mayotte": "2000-06-22",
    "Code de la nationalité française": "1994-01-01",
    "Code de la route (ancien)": "2001-06-01",
    "Code de procédure civile (1807)": "2007-12-22",
    "Code des caisses d'épargne": "2005-08-25",
    "Code des douanes de Mayotte": "2026-05-01",
    "Code des débits de boissons et des mesures contre l'alcoolisme": "2003-05-27",
    "Code des marchés publics (édition 1964)": "2002-01-01",
    "Code des marchés publics (édition 2001)": "2004-06-01",
    "Code des marchés publics (édition 2004)": "2006-09-01",
    "Code des marchés publics (édition 2006)": "2016-04-01",
    "Code des tribunaux administratifs et des cours administratives d'appel": "2001-01-01",
    "Code du blé": "2006-05-26",
    "Code du travail applicable à Mayotte": "2020-01-01",
    "Code du vin": "2003-09-06",
    "Code forestier": "2012-07-01",
    "Code forestier de Mayotte": "2016-01-01",
    "Code pénal (ancien)": "1994-03-01",
}

# Un titre écrit seul qui désigne deux codes EN VIGUEUR. « Code minier » tout court vise le
# plus souvent le code de 2011, mais c'est aussi le titre exact de l'ancien, en partie en
# vigueur. On ne choisit pas : on cherche dans les deux et on montre ce qu'on a trouvé.
AMBIGUOUS = {"Code minier": ["Code minier (nouveau)", "Code minier"]}

# Un titre écrit seul qui désigne un code ET ses éditions abrogées, de la plus récente à la
# plus ancienne. On cherche dans l'ordre et on s'arrête au premier code où l'article est en
# vigueur à la date de référence : c'est celui que le texte applique, sans bruit. Sinon, on
# montre ce que les anciens contiennent.
#   « Code forestier » et « Code de justice militaire » sont sur Légifrance les titres
#   exacts des codes ABROGÉS ; l'usage les emploie pour les nouveaux, qui s'appellent
#   « (nouveau) ». Les prendre à la lettre ferait dire « abrogé » d'un article en vigueur.
#   « Code rural » : l'actuel s'appelle « Code rural et de la pêche maritime » depuis 2010.
SUCCESSION = {
    "Code forestier": ["Code forestier (nouveau)", "Code forestier"],
    "Code de justice militaire": ["Code de justice militaire (nouveau)",
                                  "Code de justice militaire"],
    "Code pénal": ["Code pénal", "Code pénal (ancien)"],
    "Code de commerce": ["Code de commerce", "Code de commerce (ancien)"],
    "Code de procédure civile": ["Code de procédure civile", "Code de procédure civile (1807)"],
    "Code de la route": ["Code de la route", "Code de la route (ancien)"],
    "Code rural": ["Code rural et de la pêche maritime", "Code rural (ancien)"],
    "Code des marchés publics": [f"Code des marchés publics (édition {y})"
                                 for y in (2006, 2004, 2001, 1964)],
}
# Formes d'usage qui ne sont le titre d'aucun code : (motif, clé de SUCCESSION ou titre).
ALIASES = [
    (r"Code\s+des\s+march[ée]s\s+publics", "Code des marchés publics"),
    (r"Code\s+rural", "Code rural"),
    (r"ancien\s+Code\s+p[ée]nal", "Code pénal (ancien)"),
    (r"ancien\s+Code\s+de\s+commerce", "Code de commerce (ancien)"),
    (r"ancien\s+Code\s+de\s+proc[ée]dure\s+civile", "Code de procédure civile (1807)"),
    (r"ancien\s+Code\s+de\s+la\s+route", "Code de la route (ancien)"),
    (r"ancien\s+Code\s+forestier", "Code forestier"),
    (r"ancien\s+Code\s+rural", "Code rural (ancien)"),
    (r"ancien\s+Code\s+de\s+justice\s+militaire", "Code de justice militaire"),
] + [
    # Les annexes du CGI (point E) : « de l'annexe III au CGI », « CGI, ann. III ». Sans
    # elles, l'article était attribué au CGI lui-même.
    (rf"ann(?:exe|\.)\s+{roman}\b\s*,?\s*(?:au|du|à\s+la|de\s+la)?\s*"
     rf"(?:CGI|Code\s+g[ée]n[ée]ral\s+des\s+imp[ôo]ts)|(?:CGI|Code\s+g[ée]n[ée]ral\s+des\s+"
     rf"imp[ôo]ts)\s*,?\s*ann(?:exe|\.)\s+{roman}\b", f"Code général des impôts, annexe {roman}")
    for roman in ("IV", "III", "II", "I")
]
# Comment nommer chacun dans le rapport, quand le titre de Légifrance ne suffit pas.
LABELS = {"Code minier": "ancien Code minier", "Code forestier": "ancien Code forestier",
          "Code de justice militaire": "ancien Code de justice militaire"}

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
        [(_loose(t), t) for t in TITLES + list(ABROGATED)]
        + [(p, t) for _, p, t in ABBREVIATIONS] + ALIASES,
        key=lambda p: -len(p[0]))      # le plus long d'abord : « Code de procédure civile »
                                       # avant « Code civil »
    RE_CODE = re.compile(
        "|".join(f"(?P<c{i}>{p})" for i, (p, _) in enumerate(_PATTERNS)), re.I)


_build()


def learn(titles):
    """Ajoute à la reconnaissance les titres que Légifrance connaît et pas nous. Renvoie les
    nouveaux. On n'en retire jamais : un code disparu de Légifrance reste une citation à
    repérer. Les abréviations, elles, ne s'apprennent pas : elles viennent de l'usage."""
    # Un titre de code s'écrit « Code ... » (ou « Livre des procédures fiscales »), sur une
    # ligne. Une liste usurpée qui ferait apprendre « de » ferait lire « article 1240 de la
    # demande » comme une citation de code (audit du 01/10/2026).
    titles = {t for t in titles if isinstance(t, str) and len(t) <= 150
              and re.fullmatch(r"(?:Code|Livre)\s[^\x00-\x1f\x7f-\x9f  ]{3,}", t)}
    new = sorted(titles - set(TITLES) - set(ABROGATED))
    if new:
        TITLES.extend(new)
        _build()
    return new
# Les sigles (CSS, CPC, cpce...) ne valent qu'en mot entier : « cssct » n'est pas le Code de
# la sécurité sociale (audit du 02/10/2026).
_ACRONYM = re.compile(r"^[A-Za-z]{2,7}$")


def find_code(text, last=False):
    """Premier code nommé dans `text` (ou le dernier si `last`) : (titre exact, début, fin),
    ou None."""
    found = None
    for found in find_codes(text):
        if not last:
            return found
    return found


def find_codes(text):
    """Tous les codes nommés dans `text`, dans l'ordre : (titre exact, début, fin)."""
    for m in RE_CODE.finditer(text):
        i = int(m.lastgroup[1:])
        title = _PATTERNS[i][1]
        word = m.group(0)
        before = text[m.start() - 1] if m.start() else " "
        after = text[m.end()] if m.end() < len(text) else " "
        if _ACRONYM.match(word) and (before.isalnum() or after.isalnum()):
            continue
        yield title, m.start(), m.end()
