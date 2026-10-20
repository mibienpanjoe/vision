"""Bounded EPUB container validation and XHTML spine extraction.

The container is checked (paths, entry count, expansion, encryption) before any
document is parsed. XHTML is read with network access and DTD loading disabled;
stylesheets, scripts, images and links are never loaded. Spans index this
revision's canonical text: headings and passages joined by blank lines.
"""

import posixpath
import re
import zipfile
from dataclasses import dataclass
from io import BytesIO
from urllib.parse import unquote, urlsplit

from app.core.errors import PublicError
from app.services.ingestion.text_adapter import (
    CHAPTER,
    MAX_CODEPOINTS,
    MAX_PASSAGE,
    MAX_PASSAGES,
    ParsedChapter,
    ParsedPassage,
    ParsedText,
)
from defusedxml import DefusedXmlException
from defusedxml.ElementTree import fromstring as parse_xml
from lxml import html

EPUB_REVISION = "epub-xhtml-v1"
NORMALIZATION = "html-space-v1"
MAX_ENTRIES = 2000
MAX_ENTRY = 16 * 1024 * 1024
MAX_EXPANDED = 64 * 1024 * 1024
SEPARATOR = "\n\n"
CONTAINER_NS = "{urn:oasis:names:tc:opendocument:xmlns:container}"
OPF_NS = "{http://www.idpf.org/2007/opf}"
XHTML_TYPES = {"application/xhtml+xml", "text/html"}
HEADINGS = {"h1", "h2", "h3", "h4", "h5", "h6"}
BLOCKS = HEADINGS | {"p", "li", "blockquote", "pre", "dd", "dt", "figcaption", "td", "th", "caption",
                     "div", "section", "article", "aside", "header", "footer", "main"}
REMOVED = ("script", "style", "head", "nav", "template", "noscript")
MEDIA = ("img", "svg", "video", "audio", "object", "embed", "iframe", "math")
BREAK = ""
DECLARATION = re.compile(r"^\s*<\?xml[^>]*\?>")
# HTML whitespace only: a no-break space is content, not layout.
SPACE = re.compile(r"[ \t\n\r\f]+")


@dataclass(frozen=True)
class ParsedEpub:
    parsed: ParsedText
    text: str


def invalid():
    return PublicError(422, "INVALID_SOURCE", "Source is not a readable EPUB.")


def unsafe():
    return PublicError(422, "EPUB_UNSAFE_PATH", "EPUB contains an unsafe path.")


def limited():
    return PublicError(422, "PARSER_LIMIT", "Source exceeds the EPUB expansion budget.")


def safe_name(name):
    parts = name.split("/")
    return (bool(name) and "\\" not in name and "\x00" not in name and not name.startswith("/")
            and ":" not in parts[0] and ".." not in parts)


def resolve(base, href):
    """Resolve a container-relative reference without leaving the container."""
    target = urlsplit(href)
    if target.scheme or target.netloc:
        raise unsafe()
    path = posixpath.normpath(posixpath.join(base, unquote(target.path)))
    if path.startswith(("../", "/")) or path == ".." or not safe_name(path):
        raise unsafe()
    return path


class Container:
    def __init__(self, data):
        try:
            self.archive = zipfile.ZipFile(BytesIO(data))
            entries = self.archive.infolist()
        except (zipfile.BadZipFile, ValueError, OSError):
            raise invalid() from None
        if len(entries) > MAX_ENTRIES:
            raise PublicError(422, "PARSER_LIMIT", "Source exceeds the EPUB entry budget.")
        names = [entry.filename for entry in entries]
        if len(set(names)) != len(names):
            raise invalid()
        if not all(safe_name(name.rstrip("/")) for name in names):
            raise unsafe()
        if any(entry.flag_bits & 0x1 for entry in entries):
            raise PublicError(422, "EPUB_ENCRYPTED", "Encrypted EPUBs are not supported.")
        if sum(entry.file_size for entry in entries) > MAX_EXPANDED:
            raise limited()
        self.names, self.expanded = set(names), 0

    def read(self, name):
        if name not in self.names:
            raise invalid()
        try:
            with self.archive.open(name) as stream:
                data = stream.read(MAX_ENTRY + 1)
        except (zipfile.BadZipFile, ValueError, OSError, EOFError):
            raise invalid() from None
        # Declared sizes are checked up front; actual bytes are bounded too.
        self.expanded += len(data)
        if len(data) > MAX_ENTRY or self.expanded > MAX_EXPANDED:
            raise limited()
        return data

    def xml(self, name):
        try:
            return parse_xml(self.read(name))
        except (DefusedXmlException, SyntaxError, ValueError):
            raise invalid() from None


def spine(container):
    if container.read("mimetype").strip() != b"application/epub+zip":
        raise invalid()
    rootfile = container.xml("META-INF/container.xml").find(f"{CONTAINER_NS}rootfiles/{CONTAINER_NS}rootfile")
    if rootfile is None or not rootfile.get("full-path"):
        raise invalid()
    package_path = resolve("", rootfile.get("full-path"))
    package = container.xml(package_path)
    base = posixpath.dirname(package_path)
    manifest = {item.get("id"): item for item in package.iterfind(f"{OPF_NS}manifest/{OPF_NS}item")}
    sections = []
    for reference in package.iterfind(f"{OPF_NS}spine/{OPF_NS}itemref"):
        item = manifest.get(reference.get("idref"))
        if item is None or not item.get("href"):
            raise invalid()
        sections.append((resolve(base, item.get("href")), item.get("media-type")))
    if not sections:
        raise invalid()
    encrypted = set()
    if "META-INF/encryption.xml" in container.names:
        for cipher in container.xml("META-INF/encryption.xml").iter("{http://www.w3.org/2001/04/xmlenc#}CipherReference"):
            encrypted.add(resolve("", cipher.get("URI", "")))
    if encrypted & {path for path, _ in sections}:
        raise PublicError(422, "EPUB_ENCRYPTED", "Encrypted EPUBs are not supported.")
    return sections


def block_text(element):
    value = SPACE.sub(" ", element.text_content()).replace(BREAK, "\n")
    return re.sub(r" ?\n ?", "\n", value).strip(" \n")


def anchor(element):
    while element is not None:
        if element.get("id"):
            return element.get("id")
        element = element.getparent()
    return None


def parse_epub(data: bytes) -> ParsedEpub:
    container = Container(data)
    blocks, chapters, passages, chapter = [], [], [], None
    offset, warnings = 0, set()
    parser = html.HTMLParser(no_network=True, remove_comments=True, remove_pis=True)
    for index, (path, media_type) in enumerate(spine(container)):
        if media_type not in XHTML_TYPES:
            warnings.add("non_text_content_skipped")
            continue
        try:
            # EPUB content documents are UTF-8 or UTF-16; never let the HTML
            # parser guess. lxml rejects str input that keeps an XML declaration.
            raw = container.read(path)
            source = raw.decode("utf-16") if raw.startswith((b"\xff\xfe", b"\xfe\xff")) else raw.decode("utf-8-sig")
            root = html.document_fromstring(DECLARATION.sub("", source, count=1), parser=parser)
        except (UnicodeDecodeError, ValueError, TypeError, html.etree.ParserError):
            raise invalid() from None
        for element in list(root.iter(*REMOVED)):
            element.drop_tree()
        if next(root.iter(*MEDIA), None) is not None:
            warnings.add("non_text_content_skipped")
        for element in root.iter("br"):
            element.tail = BREAK + (element.tail or "")
        number = 0
        for element in root.iter(*BLOCKS):
            if next(element.iterdescendants(*BLOCKS), None) is not None:
                if (element.text or "").strip() or any((child.tail or "").strip() for child in element):
                    warnings.add("mixed_block_text_skipped")
                continue
            value = block_text(element)
            if not value:
                continue
            start, end = offset, offset + len(value)
            locator = {"section": path, "spine": index, "block": number, "anchor": anchor(element)}
            number += 1
            if element.tag in HEADINGS:
                if CHAPTER.fullmatch(value):
                    if len(chapters) >= 2000:
                        raise PublicError(422, "PARSER_LIMIT", "Source exceeds the chapter budget.")
                    chapter = len(chapters) + 1
                    chapters.append(ParsedChapter(chapter, value, start, end, locator))
            else:
                if end - start > MAX_PASSAGE or len(passages) >= MAX_PASSAGES:
                    raise PublicError(422, "PARSER_LIMIT", "Source exceeds the passage budget.")
                passages.append(ParsedPassage(len(passages), chapter, start, end, value, locator))
            blocks.append(value)
            offset = end + len(SEPARATOR)
            if offset > MAX_CODEPOINTS:
                raise PublicError(422, "PARSER_LIMIT", "Source exceeds the text parser budget.")
    if not passages:
        raise PublicError(422, "NO_PASSAGES", "Source contains no supported paragraphs.")
    if not chapters:
        warnings.add("chapter_structure_unavailable")
    elif any(passage.chapter is None for passage in passages):
        warnings.add("unassigned_preamble")
    return ParsedEpub(ParsedText(tuple(chapters), tuple(passages), tuple(sorted(warnings))), SEPARATOR.join(blocks))
