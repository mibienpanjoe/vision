"""Bounded appearance variants: other moments in the card's own query-scoped consolidation where the
same resolved subject has different explicit canonical traits. No timeline is claimed beyond it."""
import hashlib

from app.models.passages import Passage
from app.models.visual_facts import FactEvidence
from app.schemas.appearance_variants import AppearanceVariant, TraitChange
from app.schemas.evidence import EvidenceSpan
from app.services.reconstruction.context import claims, subject_group
from app.services.reconstruction.state import moment_choices, reconstruct
from sqlalchemy import select

LIMIT = 3


def variant_id(card, event_id) -> str:
    digest = hashlib.sha256(f"{card.card_id}:{card.number}:{card.generation_id}:{event_id}".encode()).hexdigest()
    return f"variant:{digest[:16]}"


def evidence(db, fact_ids) -> list[EvidenceSpan]:
    spans = []
    for row in db.scalars(select(FactEvidence).where(FactEvidence.fact_id.in_(fact_ids)).order_by(FactEvidence.id).limit(8)):
        passage = db.scalar(select(Passage).where(Passage.id == row.passage_id))
        quote = passage.text[row.start:row.end] if passage else ""
        if quote:
            spans.append(EvidenceSpan(document_revision_id=str(passage.document_id), passage_id=str(passage.id),
                                      start=row.start, end=row.end, quote=quote[:2000]))
    return spans


def variants(db, card, spec) -> list[AppearanceVariant]:
    derivation_id = spec.lineage.consolidation_id
    if derivation_id is None:
        return []
    facts, chronology, labels = claims(db, derivation_id)
    group = subject_group(db, derivation_id, spec.subject.entity.entity_ids)
    own = [f for f in facts if f.subject in group and f.explained]
    current = {t.attribute.casefold(): {v.casefold() for v in t.values} for t in spec.subject.traits if t.status == "canonical"}
    shown = {e for e, label in labels.items() if label == spec.scope.resolved_moment}
    found = []
    for event in moment_choices(own, chronology):
        if event in shown or event not in labels:
            continue
        state = reconstruct(facts, group, spec.subject.entity.kind, event, chronology)
        changes, fact_ids = [], []
        for key, trait in state.traits.items():
            if trait.status != "canonical" or {v.casefold() for v in trait.values} == current.get(key, set()):
                continue
            before = next((t.values for t in spec.subject.traits if t.attribute.casefold() == key and t.status == "canonical"), [])
            changes.append(TraitChange(attribute=key, before=before[:8], after=trait.values[:8]))
            fact_ids += trait.facts
        spans = evidence(db, fact_ids) if changes else []
        if changes and spans:
            found.append(AppearanceVariant(id=variant_id(card, event), label=labels[event][:256], event_id=event,
                                           changes=changes[:8], evidence=spans, card_revision=card.number,
                                           generation_id=card.generation_id))
        if len(found) == LIMIT:
            break
    return found
