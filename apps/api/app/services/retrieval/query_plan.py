"""Normalise a visualization request into one reading-boundary-safe query plan.

Source position and story time stay separate: "chapter 3" narrows or focuses the
source, "at ten" or "after the war" names a story moment for consolidation to
anchor. Structured fields and the query text never override each other; when they
disagree the request returns choices, all drawn from the eligible narrative.
"""

import re
import uuid
from dataclasses import dataclass

from app.models.passages import Chapter
from app.schemas.retrieval import AgeMoment, Moment, PhraseMoment, VisualizationRequest
from app.services.narrative.browse import (
    chapter_ordinal,
    current_generation,
    not_found,
    not_ready,
)
from app.services.narrative.eligibility import visible_narrative
from app.services.retrieval.entity_lookup import Subject, SubjectLookup, fold
from sqlalchemy import select

RULES_VERSION = "query-plan-v1"
WORDS = "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen \
seventeen eighteen nineteen twenty".split()
TENS = {"thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90}
NUMBER = r"(\d{1,3}|" + "|".join(WORDS + list(TENS)) + r")"
END = r"(?=\s+(?:at|in|on|inside|outside|with|wearing|when|while|before|after|during)\b|\s*(?:[,.;:!?\x00]|$))"
CHAPTER = re.compile(r"\b(?:(through|up to|until|by|before|in|from)\s+)?chapter\s+" + NUMBER + r"\b")
AGE = re.compile(r"\b(?:at(?: the age of)?|aged?|when (?:he|she|they|i|it|we) (?:was|were))\s+" + NUMBER + r"\b"
                 r"|\b" + NUMBER + r"\s+years?\s+old\b")
RELATIVE = re.compile(r"\b(?:before|after|during)\s+[^,.;:!?\x00]+?" + END)
CONTEXT = re.compile(r"\b(?:at|in|on|inside|outside)\s+[^,.;:!?\x00]+?" + END)


@dataclass(frozen=True)
class Choice:
    field: str  # subject, moment or context
    value: str
    label: str


@dataclass(frozen=True)
class NeedsContext:
    choices: tuple[Choice, ...]


@dataclass(frozen=True)
class InsufficientEvidence:
    missing: tuple[str, ...]


@dataclass(frozen=True)
class QueryPlan:
    work_id: uuid.UUID
    document_id: uuid.UUID
    generation_id: uuid.UUID
    parser_revision: str
    cutoff: int | None  # chapter ordinal; None is the whole book
    cutoff_chapter_id: uuid.UUID | None
    source_focus: int | None  # a chapter the request points at, never a story time
    subject: Subject
    participants: tuple[Subject, ...]
    moment: Moment | None  # None: unspecified, so distinct states must not be blended
    context: str | None
    creative_mode: str
    style: str | None
    query: str | None
    rules_version: str = RULES_VERSION


def number(token: str) -> int:
    return int(token) if token.isdigit() else TENS.get(token, WORDS.index(token) if token in WORDS else -1)


def mask(text: str, start: int, end: int) -> str:
    return text[:start] + "\x00" * (end - start) + text[end:]


def chapter_by_number(chapters, value: int) -> Chapter | None:
    """Match the title's own number ("Chapter 3", "Chapter Three"), not the parser's ordinal."""
    for chapter in chapters:
        heading = re.match(r"\s*chapter\s+" + NUMBER + r"\b", fold(chapter.title))
        if heading and number(heading.group(1)) == value:
            return chapter
    return None


def same_moment(a: Moment, b: Moment) -> bool:
    return a.kind == b.kind and (a.years == b.years if a.kind == "age" else fold(a.text) == fold(b.text))


def describe(moment: Moment) -> str:
    return f"age {moment.years}" if moment.kind == "age" else moment.text


def subject_choice(subject: Subject) -> Choice:
    return Choice("subject", str(subject.entity_ids[0]), f"{subject.label} ({subject.kind})")


def plan_query(db, actor, work_id: uuid.UUID, request: VisualizationRequest):
    """A QueryPlan, NeedsContext or InsufficientEvidence; access and readiness failures raise."""
    document, generation = current_generation(db, actor, work_id)
    cutoff = chapter_ordinal(db, document, generation, request.through_chapter_id)
    chapters = db.scalars(select(Chapter).where(Chapter.document_id == document.id,
                                                Chapter.parser_revision == generation.parser_revision)
                          .order_by(Chapter.ordinal)).all()
    text = fold(request.query or "")

    focus, narrowed = None, cutoff
    for found in CHAPTER.finditer(text):
        chapter = chapter_by_number(chapters, number(found.group(2)))
        if chapter is None:
            return InsufficientEvidence(("The request names a chapter this work does not have.",))
        if cutoff is not None and chapter.ordinal > cutoff:
            return InsufficientEvidence(("The requested chapter is beyond the reading boundary.",))
        bound = {"before": chapter.ordinal - 1}.get(found.group(1), chapter.ordinal)
        if found.group(1) in {"through", "up to", "until", "by", "before"}:
            narrowed = bound if narrowed is None else min(narrowed, bound)
        else:
            focus = chapter.ordinal
        text = mask(text, *found.span())
    if focus is not None and narrowed is not None and focus > narrowed:
        return InsufficientEvidence(("The requested chapter is beyond the reading boundary.",))
    if narrowed is not None and narrowed < 1:
        return InsufficientEvidence(("No chapter precedes the requested reading boundary.",))

    view = visible_narrative(db, generation, narrowed)
    if view is None:
        raise not_ready()
    lookup = SubjectLookup(view)
    matches = lookup.find(text)
    for match in matches:
        text = mask(text, match.start, match.end)

    moments = []
    for found in AGE.finditer(text):
        moments.append(AgeMoment(kind="age", years=number(found.group(1) or found.group(2))))
        text = mask(text, *found.span())
    for found in RELATIVE.finditer(text):
        moments.append(PhraseMoment(kind="phrase", text=found.group()))
        text = mask(text, *found.span())
    contexts = [found.group() for found in CONTEXT.finditer(text)]

    choices: list[Choice] = []
    if request.moment is not None:
        moments = [request.moment] + [m for m in moments if not same_moment(m, request.moment)]
    if len(moments) > 1:
        choices += [Choice("moment", "request" if m is request.moment else f"query-{i}", describe(m))
                    for i, m in enumerate(moments)]
    if request.context is not None:
        contexts = [request.context] + [c for c in contexts if fold(c) != fold(request.context)]
    if len(contexts) > 1:
        choices += [Choice("context", "request" if c is request.context else f"query-{i}", c)
                    for i, c in enumerate(contexts)]

    structured = None
    if request.entity_id is not None:
        structured = lookup.subject(request.entity_id)
        if structured is None:
            raise not_found()
    named, ambiguous = [], []
    for match in matches:
        if structured in match.subjects:
            named.append(structured)
        elif len(match.subjects) == 1:
            named.append(match.subjects[0])
        else:
            ambiguous.extend(match.subjects)
    named = list(dict.fromkeys(named))
    if ambiguous:
        choices += [subject_choice(s) for s in dict.fromkeys(ambiguous) if s not in named]
    elif structured is not None and named and structured not in named:
        choices += [subject_choice(s) for s in [structured, *named]]
    if choices:
        return NeedsContext(tuple(choices))
    subject = structured or (named[0] if named else None)
    if subject is None:
        return InsufficientEvidence(("No eligible character, place or object matches the request.",))

    cutoff_chapter = next((c.id for c in chapters if c.ordinal == narrowed), None)
    return QueryPlan(work_id=work_id, document_id=document.id, generation_id=generation.id,
                     parser_revision=generation.parser_revision, cutoff=narrowed, cutoff_chapter_id=cutoff_chapter,
                     source_focus=focus, subject=subject, participants=tuple(s for s in named if s != subject),
                     moment=moments[0] if moments else None, context=contexts[0] if contexts else None,
                     creative_mode=request.creative_mode, style=request.style, query=request.query)
