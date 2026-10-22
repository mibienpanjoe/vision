"""The real render actor with a synthetic image adapter."""

from app.services.visualization import render
from tests.image_fixtures import SyntheticImages

render.image_adapter = SyntheticImages

from app.workers.bootstrap import broker  # noqa: E402, F401
from app.workers.bootstrap import render as render_actor  # noqa: E402, F401
