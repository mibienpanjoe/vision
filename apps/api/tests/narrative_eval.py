"""Compare a persisted entity derivation with the annotated corpus.

Misses, false merges, splits and ambiguity violations are reported separately so
a live extraction run can be reviewed without one blended score.
"""

from app.models.entities import Entity, EntityMention, MentionCandidate
from app.models.passages import Passage
from sqlalchemy import select

# Surface forms that identify each annotated entity when a mention resolves to it.
SURFACES = {
    "arthur": {"arthur"},
    "elodie": {"élodie"},
    "mira": {"mira", "captain mira"},
    "brann": {"brann", "captain brann"},
    "wren": {"wren", "masked visitor", "a masked visitor", "the visitor", "visitor", "the masked visitor"},
    "house": {"house", "the house", "house by the ash tree", "the house by the ash tree"},
    "compass": {"compass", "brass compass", "a brass compass", "her brass compass"},
    "sword": {"sword", "silver sword", "a silver sword", "the silver sword", "his sword"},
}


def mention_rows(db, derivation_id):
    rows = db.execute(select(EntityMention, Passage).join(Passage, Passage.id == EntityMention.passage_id)
                      .where(EntityMention.derivation_id == derivation_id)).all()
    candidates = {}
    for mention_id, entity_id in db.execute(select(MentionCandidate.mention_id, MentionCandidate.entity_id)
                                            .join(EntityMention).where(EntityMention.derivation_id == derivation_id)):
        candidates.setdefault(mention_id, set()).add(entity_id)
    return [(m, p, p.text[m.start:m.end], candidates.get(m.id, set())) for m, p in rows]


def evaluate(db, derivation_id) -> dict:
    labels = {e.id: e.label for e in db.scalars(select(Entity).where(Entity.derivation_id == derivation_id))}
    matched: dict = {}
    violations = []
    for mention, passage, text, candidates in mention_rows(db, derivation_id):
        surface = text.casefold().strip()
        if mention.entity_id is not None:
            for expected, forms in SURFACES.items():
                if surface in forms:
                    matched.setdefault(mention.entity_id, set()).add(expected)
        if surface == "captain" and mention.entity_id is not None:
            violations.append(f"title 'captain' resolved to {labels[mention.entity_id]}")
        if surface == "wren" and (passage.chapter_ordinal or 0) < 5 and mention.entity_id is not None \
                and labels[mention.entity_id].casefold() == "arthur":
            violations.append("Wren resolved to Arthur before the chapter-five revelation")
    by_expected: dict = {}
    for entity_id, expected in matched.items():
        for name in expected:
            by_expected.setdefault(name, set()).add(entity_id)
    return {
        "misses": sorted(set(SURFACES) - set(by_expected)),
        "false_merges": sorted(sorted(names) for names in matched.values() if len(names) > 1),
        "splits": sorted(name for name, ids in by_expected.items() if len(ids) > 1),
        "unmatched_entities": sorted(labels[i] for i in labels if i not in matched),
        "ambiguity_violations": violations,
    }
