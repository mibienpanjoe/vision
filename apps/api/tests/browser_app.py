"""Isolated browser API: real persistence and domain services, deterministic model adapters."""

import json

from app.main import create_app
from app.providers.contracts import ProviderRateLimited
from app.providers.deterministic import RuleAdapter
from app.providers.embeddings import HashedEmbeddings
from app.providers.images import RenderPolicy
from app.services.narrative import pipeline
from app.services.visualization import render, specification
from tests.test_appearance_states import annotated_consolidation
from tests.test_grounding_verification import verdict_rule

pipeline.local_embedder = HashedEmbeddings
def consolidation_rule(sources):
    request = json.loads(next(source["text"] for source in sources if source["ref"] == "request"))
    if "unavailable provider" in (request["request"] or ""):
        raise ProviderRateLimited()
    result = annotated_consolidation(sources)
    if result["requested_event"] is None:
        result["requested_event"] = next((event["key"] for event in result["events"] if event["label"] == request["moment"]), None)
    return result


specification.consolidation_adapter = lambda: RuleAdapter(consolidation_rule)
specification.adjudicator = lambda _: RuleAdapter(verdict_rule({"plain linen shirt": ("entailed", None)}))
# Synthetic renders: the worker returns a fixture PNG; no image provider is called.
render.configured_policy = lambda: RenderPolicy("synthetic", "fixture-v1", 5)
app = create_app()
