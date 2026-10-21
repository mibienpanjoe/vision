"""Real actors with an optional test-owned gate before parsing, for pending UI checks."""

import os
import time
from pathlib import Path

from app.services.ingestion import parse

actual_parse = parse.parse_source


def gated_parse(*args):
    gate = Path(os.environ["VISION_TEST_PARSE_GATE"])
    deadline = time.monotonic() + 60
    while gate.exists():
        if time.monotonic() > deadline:
            raise TimeoutError("Synthetic browser parser gate timed out")
        time.sleep(0.05)
    return actual_parse(*args)


parse.parse_source = gated_parse

from app.workers.bootstrap import broker, ingest, narrate, probe  # noqa: E402, F401
