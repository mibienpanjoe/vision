"""Stored visualizations: idempotent creation of resolved results, owner-scoped reads and revision history.

Only a resolved specification becomes a stored resource; other outcomes are
returned without reserving the key, since nothing was created. A key is scoped
to the owner and work and fingerprints the validated request: the same request
replays the stored result, a different one is `409 IDEMPOTENCY_CONFLICT`.
Another owner's work or visualization is the common `404`.
"""

import hashlib
import json
import uuid

from app.core.errors import PublicError
from app.core.security import owned_object
from app.models.visualizations import Visualization, VisualizationRevision
from app.models.works import Work
from app.schemas.retrieval import VisualizationRequest
from app.schemas.visualization import (
    ResolvedSpecification,
    RevisionPage,
    RevisionSummary,
    VisualizationCreated,
    VisualizationPage,
    VisualizationResult,
    VisualizationSummary,
    VisualizationView,
)
from app.services.visualization.specification import compose
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

PAGE = 100


def not_found():
    return PublicError(404, "RESOURCE_NOT_FOUND", "Resource not found.")


def conflict():
    return PublicError(409, "IDEMPOTENCY_CONFLICT", "Key already used for a different request.")


def view(db, visualization: Visualization, number: int | None = None) -> VisualizationView:
    revision = db.get(VisualizationRevision, (visualization.id, number or visualization.revision))
    if revision is None:
        raise not_found()
    return VisualizationView(id=visualization.id, work_id=visualization.work_id, revision=revision.number,
                             created_at=revision.created_at,
                             request=VisualizationRequest.model_validate_json(json.dumps(visualization.request)),
                             result=ResolvedSpecification.model_validate_json(json.dumps(revision.result)))


def owned(db, actor, work_id, visualization_id) -> Visualization:
    owned_object(db, Work, work_id, actor)
    found = db.scalar(select(Visualization).where(Visualization.id == visualization_id, Visualization.work_id == work_id,
                                                  Visualization.owner_id == actor.owner_id))
    if found is None:
        raise not_found()
    return found


def create(db, actor, work_id: uuid.UUID, body, key: str, correlation_id: str) -> tuple[int, VisualizationCreated]:
    owned_object(db, Work, work_id, actor)
    request = body.model_dump(mode="json")
    digest = hashlib.sha256(json.dumps(request, sort_keys=True).encode()).hexdigest()

    def prior():
        return db.scalar(select(Visualization).where(Visualization.owner_id == actor.owner_id,
                                                     Visualization.work_id == work_id, Visualization.idempotency_key == key))

    def replay(found):
        if found.request_hash != digest:
            raise conflict()
        stored = view(db, found)
        return 201, VisualizationCreated(visualization=stored, result=VisualizationResult(stored.result))

    if (found := prior()) is not None:
        return replay(found)
    outcome = compose(db, actor, work_id, body, correlation_id)
    if outcome.outcome != "resolved":
        return 200, VisualizationCreated(visualization=None, result=VisualizationResult(outcome))
    scope = outcome.data.scope
    visualization = Visualization(owner_id=actor.owner_id, work_id=work_id, idempotency_key=key, request_hash=digest,
                                  request=request, revision=1)
    db.add(visualization)
    try:
        db.flush()
        db.add(VisualizationRevision(visualization_id=visualization.id, number=1, generation_id=scope.generation_id,
                                     parser_revision=scope.parser_revision,
                                     consolidation_id=outcome.data.lineage.consolidation_id,
                                     result=outcome.model_dump(mode="json")))
        db.commit()
    except IntegrityError:
        db.rollback()
        if (found := prior()) is None:
            raise
        return replay(found)
    db.refresh(visualization)
    stored = view(db, visualization)
    return 201, VisualizationCreated(visualization=stored, result=VisualizationResult(stored.result))


def list_visualizations(db, actor, work_id) -> VisualizationPage:
    owned_object(db, Work, work_id, actor)
    rows = db.execute(select(Visualization, VisualizationRevision).join(
        VisualizationRevision, (VisualizationRevision.visualization_id == Visualization.id)
        & (VisualizationRevision.number == Visualization.revision))
        .where(Visualization.work_id == work_id, Visualization.owner_id == actor.owner_id)
        .order_by(Visualization.created_at.desc(), Visualization.id).limit(PAGE)).all()
    return VisualizationPage(items=[VisualizationSummary(
        id=v.id, revision=v.revision, subject=r.result["data"]["subject"]["entity"]["label"],
        created_at=v.created_at) for v, r in rows])


def revisions(db, actor, work_id, visualization_id) -> RevisionPage:
    found = owned(db, actor, work_id, visualization_id)
    rows = db.scalars(select(VisualizationRevision).where(VisualizationRevision.visualization_id == found.id)
                      .order_by(VisualizationRevision.number.desc()))
    return RevisionPage(items=[RevisionSummary(number=r.number, created_at=r.created_at,
                                               generation_id=r.generation_id, parser_revision=r.parser_revision,
                                               consolidation_id=r.consolidation_id) for r in rows])
