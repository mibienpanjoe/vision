"""Real conversation actor with only synthetic model adapters and optional test crash gates."""
import os
import time
from pathlib import Path

from app.providers.deterministic import RuleAdapter
from app.providers.embeddings import HashedEmbeddings
from app.services.conversations import store
from app.services.narrative import pipeline
from app.services.visualization import history, specification
from tests.test_appearance_states import annotated_consolidation
from tests.test_grounding_verification import verdict_rule

pipeline.local_embedder = HashedEmbeddings
specification.consolidation_adapter = lambda: RuleAdapter(annotated_consolidation)
specification.adjudicator = lambda _: RuleAdapter(verdict_rule({"plain linen shirt": ("entailed", None)}))
original_compose = history.compose


def gated_compose(*args, **kwargs):
    if gate_path := os.environ.get("VISION_TEST_CONVERSATION_GATE"):
        gate = Path(gate_path)
        if gate.exists():
            kwargs["progress"]("retrieving")
            gate.with_suffix(".started").touch()
            while gate.exists():
                time.sleep(0.05)
    return original_compose(*args, **kwargs)


history.compose = gated_compose

original_publish = store.publish_card


def gated_publish(*args, **kwargs):
    if gate_path := os.environ.get("VISION_TEST_CARD_GATE"):
        gate = Path(gate_path)
        if gate.exists():
            gate.with_suffix(".started").touch()
            while gate.exists():
                time.sleep(0.05)
    return original_publish(*args, **kwargs)


store.publish_card = gated_publish

from app.workers.bootstrap import broker, converse  # noqa: E402, F401
