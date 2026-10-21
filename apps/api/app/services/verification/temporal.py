"""Reading-boundary and story-time guards for one verified claim."""

from app.services.narrative.chronology import Chronology
from app.services.reconstruction.state import Fact, position


def boundary_problem(chapters, cutoff: int | None) -> str | None:
    """Every evidence passage (and every linked event's evidence) must lie inside the reading boundary."""
    if cutoff is not None and any((chapter or 0) > cutoff for chapter in chapters):
        return "beyond_boundary"
    return None


def applicability_problem(fact: Fact, event, chronology: Chronology, canonical: bool) -> str | None:
    """A canonical claim must apply at the requested event itself; an inference must at least precede it."""
    if event is None or not fact.events:
        return None if not canonical or event is None else "not_at_this_moment"
    where = position(fact, event, chronology)
    if where == "direct":
        return None
    if canonical or where != "before":
        return "not_at_this_moment"
    return None
