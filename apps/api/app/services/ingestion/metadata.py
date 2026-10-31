"""Bounded local display metadata; immutable source bytes are never rewritten."""

import re
from threading import Lock

import pypdfium2 as pdfium
from app.core.errors import PublicError
from app.schemas.works import UploadMetadata
from app.services.ingestion.epub_adapter import CONTAINER_NS, Container, resolve
from app.services.ingestion.inputs import MAX_SOURCE_BYTES, validate_source

TEXT_PREFIX = 64 * 1024
XML_LIMIT = 128 * 1024
PDF_LOCK = Lock()  # PDFium calls within one process must not overlap.


def filename_title(filename):
    name = filename.replace("\\", "/").rsplit("/", 1)[-1]
    return clean(name.rsplit(".", 1)[0].replace("_", " "))


def clean(value):
    return " ".join("".join(c for c in value if ord(c) >= 32 or c in "\n\r\t").split())[:256].strip()


def detect_format(data, filename):
    if data.startswith(b"%PDF-"):
        return "pdf"
    if data.startswith(b"PK\x03\x04"):
        container = Container(data)
        try:
            if "mimetype" in container.names and container.archive.getinfo("mimetype").file_size <= 64 \
                    and container.read("mimetype").strip() == b"application/epub+zip":
                return "epub"
        finally:
            container.archive.close()
        raise PublicError(422, "INVALID_SOURCE", "Source is not a supported book format.")
    return "md" if filename.lower().endswith(".md") else "txt"


def epub_title(data):
    container = Container(data)
    try:
        def xml(path):
            if path not in container.names or container.archive.getinfo(path).file_size > XML_LIMIT:
                return None
            return container.xml(path)
        root = xml("META-INF/container.xml")
        if root is None:
            return ""
        rootfile = root.find(f"{CONTAINER_NS}rootfiles/{CONTAINER_NS}rootfile")
        if rootfile is None or not rootfile.get("full-path"):
            return ""
        package = xml(resolve("", rootfile.get("full-path")))
        if package is None:
            return ""
        titles = package.findall("{http://www.idpf.org/2007/opf}metadata/{http://purl.org/dc/elements/1.1/}title")
        return next((clean("".join(t.itertext())) for t in titles if clean("".join(t.itertext()))), "")
    finally:
        container.archive.close()


def embedded_title(data, source_format):
    try:
        if source_format == "epub":
            return epub_title(data)
        if source_format == "pdf":
            with PDF_LOCK, pdfium.PdfDocument(data) as document:
                return clean(document.get_metadata_value("Title"))
        text = data[:TEXT_PREFIX].decode("utf-8", errors="ignore").lstrip("\ufeff").replace("\r\n", "\n")
        if source_format == "md" and text.startswith("---\n"):
            front = text.split("\n---", 1)
            if len(front) == 2:
                match = re.search(r"^title:\s*(.+)$", front[0], re.M | re.I)
                if match:
                    return clean(match[1].strip().strip("\"'"))
        match = re.search(r"^Title:\s*(.+)$", text, re.M | re.I)
        if not match and source_format == "md":
            match = re.search(r"^#\s+(.+?)\s*#*\s*$", text, re.M)
        return clean(match[1]) if match else ""
    except (PublicError, pdfium.PdfiumError, ValueError, UnicodeError, OSError):
        return ""


def resolve_metadata(metadata, data, filename=""):
    if len(data) > MAX_SOURCE_BYTES:
        raise PublicError(413, "SOURCE_TOO_LARGE", "Source exceeds the upload limit.")
    source_format = metadata.format or detect_format(data, filename)
    validate_source(data, source_format)
    title = metadata.title or embedded_title(data, source_format) or filename_title(filename) or "Untitled book"
    return UploadMetadata(title=title, format=source_format)
