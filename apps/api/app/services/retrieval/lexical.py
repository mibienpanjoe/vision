"""Entity-linked and PostgreSQL full-text candidates inside one plan's scope.

Every query is restricted to the plan's document, parser revision and reading
boundary before any row is returned. Names come only from surfaces that identify
the subject alone at this cutoff, so an ambiguous title never widens the search.
"""

from functools import reduce

from app.models.appearance import AppearanceCandidate, AppearanceSubject
from app.models.passages import Passage
from app.services.narrative.eligibility import latest
from app.services.retrieval.evidence import Candidate
from app.services.retrieval.fusion import PassageInfo
from app.services.retrieval.query_plan import WORDS
from sqlalchemy import case, func, or_, select

CONFIG = "english"
LIMIT = 50


def in_scope(query, plan):
    query = query.where(Passage.document_id == plan.document_id, Passage.parser_revision == plan.parser_revision)
    if plan.cutoff is not None:
        query = query.where(or_(Passage.chapter_ordinal.is_(None), Passage.chapter_ordinal <= plan.cutoff))
    return query


def passage_infos(db, plan) -> dict:
    """Ordinal and text of every passage inside the plan's scope, for selection and expansion."""
    rows = db.execute(in_scope(select(Passage.id, Passage.ordinal, Passage.text), plan)).all()
    return {pid: PassageInfo(ordinal, text) for pid, ordinal, text in rows}


def ordinals(db, plan, passage_ids) -> dict:
    return dict(db.execute(in_scope(select(Passage.id, Passage.ordinal), plan).where(Passage.id.in_(passage_ids))).all())


def entity_linked(db, plan, view) -> list[Candidate]:
    """Whole passages where a mention resolves to the subject, most mentions first."""
    group = set(plan.subject.entity_ids)
    anchors: dict = {}
    for mention in view.mentions:
        if mention.entity_id in group:
            anchors.setdefault(mention.passage_id, set()).add((mention.start, mention.end))
    order = ordinals(db, plan, anchors)
    ranked = sorted(anchors, key=lambda p: (-len(anchors[p]), order[p]))
    return [Candidate(p, 0, len(view.passages[p][1]), {"entity": rank}, anchors=anchors[p])
            for rank, p in enumerate(ranked, 1)]


def appearance_linked(db, plan, view) -> list[Candidate]:
    """Protected description sentences whose resolved mentions include the subject."""
    entities = latest(db, plan.generation_id, "entities")
    derivation = entities and latest(db, plan.generation_id, "appearance", entities.id)
    if derivation is None:
        return []
    rows = db.execute(select(AppearanceCandidate).join(AppearanceSubject)
                      .where(AppearanceCandidate.derivation_id == derivation.id,
                             AppearanceSubject.entity_id.in_(plan.subject.entity_ids))).scalars().unique().all()
    rows = [r for r in rows if r.passage_id in view.passages]
    order = ordinals(db, plan, {r.passage_id for r in rows})
    rows.sort(key=lambda r: (order[r.passage_id], r.start))
    return [Candidate(r.passage_id, r.start, r.end, {"appearance": rank}, protected=True)
            for rank, r in enumerate(rows, 1)]


def terms(plan) -> list[str]:
    """Moment and context words; an age is searched as written in English prose."""
    found = [plan.context] if plan.context else []
    if plan.moment is not None:
        if plan.moment.kind == "phrase":
            found.append(plan.moment.text)
        else:
            found.append(WORDS[plan.moment.years] if plan.moment.years < len(WORDS) else str(plan.moment.years))
    return found


def lexical(db, plan, names: list[str], extra: list[str], limit: int = LIMIT) -> list[Candidate]:
    """Whole passages matching any exact name phrase or request term.

    Passages matching more distinct names and terms come first, then cover density.
    """
    parts = [func.phraseto_tsquery(CONFIG, n) for n in names] + [func.plainto_tsquery(CONFIG, t) for t in extra]
    if not parts:
        return []
    query = reduce(lambda a, b: a.op("||")(b), parts)
    coverage = reduce(lambda a, b: a + b, [case((Passage.search.op("@@")(part), 1), else_=0) for part in parts])
    rows = db.execute(in_scope(select(Passage.id, func.length(Passage.text)), plan)
                      .where(Passage.search.op("@@")(query))
                      .order_by(coverage.desc(), func.ts_rank_cd(Passage.search, query).desc(), Passage.ordinal)
                      .limit(limit)).all()
    return [Candidate(pid, 0, length, {"lexical": i}) for i, (pid, length) in enumerate(rows, 1)]
