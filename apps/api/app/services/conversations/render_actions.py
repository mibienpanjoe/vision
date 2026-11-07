"""Explicit image generation from the active card, reusing the existing reservation, cap and worker.

The reservation key is derived from the card revision, so a button click, a chat request, a duplicate
click or a reload all resolve to the same single render for that prompt version.
"""
from app.core.errors import PublicError
from app.models.conversations import PromptCardRevision
from app.models.renders import RenderJob
from app.schemas.conversations import ConversationRender, ConversationRenderPage
from app.schemas.render import RenderCreate, RenderView
from app.services.visualization import render
from sqlalchemy import select


def card_key(card):
    return f"card-{card.card_id.hex}-{card.number}"


def reserve(db, actor, thread, card_revision):
    if card_revision != thread.card_revision or not thread.card_revision:
        raise PublicError(409, "CARD_CHANGED", "The prompt changed. Generate from its current version.")
    card = db.get(PromptCardRevision, (thread.card_id, card_revision))
    view = render.reserve(db, actor, thread.work_id, card.visualization_id,
                          RenderCreate(specification_revision=card.visualization_revision), card_key(card))
    return ConversationRender(card_revision=card.number, render=view)


def page(db, actor, thread):
    cards = list(db.scalars(select(PromptCardRevision).where(PromptCardRevision.card_id == thread.card_id)))
    by_spec = {}
    for card in sorted(cards, key=lambda c: c.number):
        by_spec.setdefault((card.visualization_id, card.visualization_revision), card.number)
    if not by_spec:
        return ConversationRenderPage(current_card_revision=thread.card_revision, items=[])
    jobs = db.scalars(select(RenderJob).where(RenderJob.owner_id == actor.owner_id, RenderJob.work_id == thread.work_id,
                                              RenderJob.visualization_id.in_({v for v, _ in by_spec}))
                      .order_by(RenderJob.created_at.desc(), RenderJob.id).limit(20))
    items = [ConversationRender(card_revision=by_spec[(job.visualization_id, job.specification_revision)], render=RenderView.from_job(job))
             for job in jobs if (job.visualization_id, job.specification_revision) in by_spec]
    return ConversationRenderPage(current_card_revision=thread.card_revision, items=items)
