"""Real preparation/chat actors; fixture recognition covers every source occurrence without neural calls."""
from app.providers.local_entities import RULES_VERSION, LocalEntities
from app.services.narrative import pipeline
from tests.browser_worker import broker, ingest, narrate  # noqa: F401
from tests.conversation_worker import converse  # noqa: F401
from tests.test_local_entities import FIXTURE_SPANS, corefer_pronouns, recognizer


def fixture_entities():
    adapter = LocalEntities(recognizer(FIXTURE_SPANS), corefer_pronouns("Arthur"))
    adapter.model = "synthetic-all-span-v1+" + RULES_VERSION
    adapter.configuration = {"recognizer": "synthetic-fixture", "rules": RULES_VERSION}
    return adapter


pipeline.local_adapter = fixture_entities
