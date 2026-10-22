import os
import uuid
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from app.models.model_runs import Derivation
from app.models.visualizations import VisualizationRevision
from sqlalchemy import select
from sqlalchemy.engine import make_url

pytestmark = pytest.mark.integration
ORIGIN = {"Origin": "http://127.0.0.1:3000"}


def stored(api):
    _, clients, work_id, story = api
    response = clients["reader"].post(f"/v1/works/{work_id}/visualizations", json={
        "query": "Arthur at home after the war", "through_chapter_id": str(story.chapters[3])},
        headers={**ORIGIN, "Idempotency-Key": "refinement-source"})
    assert response.status_code == 201, response.text
    return response.json()["visualization"]


def test_revision_request_and_dependency_inputs_are_preserved_through_migration(api):
    original = stored(api)
    _, clients, work_id, story = api
    view = original["result"]["data"]
    inputs = view["lineage"]["inputs"]
    assert set(inputs) == {"entities", "appearance", "index"}
    consolidation = story.db.get(Derivation, uuid.UUID(view["lineage"]["consolidation_id"]))
    assert inputs["entities"] == str(consolidation.input_derivation_id)
    assert "steel armor" in view["generation"]["excluded_values"]
    story.db.rollback()
    target = make_url(os.environ["DATABASE_URL"])
    assert target.database == story.engine.url.database and target.database.startswith("vision_test_")
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    command.downgrade(config, "0019")
    command.upgrade(config, "head")
    revision = story.db.scalar(select(VisualizationRevision).where(VisualizationRevision.visualization_id == uuid.UUID(original["id"])))
    assert revision.request == original["request"]
    response = clients["reader"].get(f"/v1/works/{work_id}/visualizations/{original['id']}/revisions/1")
    assert response.status_code == 200 and response.json() == original
