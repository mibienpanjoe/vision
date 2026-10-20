"""Format → parser revision and adapter; a job records its revision at upload."""

from app.core.errors import PublicError
from app.services.ingestion.pdf_adapter import NORMALIZATION, PDF_REVISION, parse_pdf
from app.services.ingestion.text_adapter import PARSER_REVISION, parse_text

REVISIONS = {"txt": PARSER_REVISION, "md": PARSER_REVISION, "pdf": PDF_REVISION}


def parse_source(data, source_format, revision):
    """Return parsed text and its normalization revision."""
    if REVISIONS.get(source_format) != revision:
        raise PublicError(422, "UNSUPPORTED_PARSER_VERSION", "Parser revision is not supported.")
    if source_format == "pdf":
        return parse_pdf(data).parsed, NORMALIZATION
    return parse_text(data, source_format), "none-v1"
