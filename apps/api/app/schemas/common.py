from typing import Annotated

from app.schemas.access import LoginRequest, PrincipalView
from app.schemas.base import ContractModel
from app.schemas.entities import EntityDetail, EntityPage
from app.schemas.evidence import EvidenceRequest, EvidenceView
from app.schemas.jobs import JobView, ProbeRequest
from app.schemas.outcomes import (  # noqa: F401  (re-exported: the shared envelope lives here for callers)
    ContextChoice,
    ErrorEnvelope,
    Failed,
    InsufficientEvidence,
    NeedsContext,
    Resolved,
    SafeError,
)
from app.schemas.retrieval import VisualizationRequest
from app.schemas.scope import RequestScope, SourceSpan
from app.schemas.visualization import (
    RevisionPage,
    VisualizationCreated,
    VisualizationPage,
    VisualizationResult,
    VisualizationView,
)
from app.schemas.works import (
    ChapterPage,
    GenerationPage,
    IngestionView,
    LibraryPage,
    UploadAccepted,
    UploadMetadata,
    WorkView,
)
from pydantic import ConfigDict, Field, RootModel

# A concrete binding proves the generic envelope on a span; VisualizationResult binds it to the specification.
SpanOutcome = Annotated[
    Resolved[SourceSpan] | NeedsContext | InsufficientEvidence | Failed,
    Field(discriminator="outcome"),
]


class SpanResolution(RootModel[SpanOutcome]):
    model_config = ConfigDict(strict=True)


class SchemaCatalog(ContractModel):
    """Build-time export root only; this is not an HTTP request/response."""
    login_request: LoginRequest
    principal: PrincipalView
    probe_request: ProbeRequest
    job: JobView
    upload_metadata: UploadMetadata
    upload_accepted: UploadAccepted
    work: WorkView
    library_page: LibraryPage
    ingestion: IngestionView
    generations: GenerationPage
    chapters: ChapterPage
    evidence_request: EvidenceRequest
    evidence: EvidenceView
    source_span: SourceSpan
    scope: RequestScope
    error: ErrorEnvelope
    span_outcome: SpanResolution
    entity_page: EntityPage
    entity_detail: EntityDetail
    visualization_request: VisualizationRequest
    visualization_result: VisualizationResult
    visualization_created: VisualizationCreated
    visualization: VisualizationView
    visualization_page: VisualizationPage
    revision_page: RevisionPage
