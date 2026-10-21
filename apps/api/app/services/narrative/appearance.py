"""Mark sentences likely to describe how something looks (DEC-38), locally and deterministically.

A candidate is a pointer for retrieval, not a fact: the sentence span, the cue
words it matched and the entities resolved inside it by the entity derivation.
Hand-written cues beat a zero-shot classifier on the annotated corpus (recall
0.79 against 0.33), so no model runs here.
"""

import re
import uuid
from collections.abc import Callable
from datetime import UTC, datetime

from app.models.appearance import AppearanceCandidate, AppearanceSubject
from app.models.entities import EntityMention
from app.models.model_runs import Derivation
from app.services.narrative.derivations import claim
from sqlalchemy import select
from sqlalchemy.orm import Session

STAGE = "appearance"
VERSION = "appearance-v1/cues-v1/local"
CUES = re.compile(
    r"\b(hair|eyes?|face|cheeks?|skin|scars?|beard|moustache|brow|lips|mouth|hands?|figure|stature|height|"
    r"tall|short|pale|dark|fair|stooped|lean|thin|stout|ugly|handsome|beautiful|deformed|dwarfish|"
    r"wore|wearing|worn|dressed|coat|cloak|armou?r|shirt|dress|gown|hat|boots|mask|clothes|clothing|uniform|"
    r"red|blue|green|black|white|gr[ae]y|golden|silver|brass|brown|chestnut|"
    r"steel|iron|wooden|stone|slate|brick|roof|walls?|windows?|candlelight|lamplight|fog)\b", re.I)
SENTENCE = re.compile(r"[^.!?]+[.!?]+[\"”’]?|[^.!?]+$")


def candidates(text: str) -> list[tuple[int, int, str]]:
    """(start, end, cues) for each sentence with at least one cue, trimmed of surrounding space."""
    found = []
    for match in SENTENCE.finditer(text):
        cues = sorted({c.casefold() for c in CUES.findall(match.group())})
        if cues:
            start = match.start() + len(match.group()) - len(match.group().lstrip())
            found.append((start, match.start() + len(match.group().rstrip()), ",".join(cues)[:256]))
    return found


def derive_appearance(engine, generation_id: uuid.UUID, entity_derivation_id: uuid.UUID,
                      cancelled: Callable[[], bool] = lambda: False) -> uuid.UUID:
    derivation_id, attempt, _, passages = claim(engine, generation_id, STAGE, VERSION, entity_derivation_id)
    if attempt is None:
        return derivation_id
    with Session(engine) as db, db.begin():
        derivation = db.scalar(select(Derivation).where(Derivation.id == derivation_id).with_for_update())
        if derivation.attempt != attempt or derivation.status != "running":
            return derivation_id
        if cancelled():
            derivation.status, derivation.completed_at = "cancelled", datetime.now(UTC)
            return derivation_id
        mentions: dict[uuid.UUID, list[tuple[int, int, uuid.UUID]]] = {}
        for mention in db.scalars(select(EntityMention).where(EntityMention.derivation_id == entity_derivation_id,
                                                              EntityMention.entity_id.is_not(None))):
            mentions.setdefault(mention.passage_id, []).append((mention.start, mention.end, mention.entity_id))
        for passage in passages:
            for start, end, cues in candidates(passage.text):
                candidate = AppearanceCandidate(id=uuid.uuid4(), derivation_id=derivation_id, passage_id=passage.id,
                                                start=start, end=end, cues=cues)
                db.add(candidate)
                db.flush()
                db.add_all(AppearanceSubject(candidate_id=candidate.id, entity_id=entity_id) for entity_id in dict.fromkeys(
                    e for s, t, e in mentions.get(passage.id, ()) if start <= s and t <= end))
        derivation.status, derivation.completed_at = "succeeded", datetime.now(UTC)
    return derivation_id
