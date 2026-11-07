"""Classify a turn into a validated typed intent from durable context.

A deterministic classifier is the default authority. With VISION_INTENT_MODEL=1 a configured text
adapter proposes the intent under bounded, versioned structured inference; refs it returns must be
ones this context issued, and any invalid or unavailable result falls back to the deterministic path.
"""
import json
import os
import re

from app.providers.contracts import (
    UNTRUSTED_NOTICE,
    Limits,
    ProviderRequest,
    SourceItem,
)
from app.providers.execution import execute, persist_run
from app.schemas.conversation_intent import INTENT_VERSION, ConversationIntent
from pydantic import ValidationError

LIMITS = Limits(timeout_seconds=30, max_input_chars=12_000, max_output_tokens=400, max_total_tokens=6_000)
INSTRUCTIONS = (
    "Classify the reader's latest message about a book portrayal into one typed intent. "
    "new_portrayal: a different subject or a fresh request; query must be self-contained with names, not pronouns. "
    "moment_edit: same subject at another time, age, place or situation, or a change of clothing or scene; "
    "set moment/context, or ref to an earlier_portrayals ref when the reader asks for an earlier appearance. "
    "presentation_edit: only artistic style, medium, lighting or framing; never clothing, body, setting or story facts; "
    "keep lists traits the reader wants unchanged. clarification_answer: the reader picks one of open_choices; set ref. "
    "source_request: the reader asks where the text supports the portrayal. image_request: the reader asks to "
    "generate or render an image. Use only refs present in the data. " + UNTRUSTED_NOTICE)
PRONOUNS = re.compile(r"\b(he|she|him|her|his|hers|they|them|their)\b", re.I)
# Words that describe the depicted content; a "style" containing them must go through source verification.
CONTENT = re.compile(r"\b(wear\w*|dress\w*|cloth\w*|coat|shirt|hat|boots?|uniform|outfit|armou?r|hair\w*|beard|eyes?|"
                     r"scar\w*|wound\w*|injur\w*|older|younger|age[ds]?|child|young|old|inside|outside|"
                     r"home|house|room|war|battle|wedding|night|morning|holding)\b", re.I)
STYLE = re.compile(r"\b(style|watercolou?r|oil|painting|painted|photo\w*|realistic|anime|manga|sketch\w*|charcoal|pencil|"
                   r"ink|noir|cinematic|black and white|monochrome|lighting|portrait|close-?up|framing|render(ed)? as|"
                   r"illustrat\w*|comic|pastel|engraving)\b", re.I)
SOURCE = re.compile(r"\b(source|sources|evidence|quote|quotes|citation|passage|where does|where in the book|why do you say)\b", re.I)
IMAGE = re.compile(r"\b(generate|render|create|make|draw)\b.{0,20}\b(image|picture|illustration|it)\b", re.I)
EARLIER = re.compile(r"\b(earlier|previous|before|original|first|last)\b.{0,15}\b(appearance|look|version|one|portrayal|prompt)\b", re.I)
KEEP = {"attire": r"cloth\w*|outfit|attire|wardrobe|dress", "hair": r"hair", "eyes": r"eyes?", "face": r"face",
        "age": r"age", "build": r"build|body"}
MOMENT = re.compile(r"\b(when|after|before|during|while|as an? |at|in|on|older|younger|later|earlier|childhood|age \d+)\b", re.I)


def resolve(text, subject):
    return PRONOUNS.sub(subject, text) if subject else text


def deterministic(context, text, ref=None) -> ConversationIntent:
    text = " ".join(text.split())
    current = context.current
    if ref is not None:
        return ConversationIntent(kind="clarification_answer", ref=ref)
    if current is None:
        return ConversationIntent(kind="new_portrayal", query=text[:1000])
    if SOURCE.search(text):
        return ConversationIntent(kind="source_request")
    if IMAGE.search(text) and not STYLE.search(text):
        return ConversationIntent(kind="image_request")
    if EARLIER.search(text) and context.earlier:
        return ConversationIntent(kind="moment_edit", ref=context.earlier[0].ref)
    keep = [name for name, pattern in KEEP.items() if re.search(rf"\b(keep|same)\b.{{0,20}}\b({pattern})\b", text, re.I)]
    remainder = re.sub(r"\b(keep|same)\b.{0,20}?\b(" + "|".join(KEEP.values()) + r")\b[,. ]*", " ", text, flags=re.I).strip(" ,.")
    if STYLE.search(remainder) and not CONTENT.search(remainder):
        return ConversationIntent(kind="presentation_edit", style=remainder[:256], keep=keep)
    if keep and not remainder:
        return ConversationIntent(kind="presentation_edit", keep=keep)
    if subject_named(context, text):
        return ConversationIntent(kind="new_portrayal", query=text[:1000])
    if MOMENT.search(remainder or text) or CONTENT.search(remainder or text) or PRONOUNS.search(text):
        return ConversationIntent(kind="moment_edit", query=resolve(remainder or text, current.subject)[:1000], keep=keep)
    return ConversationIntent(kind="new_portrayal", query=text[:1000])


def subject_named(context, text):
    """Another known subject's name means a new portrayal, not an edit of the current one."""
    names = {p.subject.lower() for p in context.earlier} - {context.current.subject.lower()}
    return any(re.search(rf"\b{re.escape(name)}\b", text, re.I) for name in names)


def safe(intent: ConversationIntent, context) -> ConversationIntent | None:
    """Reject unknown refs and route content disguised as style through the verified moment path."""
    issued = set(context.choices) if intent.kind == "clarification_answer" else {p.ref for p in context.earlier}
    if intent.ref is not None and intent.ref not in issued:
        return None
    if context.current is None and intent.kind != "new_portrayal" and intent.kind != "clarification_answer":
        return None
    if intent.kind == "presentation_edit" and intent.style and CONTENT.search(intent.style):
        return ConversationIntent(kind="moment_edit", context=intent.style, keep=intent.keep)
    return intent


def model_intent(db, owner_id, generation_id, context, text):
    from app.services.visualization.specification import consolidation_adapter
    adapter = consolidation_adapter()
    if adapter is None:
        return None
    data = json.dumps({"message": text[:2000], **context.block()}, ensure_ascii=False)
    request = ProviderRequest(role="reasoning", purpose="conversation.intent", prompt_version=INTENT_VERSION,
                              instructions=INSTRUCTIONS, sources=(SourceItem(ref="turn", text=data[:16_000]),), limits=LIMITS)
    run = execute(adapter, request, ConversationIntent)
    persist_run(db, owner_id, run.record, generation_id)
    return run.output


def classify(db, owner_id, generation_id, context, text, ref=None) -> tuple[ConversationIntent, str]:
    if context.variant is not None:
        return ConversationIntent(kind="moment_edit", moment=context.variant), "action"
    if ref is not None:
        if ref not in context.choices:
            return ConversationIntent(kind="new_portrayal", query=text[:1000]), "deterministic"
        return ConversationIntent(kind="clarification_answer", ref=ref), "action"
    if os.environ.get("VISION_INTENT_MODEL") == "1":
        try:
            proposed = model_intent(db, owner_id, generation_id, context, text)
        except ValidationError:
            proposed = None
        if proposed is not None and (checked := safe(proposed, context)) is not None:
            return checked, "model"
    return safe(deterministic(context, text), context) or ConversationIntent(kind="new_portrayal", query=text[:1000]), "deterministic"
