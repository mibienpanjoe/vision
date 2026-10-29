"""Local book metadata comes from bounded document fields, never a provider."""

import pytest
from app.core.errors import PublicError
from app.schemas.works import UploadMetadata
from tests.epub_builder import build, chapters


def pdf_with_title():
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
               b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 100 100] >>", b"<< /Title (Embedded PDF Book) >>"]
    data, offsets = b"%PDF-1.4\n", [0]
    for i, obj in enumerate(objects, 1):
        offsets.append(len(data))
        data += f"{i} 0 obj\n".encode() + obj + b"\nendobj\n"
    start = len(data)
    data += b"xref\n0 5\n0000000000 65535 f \n"
    data += b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets[1:])
    return data + f"trailer\n<< /Size 5 /Root 1 0 R /Info 4 0 R >>\nstartxref\n{start}\n%%EOF\n".encode()


@pytest.mark.parametrize("data,filename,source_format,title", [
    (build(), "download.bin", "epub", chapters()[0][0]),
    (pdf_with_title(), "download.txt", "pdf", "Embedded PDF Book"),
    (b"# A Markdown Book\n\nA chapter.", "download.MD", "md", "A Markdown Book"),
    (b'---\ntitle: "A Frontmatter Book"\n---\n\n# Chapter One', "download.md", "md", "A Frontmatter Book"),
    (b"Title: A Text Book\nAuthor: A Writer\n\nA chapter.", "download.txt", "txt", "A Text Book"),
    (b"The first paragraph is not necessarily a title.", r"C:\private\My_Book.txt", "txt", "My Book"),
    (b"A paragraph.", "", "txt", "Untitled book"),
])
def test_automatic_title_and_format(data, filename, source_format, title):
    from app.services.ingestion.metadata import resolve_metadata
    resolved = resolve_metadata(UploadMetadata(), data, filename)
    assert (resolved.format, resolved.title) == (source_format, title)


def test_explicit_override_and_invalid_source_keep_existing_rules():
    from app.services.ingestion.metadata import resolve_metadata
    resolved = resolve_metadata(UploadMetadata(title="My edition", format="md"), b"# Embedded Title", "book.md")
    assert resolved.title == "My edition" and resolved.format == "md"
    with pytest.raises(PublicError):
        resolve_metadata(UploadMetadata(), b"\xff\x00", "bad.txt")
    with pytest.raises(PublicError):
        resolve_metadata(UploadMetadata(format="txt"), pdf_with_title(), "book.pdf")


def test_optional_bad_metadata_falls_back_and_oversized_title_is_bounded():
    from app.services.ingestion.metadata import resolve_metadata
    malformed = build({"OEBPS/content.opf": '<!DOCTYPE x [<!ENTITY boom SYSTEM "file:///etc/passwd">]><x>&boom;</x>'})
    assert resolve_metadata(UploadMetadata(), malformed, "Safe_Name.epub").title == "Safe Name"
    title = resolve_metadata(UploadMetadata(), b"# " + b"A" * 500, "book.md").title
    assert len(title) == 256
