"""Isolated browser API: real persistence and domain services, deterministic model adapters."""

from app.main import create_app
from app.providers.deterministic import RuleAdapter
from app.providers.embeddings import HashedEmbeddings
from app.services.narrative import pipeline
from app.services.visualization import specification
from tests.test_appearance_states import annotated_consolidation
from tests.test_grounding_verification import verdict_rule

pipeline.local_embedder = HashedEmbeddings
specification.consolidation_adapter = lambda: RuleAdapter(annotated_consolidation)
specification.adjudicator = lambda _: RuleAdapter(verdict_rule({"plain linen shirt": ("entailed", None)}))
app = create_app()
