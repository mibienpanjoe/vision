"""Progress reflects executed composition stages; replay does not invent work."""
import uuid

import pytest
from app.core.security import ActorScope
from app.models.access import Principal
from app.schemas.retrieval import VisualizationRequest
from app.services.visualization.history import create
from sqlalchemy import select

pytestmark = pytest.mark.integration


def test_grounded_composition_reports_real_stages_and_replay_reports_none(api):
    _, _, work_id, story = api
    owner = story.db.scalar(select(Principal).where(Principal.username == "reader"))
    actor = ActorScope(owner.id, owner.username)
    observed = []
    request = VisualizationRequest(query="Arthur", moment={"kind": "phrase", "text": "after the war"}, context="at home")
    status, result = create(story.db, actor, uuid.UUID(work_id), request, "progress", "test", progress=observed.append)
    assert status == 201 and result.result.root.outcome == "resolved"
    assert observed == ["resolving", "retrieving", "composing", "verifying"]
    observed.clear()
    replay = create(story.db, actor, uuid.UUID(work_id), request, "progress", "test", progress=observed.append)
    assert replay[1] == result and observed == []
