"""Table-driven intent classification over durable context; no provider calls."""
import uuid

import pytest
from app.schemas.conversation_intent import ConversationIntent
from app.services.conversations import intent
from app.services.conversations.context import Context, Portrayal
from pydantic import ValidationError


def portrayal(ref, subject="Arthur", **request):
    return Portrayal(ref, int(ref.split(":")[1]), uuid.uuid4(), 1, subject, str(uuid.uuid4()), request,
                     f"{subject}, plain linen shirt", {"attire": ["plain linen shirt"]})


CURRENT = portrayal("card:2", moment={"kind": "phrase", "text": "after the war"})
EARLIER = portrayal("card:1")
WITH_CARD = Context(CURRENT, [EARLIER], {}, None)
FRESH = Context(None, [], {}, None)


@pytest.mark.parametrize("context, text, kind, fields", [
    (FRESH, "Arthur after the war at home", "new_portrayal", {"query": "Arthur after the war at home"}),
    (FRESH, "make it watercolor", "new_portrayal", {}),
    (WITH_CARD, "as a watercolor painting", "presentation_edit", {"style": "as a watercolor painting"}),
    (WITH_CARD, "keep the clothes, charcoal sketch", "presentation_edit", {"style": "charcoal sketch", "keep": ["attire"]}),
    (WITH_CARD, "keep the clothes", "presentation_edit", {"keep": ["attire"]}),
    (WITH_CARD, "use the earlier appearance", "moment_edit", {"ref": "card:1"}),
    (WITH_CARD, "what about when he was a child", "moment_edit", {"query": "what about when Arthur was a child"}),
    (WITH_CARD, "where does the book say that?", "source_request", {}),
    (WITH_CARD, "generate an image", "image_request", {}),
    # Wardrobe or scene described as a style must not skip source verification.
    (WITH_CARD, "watercolor style wearing a red coat", "moment_edit", {}),
    (WITH_CARD, "oil painting at the wedding", "moment_edit", {}),
])
def test_deterministic_intents(context, text, kind, fields):
    result = intent.safe(intent.deterministic(context, text), context)
    assert result.kind == kind
    for name, value in fields.items():
        assert getattr(result, name) == value


def test_model_refs_must_be_issued_by_context():
    assert intent.safe(ConversationIntent(kind="moment_edit", ref="card:9"), WITH_CARD) is None
    assert intent.safe(ConversationIntent(kind="clarification_answer", ref="choice:0"), WITH_CARD) is None
    assert intent.safe(ConversationIntent(kind="presentation_edit", style="charcoal"), FRESH) is None
    disguised = intent.safe(ConversationIntent(kind="presentation_edit", style="in his uniform, cinematic"), WITH_CARD)
    assert disguised.kind == "moment_edit" and disguised.context == "in his uniform, cinematic"


def test_actions_use_server_issued_choice_refs_only():
    asked = Context(CURRENT, [], {"choice:0": {"id": str(uuid.uuid4()), "label": "Arthur Penhallow", "field": "subject"}}, {"query": "Arthur"})
    chosen, source = intent.classify(None, None, None, asked, "Arthur Penhallow", "choice:0")
    assert (chosen.kind, chosen.ref, source) == ("clarification_answer", "choice:0", "action")
    chosen, _ = intent.classify(None, None, None, asked, "Arthur Penhallow", "choice:7")
    assert chosen.kind == "new_portrayal"


def test_model_output_is_validated_and_falls_back(monkeypatch):
    monkeypatch.setenv("VISION_INTENT_MODEL", "1")
    monkeypatch.setattr(intent, "model_intent", lambda *args: ConversationIntent(kind="moment_edit", ref="card:42"))
    chosen, source = intent.classify(None, None, None, WITH_CARD, "as a watercolor painting")
    assert (chosen.kind, source) == ("presentation_edit", "deterministic")
    monkeypatch.setattr(intent, "model_intent", lambda *args: ConversationIntent(kind="moment_edit", ref="card:1"))
    assert intent.classify(None, None, None, WITH_CARD, "the look from before")[0].ref == "card:1"


def test_intent_schema_rejects_incomplete_or_unknown_fields():
    with pytest.raises(ValidationError):
        ConversationIntent(kind="new_portrayal")
    with pytest.raises(ValidationError):
        ConversationIntent.model_validate_json('{"kind": "source_request", "work_id": "x"}')
