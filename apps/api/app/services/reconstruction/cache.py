"""Scoped cache of resolved specifications (T32b, PROP-05).

The key is everything the result depends on: owner, work, generation, reading
cutoff, subject and participant identities, moment, context, creative mode,
style, locked facts, and the processing versions of every stage (the entity,
appearance and index derivations in use, query-plan rules, consolidation prompt,
schema and model, adjudication, gates and specification versions). A changed
input, model, derivation or generation is a different key, so it is recomputed
rather than reused; a whole-book result can never answer a chapter-limited
reader. A hit is looked up only after the plan has re-checked ownership and the
current generation, and only under the same owner.
"""

import hashlib
import json

from app.models.visualizations import CachedResult
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

GATES_VERSION = "verify-v5"


def cache_scope(owner_id, plan, versions: dict, locks: dict | None = None) -> dict:
    return {"owner": str(owner_id), "work": str(plan.work_id), "generation": str(plan.generation_id),
            "cutoff": plan.cutoff, "subject": sorted(map(str, plan.subject.entity_ids)),
            "participants": sorted(str(i) for p in plan.participants for i in p.entity_ids),
            "moment": plan.moment.model_dump() if plan.moment else None, "context": plan.context,
            "query_sha256": hashlib.sha256((plan.query or "").encode()).hexdigest(),
            "creative_mode": plan.creative_mode, "style": plan.style, "locks": locks or {}, "versions": versions}


def cache_key(scope: dict) -> str:
    return hashlib.sha256(json.dumps(scope, sort_keys=True).encode()).hexdigest()


def lookup(db, owner_id, scope: dict) -> dict | None:
    row = db.scalar(select(CachedResult).where(CachedResult.key == cache_key(scope), CachedResult.owner_id == owner_id))
    return row.result if row is not None else None


def remember(db, owner_id, plan, scope: dict, result: dict) -> None:
    """Concurrent identical requests store one row; the first writer wins."""
    db.execute(insert(CachedResult).values(key=cache_key(scope), owner_id=owner_id, work_id=plan.work_id,
                                           generation_id=plan.generation_id, scope=scope, result=result)
               .on_conflict_do_nothing(index_elements=["key"]))
    db.commit()
