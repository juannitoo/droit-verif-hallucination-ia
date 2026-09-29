"""Plain text of a document, whatever its format.

FORMATS
  .txt .md       read as is
  .docx          Word, and Google Docs exported as Word      (standard library)
  .odt           LibreOffice, OpenOffice                     (standard library)
  .pdf           pypdf if installed, otherwise pdftotext     (poppler)

  Apple Pages (.pages) and old Word (.doc) are not read: export them to PDF or .docx.

WHAT IT NEVER DOES
  Return empty text silently. A scanned PDF (an image, no text) raises an error instead of
  producing "no citation found": that would be a hole disguised as a result.

Footnotes are read too: that is where legal briefs put their citations.
"""
import re
import shutil
import subprocess
import unicodedata
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

from .locales import t

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
T = "{urn:oasis:names:tc:opendocument:xmlns:text:1.0}"


class Unreadable(Exception):
    """The document cannot be read. The message says what to do."""


def _docx(path):
    with zipfile.ZipFile(path) as z:
        parts = ["word/document.xml", "word/footnotes.xml", "word/endnotes.xml"]
        xmls = [z.read(p) for p in parts if p in z.namelist()]
    blocks = []
    for x in xmls:
        for p in ET.fromstring(x).iter(W + "p"):
            pieces = []
            for e in p.iter():
                if e.tag == W + "t":
                    pieces.append(e.text or "")
                elif e.tag == W + "tab":
                    pieces.append("\t")
                elif e.tag in (W + "br", W + "cr"):
                    pieces.append("\n")
            blocks.append("".join(pieces))
    return "\n".join(blocks)


def _odt_text(e):
    """Text of an ODT node. Repeated spaces are encoded as <text:s text:c="3"/>."""
    pieces = [e.text or ""]
    for f in e:
        if f.tag == T + "s":
            pieces.append(" " * int(f.get(T + "c", "1")))
        elif f.tag == T + "tab":
            pieces.append("\t")
        elif f.tag == T + "line-break":
            pieces.append("\n")
        else:
            pieces.append(_odt_text(f))
        pieces.append(f.tail or "")
    return "".join(pieces)


def _odt(path):
    with zipfile.ZipFile(path) as z:
        root = ET.fromstring(z.read("content.xml"))

    # Notes sit INSIDE the paragraph that calls them: read them in place, and do not descend
    # into a paragraph again, or every note would come out twice.
    def paragraphs(e):
        if e.tag in (T + "p", T + "h"):
            yield e
        else:
            for f in e:
                yield from paragraphs(f)
    return "\n".join(_odt_text(p) for p in paragraphs(root))


def _pdf(path):
    try:
        from pypdf import PdfReader
        return "\n".join((pg.extract_text() or "") for pg in PdfReader(path).pages)
    except ImportError:
        pass
    if shutil.which("pdftotext"):
        r = subprocess.run(["pdftotext", "-layout", str(path), "-"],
                           capture_output=True, text=True)
        if r.returncode == 0:
            return r.stdout
        raise Unreadable(t.PDF_FAILED.format(detail=r.stderr.strip()[:200]))
    raise Unreadable(t.PDF_NO_READER)


def _normalize(text):
    # NFKC undoes PDF ligatures and non-breaking spaces.
    text = unicodedata.normalize("NFKC", text)
    # A case number split at a line end by a PDF: "17-\n28.268".
    return re.sub(r"(\d)-[ \t]*\n\s*(\d)", r"\1-\2", text)


READERS = {".docx": _docx, ".odt": _odt, ".pdf": _pdf}
TO_EXPORT = {".pages": "Apple Pages", ".doc": "Word 97-2003", ".gdoc": "Google Docs",
             ".rtf": "RTF", ".wps": "Works"}


def text_of(path):
    path = Path(path)
    ext = path.suffix.lower()
    if ext in TO_EXPORT:
        raise Unreadable(t.EXPORT_FIRST.format(name=path.name, fmt=TO_EXPORT[ext]))
    try:
        raw = READERS[ext](path) if ext in READERS else path.read_text(encoding="utf-8")
    except (zipfile.BadZipFile, ET.ParseError, KeyError) as e:
        raise Unreadable(t.DAMAGED.format(name=path.name, ext=ext, detail=e))
    except UnicodeDecodeError:
        raise Unreadable(t.UNKNOWN_FORMAT.format(name=path.name))
    text = _normalize(raw)
    if len(text.split()) < 5:
        raise Unreadable(t.NO_TEXT_PDF.format(name=path.name) if ext == ".pdf"
                         else t.NO_TEXT.format(name=path.name))
    return text
