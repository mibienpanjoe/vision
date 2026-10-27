"""Refine presentation under a strong revision; canonical profiles remain immutable."""

import hashlib
import json
import re

from app.core.errors import PublicError
from app.models.model_runs import Derivation
from app.models.visualizations import (
    Visualization,
    VisualizationMutation,
    VisualizationRevision,
)
from app.models.works import Document
from app.schemas.evidence import EvidenceRequest
from app.schemas.visualization import CreativeAddition
from app.services.narrative import pipeline
from app.services.narrative.browse import current_generation
from app.services.narrative.eligibility import latest
from app.services.retrieval.semantic import index_version
from app.services.verification.claims import (
    Verification,
    VerifiedTrait,
    prompt_problems,
)
from app.services.verification.provenance import resolve_evidence
from app.services.visualization import history
from app.services.visualization.prompts import compose_prompt
from sqlalchemy import select


def conflict(code, message):
    return PublicError(409, code, message)


def current_inputs(db, generation, index):
    entities = latest(db, generation.id, "entities")
    appearance = latest(db, generation.id, "appearance", entities.id) if entities else None
    indexed = db.scalar(select(Derivation.id).where(
        Derivation.generation_id == generation.id, Derivation.stage == "index",
        Derivation.processing_version == index, Derivation.status == "succeeded"))
    return {"entities": str(entities.id) if entities else None,
            "appearance": str(appearance.id) if appearance else None, "index": str(indexed) if indexed else None}


def require_current_inputs(db, actor, work_id, spec):
    # Parse publication takes this same lock before advancing the source pointer.
    db.scalar(select(Document).where(Document.work_id == work_id, Document.revision == 1).with_for_update())
    _, generation = current_generation(db, actor, work_id)
    if generation.id != spec.scope.generation_id or generation.parser_revision != spec.scope.parser_revision:
        raise conflict("SCOPE_CHANGED", "The source changed. Create a new reconstruction.")
    index = index_version(pipeline.local_embedder())
    if (not spec.lineage.inputs or spec.lineage.inputs != current_inputs(db, generation, index)
            or (spec.lineage.inputs.get("index") and spec.lineage.processing["index"] != index)):
        raise conflict("DEPENDENCIES_CHANGED", "Processing changed. Create a new reconstruction.")
    return generation


def refine(db, actor, work_id, visualization_id, body, match, key):
    history.owned(db, actor, work_id, visualization_id)
    visualization = db.scalar(select(Visualization).where(Visualization.id == visualization_id)
                              .with_for_update().execution_options(populate_existing=True))
    if match is None:
        raise PublicError(428, "REVISION_REQUIRED", "A current revision is required.")
    if not re.fullmatch(r'"[1-9][0-9]*"', match):
        raise PublicError(412, "REVISION_CONFLICT", "Result changed. Reload its current revision.")
    expected = int(match[1:-1])
    digest = hashlib.sha256(json.dumps(body.model_dump(mode="json"), sort_keys=True).encode()).hexdigest()
    receipt = db.get(VisualizationMutation, (visualization_id, key))
    if receipt is not None:
        if receipt.expected_revision != expected or receipt.request_hash != digest:
            raise conflict("IDEMPOTENCY_CONFLICT", "Key already used for another refinement.")
        return history.view(db, visualization, receipt.result_revision)
    if expected != visualization.revision:
        raise PublicError(412, "REVISION_CONFLICT", "Result changed. Reload its current revision.")
    base = history.view(db, visualization)
    spec = base.result.data.model_copy(deep=True)
    generation = require_current_inputs(db, actor, work_id, spec)

    members = [spec.subject, *spec.participants, *spec.world]
    boundary = {"mode": "through_chapter", "chapter_id": str(spec.scope.through_chapter_id)} if spec.scope.through_chapter_id else {"mode": "whole_book"}
    gate = Verification(None)
    for member in members:
        for trait in member.traits:
            for span in trait.evidence:
                resolve_evidence(db, actor, work_id, EvidenceRequest.model_validate_json(json.dumps({
                    "span": span.model_dump(), "parser_revision": spec.scope.parser_revision,
                    "reading_boundary": boundary, "context_before": 0, "context_after": 0})))
            gate.traits[f"{member.entity.entity_ids[0]}:{trait.attribute}"] = VerifiedTrait(
                trait.attribute, trait.status, trait.values, [], {})
    locks = {}
    for lock_index, lock in enumerate(body.locks):
        trait = next((trait for member in members if lock.entity_id in member.entity.entity_ids
                      for trait in member.traits if trait.attribute == lock.attribute and trait.status == "canonical"
                      and lock.value in trait.values), None)
        if trait is None:
            raise conflict("LOCK_UNSUPPORTED", "A lock must match an existing canonical value.")
        lock_key = f"lock:{lock_index}"
        locks[lock_key] = lock.value
        gate.traits[lock_key] = VerifiedTrait(trait.attribute, trait.status, trait.values, [], {})

    spec.creative = [CreativeAddition(attribute="style", value=body.style,
                                     reason="Artistic style, not a claim about the book.")] if body.style else []
    if body.creative_mode == "interpretation":
        spec.creative += [CreativeAddition(attribute=unknown, value="artist's choice",
                                           reason="Not established by the eligible text.") for unknown in spec.subject.unknown]
    prompt, negative = compose_prompt(spec.subject, spec.participants, spec.world, spec.creative, body.style,
                                      body.creative_mode == "interpretation", spec.generation.excluded_values)
    if prompt_problems(prompt, gate, spec.generation.excluded_values, locks, [addition.value for addition in spec.creative],
                       entities=[m.entity.label for m in [spec.subject, *spec.participants, *spec.world]]):
        raise conflict("PROMPT_GATE_FAILED", "The refinement conflicts with the verified profile.")
    spec.scope.creative_mode = body.creative_mode
    spec.generation.style, spec.generation.prompt, spec.generation.negative_prompt = body.style, prompt, negative
    spec.locks = body.locks
    spec.lineage.processing["refinement"] = "refinement-v1"
    base.result.data = spec
    request = {**base.request.model_dump(mode="json"), "style": body.style, "creative_mode": body.creative_mode}
    number = expected + 1
    db.add(VisualizationRevision(visualization_id=visualization.id, number=number, generation_id=generation.id,
                                parser_revision=spec.scope.parser_revision, consolidation_id=spec.lineage.consolidation_id,
                                result=base.result.model_dump(mode="json"), request=request))
    db.flush()
    db.add(VisualizationMutation(visualization_id=visualization.id, key=key, expected_revision=expected,
                                 request_hash=digest, result_revision=number))
    visualization.revision = number
    db.commit()
    return history.view(db, visualization, number)
