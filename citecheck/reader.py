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

PAGES
  Page breaks are kept as "\f" in the text, so a citation can be located. PDF pages are
  exact. Word and LibreOffice store the page breaks of their last rendering: pages there
  are approximate. Word footnotes come after the body, after a NOTES mark: their page is
  unknown. Plain text has no pages.
"""
import os
import re
import shutil
import subprocess
import unicodedata
import zipfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from .locales import t

MAX_UNPACKED = 200 * 1024 * 1024   # a .docx or .odt part larger than this is refused:
                                   # a crafted "zip bomb" would otherwise fill the memory
# The limits above bound what is unpacked, not what is built from it. These bound the rest
# (audit of 30/09/2026, point 2): a 280-byte .odt asking for 300 million spaces took 600 MB.
MAX_TEXT = 10_000_000     # characters of extracted text: some 3,000 pages of conclusions
MAX_PAGES = 3_000         # pages of a PDF: each one costs pypdf time and memory
MAX_SPACES = 100          # <text:s text:c="n"/> is a run of spaces, never a page of them
PDFTOTEXT_TIMEOUT = 120   # seconds
PAGE = "\f"
NOTES = "\x1e"      # separates the body of a Word document from its footnotes

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
T = "{urn:oasis:names:tc:opendocument:xmlns:text:1.0}"


class Unreadable(Exception):
    """The document cannot be read. The message says what to do."""


class Suspicious(ValueError):
    """The file has a structure no word processor writes: refused rather than read."""


class _NoDTD(ET.TreeBuilder):
    def doctype(self, name, pubid, system):
        raise Suspicious("DTD")


def parse_xml(data):
    """ElementTree, with any DTD refused before it is used. Word, LibreOffice and CELLAR
    never send one; a DTD is what declares the entities of a "billion laughs" or of an
    external file, and how Python treats them depends on the expat it was built with."""
    parser = ET.XMLParser(target=_NoDTD())
    parser.feed(data)
    return parser.close()


@dataclass
class Document:
    text: str
    pages: str | None      # "exact", "approximate", or None when the format has no pages

    def locate(self, offset):
        """(page, in_notes) for a position in the text. page is None if unknown."""
        notes = self.text.find(NOTES)
        if notes != -1 and offset > notes:
            return None, True
        if not self.pages:
            return None, False
        return self.text.count(PAGE, 0, offset) + 1, False

    def excerpt(self, start, end, margin=60):
        a, b = max(0, start - margin), min(len(self.text), end + margin)
        body = " ".join(self.text[a:b].replace(PAGE, " ").replace(NOTES, " ").split())
        return ("…" if a else "") + body + ("…" if b < len(self.text) else "")


def _check_size(z, names):
    for name in names:
        if name in z.namelist() and z.getinfo(name).file_size > MAX_UNPACKED:
            raise Unreadable(t.TOO_BIG.format(name=name))


def _docx(path):
    with zipfile.ZipFile(path) as z:
        _check_size(z, ["word/document.xml", "word/footnotes.xml", "word/endnotes.xml"])
        parts = ["word/document.xml", "word/footnotes.xml", "word/endnotes.xml"]
        xmls = [z.read(p) for p in parts if p in z.namelist()]
    blocks = []
    for n, x in enumerate(xmls):
        if n == 1:
            blocks.append(NOTES)
        for p in parse_xml(x).iter(W + "p"):
            pieces = []
            for e in p.iter():
                if e.tag == W + "t":
                    pieces.append(e.text or "")
                elif e.tag == W + "tab":
                    pieces.append("\t")
                elif e.tag == W + "lastRenderedPageBreak":
                    pieces.append(PAGE)
                elif e.tag == W + "br" and e.get(W + "type") == "page":
                    pieces.append(PAGE)
                elif e.tag in (W + "br", W + "cr"):
                    pieces.append("\n")
            blocks.append("".join(pieces))
    return "\n".join(blocks)


def _odt_text(e):
    """Text of an ODT node. Repeated spaces are encoded as <text:s text:c="3"/>."""
    pieces = [e.text or ""]
    for f in e:
        if f.tag == T + "s":
            count = f.get(T + "c", "1")
            if not (count.isascii() and count.isdigit() and len(count) <= 9):
                raise Suspicious(f"text:c={count[:20]!r}")
            pieces.append(" " * min(int(count), MAX_SPACES))
        elif f.tag == T + "tab":
            pieces.append("\t")
        elif f.tag == T + "line-break":
            pieces.append("\n")
        elif f.tag == T + "soft-page-break":
            pieces.append(PAGE)
        else:
            pieces.append(_odt_text(f))
        pieces.append(f.tail or "")
    return "".join(pieces)


def _odt(path):
    with zipfile.ZipFile(path) as z:
        _check_size(z, ["content.xml"])
        root = parse_xml(z.read("content.xml"))

    # Notes sit INSIDE the paragraph that calls them: read them in place, and do not descend
    # into a paragraph again, or every note would come out twice.
    def paragraphs(e):
        if e.tag in (T + "p", T + "h"):
            yield e
        elif e.tag == T + "soft-page-break":       # a break between two paragraphs
            yield None
        else:
            for f in e:
                yield from paragraphs(f)
    return "\n".join(PAGE if p is None else _odt_text(p) for p in paragraphs(root))


def _pdf(path):
    try:
        from pypdf import PdfReader
    except ImportError:
        return _pdftotext(path)
    try:
        pages = PdfReader(path).pages
        if len(pages) > MAX_PAGES:
            raise Unreadable(t.TOO_MANY_PAGES.format(name=path.name, n=len(pages),
                                                     max=MAX_PAGES))
        texts, size = [], 0
        for pg in pages:
            texts.append(pg.extract_text() or "")
            size += len(texts[-1])
            if size > MAX_TEXT:
                raise Unreadable(t.TOO_LONG.format(name=path.name))
        return PAGE.join(texts)
    except (Unreadable, RecursionError):
        raise
    except Exception as e:        # pypdf has many error types; all mean a damaged PDF
        raise Unreadable(t.DAMAGED.format(name=path.name, ext=".pdf", detail=type(e).__name__))


# What pdftotext inherits: enough to run, nothing else. The access keys may be environment
# variables, and a program found in the PATH has no business seeing them.
CHILD_ENV = {"PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "HOME", "LANG", "LC_ALL",
             "LC_CTYPE"}


def _pdftotext(path):
    exe = shutil.which("pdftotext")
    if not exe:
        raise Unreadable(t.PDF_NO_READER)
    env = {k: v for k, v in os.environ.items() if k.upper() in CHILD_ENV}
    try:
        r = subprocess.run([exe, "-layout", str(path), "-"], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", env=env,
                           timeout=PDFTOTEXT_TIMEOUT)
    except subprocess.TimeoutExpired:
        raise Unreadable(t.PDF_FAILED.format(detail=f"> {PDFTOTEXT_TIMEOUT} s"))
    if r.returncode == 0:
        return r.stdout
    raise Unreadable(t.PDF_FAILED.format(detail=r.stderr.strip()[:200]))


def _normalize(text):
    # NFKC undoes PDF ligatures and non-breaking spaces.
    text = unicodedata.normalize("NFKC", text)
    # A case number split at a line end by a PDF: "17-\n28.268".
    return re.sub(r"(\d)-[ \t]*\n\s*(\d)", r"\1-\2", text)


READERS = {".docx": _docx, ".odt": _odt, ".pdf": _pdf}
PAGES = {".pdf": "exact", ".docx": "approximate", ".odt": "approximate"}
TO_EXPORT = {".pages": "Apple Pages", ".doc": "Word 97-2003", ".gdoc": "Google Docs",
             ".rtf": "RTF", ".wps": "Works"}


def read(path):
    """The document's text, with its page breaks kept. Raises Unreadable."""
    path = Path(path)
    text = text_of(path)
    pages = PAGES.get(path.suffix.lower())
    if pages == "approximate" and PAGE not in text:
        pages = None        # no break recorded: better no page than a wrong "page 1"
    return Document(text, pages)


def text_of(path):
    path = Path(path)
    ext = path.suffix.lower()
    if ext in TO_EXPORT:
        raise Unreadable(t.EXPORT_FIRST.format(name=path.name, fmt=TO_EXPORT[ext]))
    if ext not in READERS and path.stat().st_size > 4 * MAX_TEXT:   # utf-8: 4 bytes at most
        raise Unreadable(t.TOO_LONG.format(name=path.name))
    try:
        raw = READERS[ext](path) if ext in READERS else path.read_text(encoding="utf-8")
    except Suspicious as e:
        raise Unreadable(t.SUSPICIOUS.format(name=path.name, detail=e))
    except (zipfile.BadZipFile, ET.ParseError, KeyError) as e:
        raise Unreadable(t.DAMAGED.format(name=path.name, ext=ext, detail=e))
    except RecursionError:
        raise Unreadable(t.TOO_DEEP.format(name=path.name))
    except UnicodeDecodeError:
        raise Unreadable(t.UNKNOWN_FORMAT.format(name=path.name))
    if len(raw) > MAX_TEXT:
        raise Unreadable(t.TOO_LONG.format(name=path.name))
    text = _normalize(raw)
    if len(text.split()) < 5:
        raise Unreadable(t.NO_TEXT_PDF.format(name=path.name) if ext == ".pdf"
                         else t.NO_TEXT.format(name=path.name))
    return text
