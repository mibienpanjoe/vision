"""Attribute-level verification of a reconstructed state before anything is composed (T30).

Every fact behind a kept trait is checked again, deterministically, against the
stored source: its spans resolve to the plan's immutable passages and match
their text, every span and linked event lies inside the reading boundary, the
fact belongs to the requested subject and its evidence names that subject, and
a canonical fact is explicit, affirmed, fact or memory, asserted in its quotes
and tied to the requested moment. A fact failing any check is removed with the
reason; a trait with no surviving fact is removed. Model adjudication is
optional and source-bound: it runs only on survivors, a verdict counts only
with a quote from that claim's own evidence, and it can remove a claim but
never approve or promote one.
"""

import json
import re
import uuid
from dataclasses import dataclass, field

from app.models.entities import EntityMention
from app.models.events import EventEvidence
from app.models.passages import Passage
from app.models.visual_facts import FactEvent, FactEvidence, VisualFact
from app.models.works import Document, Work
from app.providers.adjudication import Adjudication, adjudication_request
from app.providers.contracts import Limits, ProviderAdapter, SourceItem
from app.providers.execution import execute, persist_run
from app.schemas.scope import SourceSpan
from app.services.narrative.eligibility import latest
from app.services.narrative.visual_facts import assertion_problem
from app.services.reconstruction.context import claims
from app.services.reconstruction.state import State
from app.services.retrieval.query_plan import describe
from app.services.verification.temporal import applicability_problem, boundary_problem
from sqlalchemy import select
from sqlalchemy.orm import Session

# Text that reads as an instruction to a model has no place in a visual prompt (the corpus plants one).
INSTRUCTION = re.compile(r"\b(ignore|disregard|override|reveal|jailbreak|system prompt|instructions?|secrets?)\b", re.I)
LIMITS = Limits(timeout_seconds=60, max_input_chars=16_000, max_output_tokens=2_048, max_total_tokens=8_000)


@dataclass
class VerifiedTrait:
    attribute: str
    status: str  # canonical, disputed or inferred
    values: list[str]
    facts: list[uuid.UUID]
    evidence: dict[uuid.UUID, list[SourceSpan]]  # per fact, so removing a fact removes its spans
    reason: str | None = None
    adjudication: str = "unchecked"  # unchecked or entailed


@dataclass
class Verification:
    event: uuid.UUID | None
    traits: dict[str, VerifiedTrait] = field(default_factory=dict)
    removed: dict[uuid.UUID, str] = field(default_factory=dict)  # fact id -> failed check
    adjudication: str = "not_requested"  # not_requested, applied or unavailable


@dataclass
class Source:
    """What the checks need about one fact, loaded once."""
    row: VisualFact
    spans: list[FactEvidence]
    event_chapters: list[int | None]


def load(db, derivation_id, fact_ids) -> tuple[dict[uuid.UUID, Source], dict[uuid.UUID, Passage]]:
    facts = {f.id: f for f in db.scalars(select(VisualFact).where(VisualFact.id.in_(fact_ids),
                                                                  VisualFact.derivation_id == derivation_id))}
    spans: dict = {}
    for row in db.scalars(select(FactEvidence).where(FactEvidence.fact_id.in_(facts))):
        spans.setdefault(row.fact_id, []).append(row)
    events: dict = {}
    for fact_id, event_id in db.execute(select(FactEvent.fact_id, FactEvent.event_id).where(FactEvent.fact_id.in_(facts))):
        events.setdefault(fact_id, set()).add(event_id)
    event_passages: dict = {}
    for event_id, passage_id in db.execute(select(EventEvidence.event_id, EventEvidence.passage_id).where(
            EventEvidence.event_id.in_({e for ids in events.values() for e in ids}))):
        event_passages.setdefault(event_id, []).append(passage_id)
    passage_ids = {r.passage_id for rows in spans.values() for r in rows} | {
        p for ids in event_passages.values() for p in ids}
    passages = {p.id: p for p in db.scalars(select(Passage).where(Passage.id.in_(passage_ids)))}
    sources = {fid: Source(f, spans.get(fid, []), [passages[p].chapter_ordinal for e in events.get(fid, ())
                                                   for p in event_passages.get(e, []) if p in passages])
               for fid, f in facts.items()}
    return sources, passages


def problem(source: Source, passages, mentioned, names, subject_ids, plan, canonical) -> str | None:
    fact = source.row
    if fact.subject_id not in subject_ids:
        return "wrong_owner"
    if not source.spans:
        return "no_evidence"
    for span in source.spans:
        passage = passages.get(span.passage_id)
        if passage is None or passage.document_id != plan.document_id \
                or passage.parser_revision != plan.parser_revision or not 0 <= span.start < span.end <= len(passage.text):
            return "span_mismatch"
    found = boundary_problem([passages[s.passage_id].chapter_ordinal for s in source.spans] + source.event_chapters,
                             plan.cutoff)
    if found:
        return found
    if not any(s.passage_id in mentioned or any(n in passages[s.passage_id].text.casefold() for n in names)
               for s in source.spans):
        return "unattributed"
    if canonical:
        if not fact.canonical:
            return "not_canonical"
        quotes = [passages[s.passage_id].text[s.start:s.end] for s in source.spans]
        if assertion_problem(fact.value, quotes, canonical_modality=True):
            return "unsupported_value"
    return None


def verify_state(db, plan, derivation_id: uuid.UUID, state: State, subject_ids, names: list[str],
                 adjudicator: ProviderAdapter | None = None, limits: Limits = LIMITS) -> Verification:
    """Re-check every fact behind `state`'s traits; `names` are the subject's visible names (casefolded)."""
    result = Verification(state.event)
    fact_ids = {f for t in state.traits.values() for f in t.facts}
    sources, passages = load(db, derivation_id, fact_ids)
    claimed, chronology, _ = claims(db, derivation_id)
    by_id = {f.id: f for f in claimed}
    entities = latest(db, plan.generation_id, "entities")
    mentioned = set(db.scalars(select(EntityMention.passage_id).where(
        EntityMention.derivation_id == entities.id, EntityMention.entity_id.in_(subject_ids)))) if entities else set()
    for attribute, trait in state.traits.items():
        canonical = trait.status in {"canonical", "disputed"}
        kept = []
        for fact_id in trait.facts:
            source = sources.get(fact_id)
            found = "no_evidence" if source is None else \
                problem(source, passages, mentioned, names, subject_ids, plan, canonical) or \
                applicability_problem(by_id[fact_id], state.event, chronology, canonical)
            if found:
                result.removed[fact_id] = found
            else:
                kept.append(source)
        if kept:
            values = sorted({s.row.value for s in kept}, key=str.casefold)
            status = trait.status if trait.status == "inferred" else \
                "disputed" if len({v.casefold() for v in values}) > 1 else "canonical"
            result.traits[attribute] = VerifiedTrait(
                attribute, status, values, [k.row.id for k in kept],
                {k.row.id: [SourceSpan(document_revision_id=str(plan.document_id), passage_id=str(s.passage_id),
                                       start=s.start, end=s.end, quote=passages[s.passage_id].text[s.start:s.end])
                            for s in k.spans] for k in kept},
                trait.reason)
    if adjudicator is not None:
        adjudicate(db, plan, derivation_id, result, adjudicator, limits)
    return result


def adjudicate(db, plan, derivation_id, result: Verification, adapter: ProviderAdapter, limits: Limits) -> None:
    """Remove canonical claims a quoted verdict rejects; mark traits a quoted verdict entails."""
    refs, items, values = {}, [], {}
    moment = describe(plan.moment) if plan.moment else plan.context
    for trait in result.traits.values():
        if trait.status == "inferred":
            continue
        for fact_id in trait.facts:
            fact = db.get(VisualFact, fact_id)
            quotes = [s.quote for s in trait.evidence[fact_id]]
            refs[f"c{len(items)}"] = (trait, fact_id, quotes)
            values[fact_id] = fact.value
            context = [db.get(Passage, uuid.UUID(pid)).text for pid in
                       dict.fromkeys(s.passage_id for s in trait.evidence[fact_id])]
            items.append(SourceItem(ref=f"c{len(items)}", text=json.dumps(
                {"subject": plan.subject.label, "moment": moment, "attribute": fact.attribute, "value": fact.value,
                 "quotes": quotes, "context": context}, ensure_ascii=False)))
    if not items:
        return
    run = execute(adapter, adjudication_request(items, limits), Adjudication)
    owner_id = db.scalar(select(Work.owner_id).join(Document, Document.work_id == Work.id)
                         .where(Document.id == plan.document_id))
    with Session(db.get_bind()) as session, session.begin():
        persist_run(session, owner_id, run.record, plan.generation_id, derivation_id)
    if run.output is None:
        result.adjudication = "unavailable"
        return
    result.adjudication = "applied"
    for verdict in run.output.verdicts:
        trait, fact_id, quotes = refs.get(verdict.claim, (None, None, []))
        if trait is None or fact_id not in trait.facts or not any(verdict.quote in q for q in quotes):
            continue  # unquoted or mis-quoted verdicts count for nothing
        if verdict.verdict == "entailed":
            trait.adjudication = "entailed"
        else:
            trait.facts.remove(fact_id)
            trait.evidence.pop(fact_id, None)
            result.removed[fact_id] = f"adjudicated_{verdict.verdict}"
    for attribute, trait in list(result.traits.items()):
        if not trait.facts:
            del result.traits[attribute]
        elif trait.status != "inferred":
            trait.values = sorted({values[f] for f in trait.facts}, key=str.casefold)
            trait.status = "disputed" if len({v.casefold() for v in trait.values}) > 1 else "canonical"


def prompt_problems(prompt: str, verification: Verification, excluded: list[str], locks: dict[str, str],
                    creative: list[str]) -> list[str]:
    """Checks on the final composed prompt; an empty list passes.

    Excluded or removed values may not appear unless a kept value contains them; disputed values may not
    appear as settled; every lock must be a kept canonical value and appear; creative additions may not be
    presented as quotations; instruction-like text is refused.
    """
    text = prompt.casefold()
    kept = [v.casefold() for t in verification.traits.values() if t.status != "disputed" for v in t.values]
    kept += [c.casefold() for c in creative]
    problems = [f"excluded_value:{value}" for value in dict.fromkeys(excluded)
                if value.casefold() in text and not any(value.casefold() in k for k in kept)]
    problems += [f"disputed_as_settled:{t.attribute}" for t in verification.traits.values()
                 if t.status == "disputed" and any(v.casefold() in text for v in t.values)]
    for attribute, value in locks.items():
        trait = verification.traits.get(attribute)
        if trait is None or trait.status != "canonical" or value.casefold() not in [v.casefold() for v in trait.values]:
            problems.append(f"lock_unsupported:{attribute}")
        elif value.casefold() not in text:
            problems.append(f"lock_missing:{attribute}")
    problems += [f"quoted_creative:{c}" for c in creative
                 if any(f"{a}{c.casefold()}{b}" in text for a, b in ('""', "“”", "''"))]
    if INSTRUCTION.search(prompt):
        problems.append("instruction_text")
    return problems
