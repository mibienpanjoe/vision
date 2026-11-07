"""One-click server-issued actions; each becomes an ordinary durable turn, verified like any other."""
from app.core.errors import PublicError
from app.models.conversations import ConversationTurn
from app.services.conversations import resources, store
from sqlalchemy import select


def select_variant(db, actor, conversation_id, match, key, body, correlation_id):
    thread = store.owned(db, actor, conversation_id, lock=True)
    replay = db.scalar(select(ConversationTurn.id).where(ConversationTurn.conversation_id == thread.id, ConversationTurn.key == key))
    request = {"text": "", "variant": body.variant_id, "card_revision": body.card_revision}
    if replay is None:
        if body.card_revision != thread.card_revision:
            raise PublicError(409, "CARD_CHANGED", "The prompt changed. Choose from its current moments.")
        card = resources.card(db, actor, thread, thread.card_revision)
        variant = next((v for v in card.variants if v.id == body.variant_id), None)
        if variant is None:
            raise PublicError(409, "VARIANT_UNAVAILABLE", "That moment is no longer available.")
        request.update(text=variant.label, moment=variant.label, generation_id=str(variant.generation_id))
    else:
        request = db.get(ConversationTurn, replay).request
        if (request.get("variant"), request.get("card_revision")) != (body.variant_id, body.card_revision):
            raise PublicError(409, "IDEMPOTENCY_CONFLICT", "Key already used for another turn.")
    return store.enqueue(db, actor, conversation_id, match, key, request, correlation_id,
                         message_text=f"Show {request['moment']}")
