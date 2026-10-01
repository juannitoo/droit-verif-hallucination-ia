"""Le PDF annoté : une copie du document où chaque citation vérifiée est surlignée de la
couleur de son verdict, et mène d'un clic à ce qui a été trouvé.

  bleu    confirmé : la décision existe à la date citée, l'article est en vigueur
  orange  à vérifier : autre date, autre chambre, autre version, texte cité non retrouvé...
  rouge   semble inventé : introuvable dans une base qui publie tout
  gris ?  non vérifié : pas de clé, base en panne, période non couverte, à voir à la main

Le document d'origine n'est jamais modifié. Un PDF ne se recompose pas : on ne peut pas y
insérer un signe entre deux mots sans déplacer tout le texte. On pose donc par-dessus des
annotations, comme un surligneur : le texte reste intact, et chaque lecteur de PDF peut les
masquer. Le survol d'un surlignage montre le verdict et son explication.

TROUVER UNE CITATION SUR LA PAGE
  Le texte vérifié vient de pypdf ; les positions des lettres, de pdfminer.six. Les deux
  lisent la même page, mais pas avec les mêmes espaces : on compare sans les espaces. Une
  citation lue sur la page 3 est cherchée sur la page 3, et la n-ième fois qu'elle y figure
  est la n-ième trouvée. Une citation qu'on ne retrouve pas n'est pas annotée, et on le dit.
"""
import io
import logging
import os
import time
import unicodedata

from pypdf import PdfReader, PdfWriter
from pypdf.generic import (ArrayObject, DecodedStreamObject, DictionaryObject, FloatObject,
                           NameObject, NumberObject, TextStringObject)

from . import NAME, report as rep, report_pdf
from .reader import MAX_PAGES, PAGE

# Les couleurs du rapport (report.COLORS), en 0-1 pour le PDF, posées en « produit »
# (Multiply) : le texte noir reste noir.
COLORS = {light: tuple(round(v / 255, 3) for v in rgb) for light, rgb in rep.COLORS.items()}
QUESTION = (0.35, 0.35, 0.35)       # le « ? » des citations non vérifiées

# Un PDF reçu de l'extérieur peut être fait pour occuper le poste : des centaines de milliers
# de tracés, des lettres par millions. Le lecteur (reader.py) a ses plafonds ; ceux-ci sont
# ceux de l'annotation, qui relit les pages à sa façon.
MAX_SECONDS = 60
MAX_LETTERS = 200_000       # par page : une page pleine en compte quelques milliers


class TooHeavy(Exception):
    """Le PDF dépasse ce que l'annotation accepte : rien n'est écrit."""


def squeeze(text):
    """Le texte sans ses espaces, ligatures défaites : ce que pypdf et pdfminer ont en commun."""
    return "".join(unicodedata.normalize("NFKC", text).split())


def anchor(text, start, end):
    """Ce qu'il faut pour retrouver la citation text[start:end] sur sa page : ses mots, et
    combien de fois ils figurent avant elle sur la même page."""
    page_start = text.rfind(PAGE, 0, start) + 1
    words = squeeze(text[start:end])
    return {"text": text[start:end], "nth": squeeze(text[page_start:start]).count(words)}


def output_name(path):
    """« conclusions.pdf » -> « conclusions-citations-vérifiées.pdf »."""
    return path.with_name(f"{path.stem}-citations-vérifiées{path.suffix}")


# Les lettres d'une page, avec leur place

def _inverse(m):
    a, b, c, d, e, f = m
    det = a * d - b * c
    return (d / det, -b / det, -c / det, a / det, (c * f - d * e) / det, (b * e - a * f) / det)


def _apply(m, x, y):
    a, b, c, d, e, f = m
    return a * x + c * y + e, b * x + d * y + f


def _page_ctm(page):
    """La transformation que pdfminer applique à la page (pdfinterp.process_page) : ses
    coordonnées partent du coin de la page, tournée. Les annotations, elles, se placent dans
    l'espace d'origine de la page : on défait cette transformation."""
    x0, y0, x1, y1 = page.mediabox
    return {90: (0, -1, 1, 0, -y0, x1), 180: (-1, 0, 0, -1, x1, y1),
            270: (0, 1, -1, 0, y1, -x0)}.get(page.rotate % 360, (1, 0, 0, 1, -x0, -y0))


def _device(manager, deadline):
    """Le lecteur de lettres de pdfminer, sans les tracés ni les images (on n'en a pas
    besoin) et qui s'arrête au-delà des plafonds."""
    from pdfminer.converter import PDFPageAggregator

    class Letters(PDFPageAggregator):
        count = 0

        def _check(self):
            if time.monotonic() > deadline:
                raise TooHeavy(f"plus de {MAX_SECONDS} secondes pour relire ce PDF")
            if self.count > MAX_LETTERS:
                raise TooHeavy(f"plus de {MAX_LETTERS:_} lettres sur une page".replace("_", " "))

        def begin_page(self, *args, **kw):
            self.count = 0
            super().begin_page(*args, **kw)

        def render_char(self, *args, **kw):
            self.count += 1
            self._check()
            return super().render_char(*args, **kw)

        def paint_path(self, *args, **kw):
            self._check()

        def render_image(self, *args, **kw):
            self._check()

    return Letters(manager, laparams=None)


def _letters(path, wanted, deadline):
    """{numéro de page (1...): [(lettre, x0, y0, x1, y1)]} pour les pages voulues, dans
    l'ordre où la page les écrit, en coordonnées de la page."""
    from pdfminer.layout import LTChar
    from pdfminer.pdfinterp import PDFPageInterpreter, PDFResourceManager
    from pdfminer.pdfpage import PDFPage

    # pdfminer signale en journal ce qui lui manque dans les polices du document (« Could not
    # get FontBBox ») : sans effet sur la place des lettres, et du bruit pour l'utilisateur.
    logging.getLogger("pdfminer").setLevel(logging.ERROR)
    manager = PDFResourceManager()
    device = _device(manager, deadline)
    interpreter = PDFPageInterpreter(manager, device)
    out = {}
    with open(path, "rb") as f:
        for n, page in enumerate(PDFPage.get_pages(f), 1):
            if n > MAX_PAGES or n > max(wanted, default=0):
                break
            if n not in wanted:
                continue
            interpreter.process_page(page)
            back = _inverse(_page_ctm(page))
            letters = []

            def walk(item):
                if isinstance(item, LTChar):
                    for ch in squeeze(item.get_text()):
                        xa, ya = _apply(back, item.x0, item.y0)
                        xb, yb = _apply(back, item.x1, item.y1)
                        letters.append((ch, min(xa, xb), min(ya, yb), max(xa, xb),
                                        max(ya, yb)))
                else:
                    for child in getattr(item, "_objs", ()) or ():
                        walk(child)
            walk(device.get_result())
            out[n] = letters
    return out


def _lines(boxes):
    """Les boîtes des lettres d'une citation, regroupées par ligne : un rectangle par ligne."""
    rects = []
    for x0, y0, x1, y1 in boxes:
        if rects:
            r = rects[-1]
            same_line = abs(y0 - r[1]) < 0.5 * (r[3] - r[1]) and x0 >= r[0] - 1
            if same_line:
                rects[-1] = [min(r[0], x0), min(r[1], y0), max(r[2], x1), max(r[3], y1)]
                continue
        rects.append([x0, y0, x1, y1])
    return rects


def find(letters, words, nth):
    """Les rectangles, un par ligne, de la n-ième occurrence de `words` ; None si absente."""
    flat = "".join(ch for ch, *_ in letters)
    at = -1
    for _ in range(nth + 1):
        at = flat.find(words, at + 1)
        if at < 0:
            return None
    return _lines([box for _, *box in letters[at:at + len(words)]])


# Les annotations

def _num(v):
    return FloatObject(round(v, 2))


def _appearance(writer, rects, color, question):
    """L'aspect du surlignage, dessiné une fois pour toutes : un lecteur qui ne sait pas
    dessiner une annotation (beaucoup ne savent pas) affiche celui-ci."""
    x0 = min(r[0] for r in rects)
    y0 = min(r[1] for r in rects)
    x1 = max(r[2] for r in rects)
    y1 = max(r[3] for r in rects)
    ops = ["/Surligneur gs", "{:.3f} {:.3f} {:.3f} rg".format(*color)]
    ops += [f"{r[0]:.2f} {r[1]:.2f} {r[2] - r[0]:.2f} {r[3] - r[1]:.2f} re f" for r in rects]
    if question:
        # Un « ? » en exposant, après la fin de la citation, comme un appel de note : assez
        # haut pour passer au-dessus d'une parenthèse ou d'une virgule qui suit.
        last = rects[-1]
        size = 0.55 * (last[3] - last[1])
        qx, qy = last[2] + 0.8, last[1] + 0.8 * (last[3] - last[1])
        ops += ["/Normal gs", "BT", "{:.3f} {:.3f} {:.3f} rg".format(*QUESTION),
                f"/Helv {size:.2f} Tf", f"{qx:.2f} {qy:.2f} Td", "(?) Tj", "ET"]
        x1 = max(x1, qx + size * 0.6)
        y1 = max(y1, qy + size)
    stream = DecodedStreamObject()
    stream.set_data("\n".join(ops).encode("ascii"))
    stream.update({
        NameObject("/Type"): NameObject("/XObject"),
        NameObject("/Subtype"): NameObject("/Form"),
        NameObject("/BBox"): ArrayObject([_num(x0), _num(y0), _num(x1), _num(y1)]),
        NameObject("/Resources"): DictionaryObject({
            NameObject("/ExtGState"): DictionaryObject({
                NameObject("/Surligneur"): DictionaryObject({
                    NameObject("/Type"): NameObject("/ExtGState"),
                    NameObject("/BM"): NameObject("/Multiply")}),
                NameObject("/Normal"): DictionaryObject({
                    NameObject("/Type"): NameObject("/ExtGState"),
                    NameObject("/BM"): NameObject("/Normal")})}),
            NameObject("/Font"): DictionaryObject({
                NameObject("/Helv"): DictionaryObject({
                    NameObject("/Type"): NameObject("/Font"),
                    NameObject("/Subtype"): NameObject("/Type1"),
                    NameObject("/BaseFont"): NameObject("/Helvetica")})})}),
    })
    return writer._add_object(stream), [x0, y0, x1, y1]


def _highlight(writer, rects, color, note, question):
    ap, box = _appearance(writer, rects, color, question)
    quads = []
    for x0, y0, x1, y1 in rects:
        quads += [x0, y1, x1, y1, x0, y0, x1, y0]
    return DictionaryObject({
        NameObject("/Type"): NameObject("/Annot"),
        NameObject("/Subtype"): NameObject("/Highlight"),
        NameObject("/Rect"): ArrayObject([_num(v) for v in box]),
        NameObject("/QuadPoints"): ArrayObject([_num(v) for v in quads]),
        NameObject("/C"): ArrayObject([_num(v) for v in color]),
        NameObject("/F"): NumberObject(4),                 # imprimée avec la page
        NameObject("/T"): TextStringObject(NAME),
        NameObject("/Contents"): TextStringObject(note),
        NameObject("/AP"): DictionaryObject({NameObject("/N"): ap}),
    })


def _link(rect, url):
    return DictionaryObject({
        NameObject("/Type"): NameObject("/Annot"),
        NameObject("/Subtype"): NameObject("/Link"),
        NameObject("/Rect"): ArrayObject([_num(v) for v in rect]),
        NameObject("/Border"): ArrayObject([NumberObject(0)] * 3),
        NameObject("/F"): NumberObject(4),
        NameObject("/A"): DictionaryObject({
            NameObject("/S"): NameObject("/URI"),
            NameObject("/URI"): TextStringObject(url)}),
    })


# La copie ne reprend de la pièce que ses pages, avec leurs commentaires et leurs liens
# ordinaires. Le reste agit sans qu'on le voie (JavaScript, action à l'ouverture, lancement
# d'un programme, fichier joint, formulaire) ou dit qui l'a écrit (auteur, titre, XMP) : la
# copie annotée se transmet, cela ne doit pas partir avec elle. Les signets ne sont pas
# repris non plus : un signet peut porter une action.
_QUIET_ANNOTS = {"/Text", "/Highlight", "/Underline", "/StrikeOut", "/Squiggly", "/FreeText",
                 "/Square", "/Circle", "/Line", "/Polygon", "/PolyLine", "/Ink", "/Stamp",
                 "/Caret", "/Popup", "/Link"}


def _harmless(action):
    """Une action qui ne fait qu'aller à une page du document, ou ouvrir une page web."""
    action = action.get_object() if action is not None else None
    if not isinstance(action, DictionaryObject) or "/Next" in action:
        return False
    if action.get("/S") == "/GoTo":
        return True
    return action.get("/S") == "/URI" and str(action.get("/URI", "")).lower().startswith(
        ("https://", "http://"))


def _disarm(page):
    """La page, sans ses actions ni ses annotations actives."""
    page.pop(NameObject("/AA"), None)
    if "/Annots" not in page:
        return
    kept = ArrayObject()
    for a in page["/Annots"] or []:
        annot = a.get_object()
        if not isinstance(annot, DictionaryObject) or annot.get("/Subtype") not in _QUIET_ANNOTS:
            continue
        annot.pop(NameObject("/AA"), None)
        if "/A" in annot and not _harmless(annot["/A"]):
            continue
        kept.append(a)
    page[NameObject("/Annots")] = kept


def _copy(reader):
    """Un document neuf fait des seules pages de la pièce : rien de son catalogue (action à
    l'ouverture, JavaScript, fichiers joints, formulaire, métadonnées) ne le suit."""
    writer = PdfWriter()
    for page in reader.pages:
        # Désarmée avant d'être copiée : ce qui est copié s'écrit, même retiré après.
        # (Seule la page lue en mémoire change, jamais le fichier d'origine.)
        _disarm(page)
        writer.add_page(page)
    writer.add_metadata({"/Producer": NAME})
    return writer


def _note(r):
    note = f"{rep.citation_label(r)}\n{r['verdict_label']} : {r['explanation']}"
    return note + (f"\n{r['link']}" if r.get("link") else "")


def annotate(source, target, report):
    """Écrit dans `target` la copie annotée de `source`. `report` : le rapport complet, avec
    ses extraits (ce sont eux qui disent où est chaque citation). Renvoie le nombre de
    places annotées (une citation reprise trois fois en compte trois) et celui des places
    qu'on n'a pas retrouvées sur leur page."""
    places, missed = [], 0
    for r in report["citations"]:
        loc = r.get("location") or {}
        if not (loc.get("page_exact") and loc.get("text")):
            missed += 1         # dans les notes d'un Word, ou rapport sans extraits
            continue
        # La citation, et ses reprises plus loin dans le document, sous le même verdict.
        places += [(p["page"], p, r) for p in [loc] + loc.get("repeats", []) if p.get("page")]
    letters = _letters(source, {page for page, _, _ in places},
                       time.monotonic() + MAX_SECONDS)
    reader = PdfReader(source)
    if reader.is_encrypted:
        reader.decrypt("")      # un PDF protégé contre la modification seulement
    writer = _copy(reader)
    placed = 0
    for page, where, r in places:
        rects = find(letters.get(page, []), squeeze(where["text"]), where.get("nth", 0))
        if not rects:
            missed += 1
            continue
        light = rep.light(r["verdict"])
        writer.add_annotation(page - 1, _highlight(
            writer, rects, COLORS[light], _note(r), light == rep.UNCHECKED))
        if rep.safe_link(r.get("link")):
            for rect in rects:
                writer.add_annotation(page - 1, _link(rect, r["link"]))
        placed += 1
    # En tête, une page de notice : comment lire les couleurs, et ce que le bleu ne dit pas.
    # Ajoutée à la fin : les annotations ci-dessus visent les pages du document par leur rang.
    first = writer.pages[0]
    page = PdfReader(io.BytesIO(report_pdf.notice(
        report, float(first.mediabox.width), float(first.mediabox.height)))).pages[0]
    writer.insert_page(page, 0)
    # D'abord à côté, puis à sa place : un arrêt en cours d'écriture (fenêtre fermée, disque
    # plein) ne laisse pas un PDF tronqué sous le nom choisi.
    partial = f"{target}.partiel"
    try:
        with open(partial, "wb") as f:
            writer.write(f)
        os.replace(partial, target)
    finally:
        if os.path.exists(partial):
            os.remove(partial)
    return placed, missed
