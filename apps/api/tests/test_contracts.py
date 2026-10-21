import json
from pathlib import Path

import pytest
from app.schemas import access, common, evidence, retrieval, scope, visualization
from pydantic import ValidationError

CASES = json.loads(
    (Path(__file__).parents[3] / "packages/contracts/conformance.json").read_text()
)
MODELS = {
    "SourceSpan": scope.SourceSpan,
    "EvidenceView": evidence.EvidenceView,
    "PrincipalView": access.PrincipalView,
    "RequestScope": scope.RequestScope,
    "ErrorEnvelope": common.ErrorEnvelope,
    "SpanResolution": common.SpanResolution,
    "VisualizationRequest": retrieval.VisualizationRequest,
    "VisualizationResult": visualization.VisualizationResult,
    "TraitView": visualization.TraitView,
}


@pytest.mark.parametrize("case", CASES)
def test_shared_conformance(case):
    model = MODELS[case["model"]]
    if case["valid"]:
        result = model.model_validate_json(json.dumps(case["value"]))
        assert model.model_validate_json(result.model_dump_json()) == result
    else:
        with pytest.raises(ValidationError):
            model.model_validate_json(json.dumps(case["value"]))


def test_exact_span_checks_preserve_codepoints_and_revision_text():
    span = scope.SourceSpan(
        document_revision_id="r", passage_id="p", start=1, end=2, quote="🦊"
    )
    span.validate_text("é🦊é")
    with pytest.raises(ValueError):
        span.validate_text("éXé")
    with pytest.raises(ValueError):
        span.validate_text("")
    decomposed = scope.SourceSpan(
        document_revision_id="r", passage_id="p", start=2, end=4, quote="é"
    )
    decomposed.validate_text("é🦊é")
    with pytest.raises(ValueError):
        decomposed.validate_text("é🦊é")
