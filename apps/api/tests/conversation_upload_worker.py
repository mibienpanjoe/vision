"""Real preparation/chat actors; fixture recognition covers every source occurrence without neural calls."""
import os
from pathlib import Path

from app.core.errors import PublicError
from app.providers.contracts import ProviderUnavailable
from app.providers.local_entities import RULES_VERSION, LocalEntities
from app.services.ingestion import parse
from app.services.narrative import pipeline
from tests.browser_worker import broker, ingest, narrate  # noqa: F401
from tests.conversation_worker import converse  # noqa: F401
from tests.test_local_entities import FIXTURE_SPANS, corefer_pronouns, recognizer


def fixture_entities():
    adapter = LocalEntities(recognizer(FIXTURE_SPANS), corefer_pronouns("Arthur"))
    adapter.model = "synthetic-all-span-v1+" + RULES_VERSION
    adapter.configuration = {"recognizer": "synthetic-fixture", "rules": RULES_VERSION}
    if marker := os.environ.get("VISION_TEST_NARRATIVE_FAILURE"):
        if Path(marker).exists():
            adapter.complete = lambda _: (_ for _ in ()).throw(ProviderUnavailable())
    return adapter


pipeline.local_adapter = fixture_entities


original_parse = parse.parse_source


def transient_parse(*args, **kwargs):
    if marker := os.environ.get("VISION_TEST_PARSE_FAILURE"):
        if Path(marker).exists():
            raise PublicError(503, "SOURCE_STORE_UNAVAILABLE", "Synthetic parser storage failure.")
    return original_parse(*args, **kwargs)


parse.parse_source = transient_parse
