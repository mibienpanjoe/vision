"""Builds synthetic EPUB 3 containers from the narrative corpus for parser tests."""

import zipfile
from html import escape
from io import BytesIO
from pathlib import Path

STORY = Path(__file__).parent / "fixtures/narrative/story.md"
CONTAINER = """<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles>
</container>"""
XHTML = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
<head><title>{title}</title><link rel="stylesheet" href="../styles/book.css"/>
<script>document.title = "never executed";</script></head>
<body>{body}</body>
</html>"""


def chapters():
    """Split the corpus into (heading, paragraphs) sections; the first is the book title."""
    sections = []
    for block in STORY.read_text().strip().split("\n\n"):
        if block.startswith("#"):
            sections.append((block.lstrip("# "), []))
        else:
            sections[-1][1].append(block)
    return sections


def chapter_document(index, heading, paragraphs):
    body = [f'<section epub:type="chapter" id="ch{index}">', f"<h2>{escape(heading)}</h2>"]
    for number, paragraph in enumerate(paragraphs, 1):
        # Source line breaks inside a paragraph are insignificant HTML whitespace.
        wrapped = escape(paragraph, quote=False).replace(". ", ".\n    ", 1)
        body.append(f'<p id="ch{index}-p{number}">{wrapped}</p>')
    body.append("</section>")
    return XHTML.format(title=escape(heading), body="\n".join(body))


def build(entries=None, *, items=(), spine=None, mimetype=b"application/epub+zip"):
    """Return EPUB bytes; `entries` overrides or adds container paths."""
    sections = chapters()
    title, _ = sections[0]
    files = {
        "META-INF/container.xml": CONTAINER,
        "OEBPS/styles/book.css": "p { text-indent: 1em; } @import url(https://example.invalid/x.css);",
        "OEBPS/text/title.xhtml": XHTML.format(title=escape(title),
            body=f'<h1 id="title">{escape(title)}</h1><p><img src="https://example.invalid/cover.png" alt=""/></p>'),
    }
    manifest = [*items, '<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>',
             '<item id="css" href="styles/book.css" media-type="text/css"/>',
             '<item id="title" href="text/title.xhtml" media-type="application/xhtml+xml"/>']
    refs = ['<itemref idref="title"/>']
    for index, (heading, paragraphs) in enumerate(sections[1:], 1):
        files[f"OEBPS/text/chapter{index}.xhtml"] = chapter_document(index, heading, paragraphs)
        manifest.append(f'<item id="c{index}" href="text/chapter{index}.xhtml" media-type="application/xhtml+xml"/>')
        refs.append(f'<itemref idref="c{index}"/>')
    files["OEBPS/nav.xhtml"] = XHTML.format(title="Contents", body='<nav epub:type="toc"><ol>' + "".join(
        f'<li><a href="text/chapter{i}.xhtml">{escape(h)}</a></li>' for i, (h, _) in enumerate(sections[1:], 1))
        + "</ol></nav>")
    files["OEBPS/content.opf"] = f"""<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="id">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier id="id">urn:uuid:00000000-0000-4000-8000-000000000003</dc:identifier>
    <dc:title>{escape(title)}</dc:title><dc:language>en</dc:language>
  </metadata>
  <manifest>{"".join(manifest)}</manifest>
  <spine>{"".join(spine if spine is not None else refs)}</spine>
</package>"""
    files.update(entries or {})
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        if mimetype is not None:
            archive.writestr("mimetype", mimetype, compress_type=zipfile.ZIP_STORED)
        for name, value in files.items():
            if value is not None:
                archive.writestr(name, value, compress_type=zipfile.ZIP_DEFLATED)
    return buffer.getvalue()


def flag_encrypted(data, name):
    """Set the ZIP encryption bit on `name` in its local and central headers."""
    raw = bytearray(data)
    info = zipfile.ZipFile(BytesIO(data)).getinfo(name)
    raw[info.header_offset + 6] |= 0x1
    central = raw.find(b"PK\x01\x02")
    while central != -1:
        length = int.from_bytes(raw[central + 28:central + 30], "little")
        if raw[central + 46:central + 46 + length] == name.encode():
            raw[central + 8] |= 0x1
            return bytes(raw)
        central = raw.find(b"PK\x01\x02", central + 4)
    raise ValueError(name)
