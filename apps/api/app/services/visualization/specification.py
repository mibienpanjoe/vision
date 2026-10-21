"""The real compose path: plan → retrieve → consolidate → reconstruct → verify → specification.

Every stage stays inside the plan's reading boundary. A provider failure returns
a failed outcome with its code and never falls back to unverified output; a
needs-context or insufficient-evidence result is returned as such. Nothing is
stored here except the consolidation and its run records (T32 stores results).
"""

import os
import uuid

from app.models.generations import SourceGeneration
from app.models.model_runs import Derivation
from app.models.visual_facts import VisualFact
from app.providers.contracts import ProviderAdapter
from app.providers.openai_compatible import GroqGateway
from app.schemas.outcomes import (
    ContextChoice,
    Failed,
    InsufficientEvidence,
    NeedsContext,
    SafeError,
)
from app.schemas.retrieval import VisualizationRequest
from app.schemas.visualization import (
    SPEC_VERSION,
    CreativeAddition,
    EntityRef,
    ExclusionView,
    GenerationIntent,
    Lineage,
    MemberView,
    ResolvedSpecification,
    ScopeView,
    TraitView,
    VerificationView,
    VisualSpecification,
)
from app.services.narrative import pipeline
from app.services.narrative.eligibility import visible_narrative
from app.services.reconstruction.context import scene
from app.services.reconstruction.scene import Member
from app.services.retrieval import query_plan
from app.services.retrieval.consolidation import consolidate
from app.services.retrieval.entity_lookup import SubjectLookup
from app.services.retrieval.evidence import collect
from app.services.retrieval.fusion import fuse, select
from app.services.retrieval.lexical import (
    appearance_linked,
    entity_linked,
    lexical,
    passage_infos,
    terms,
)
from app.services.retrieval.rerank import expand
from app.services.retrieval.semantic import index_version, semantic
from app.services.verification.claims import (
    Verification,
    VerifiedTrait,
    prompt_problems,
    verify_state,
)
from app.services.visualization.prompts import compose_prompt
from sqlalchemy import select as select_rows

RULED_OUT = frozenset({"removed", "negated", "superseded at this moment"})
# A failed consolidation is reclaimed on the next request, so these may succeed when asked again.
RETRYABLE = frozenset({"PROVIDER_RATE_LIMITED", "PROVIDER_TIMEOUT", "PROVIDER_UNAVAILABLE", "PROVIDER_INVALID_OUTPUT"})


def consolidation_adapter() -> ProviderAdapter | None:
    return GroqGateway.from_environment()


def adjudicator(adapter: ProviderAdapter | None) -> ProviderAdapter | None:
    return adapter if os.environ.get("VISION_ADJUDICATE", "1") == "1" else None


def failed(code: str, message: str, correlation_id: str) -> Failed:
    return Failed(outcome="failed", schema_version="1.0",
                  error=SafeError(code=code, message=message, retryable=code in RETRYABLE, correlation_id=correlation_id))


def insufficient(*missing: str) -> InsufficientEvidence:
    return InsufficientEvidence(outcome="insufficient_evidence", schema_version="1.0", missing=list(missing))


def member_view(member: Member, verification: Verification) -> MemberView:
    traits = [TraitView(attribute=t.attribute, status=t.status, values=t.values,
                        evidence=[span for spans in t.evidence.values() for span in spans], reason=t.reason,
                        adjudication=t.adjudication) for t in verification.traits.values()]
    kept = {t.attribute for t in traits if t.status != "inferred"}
    unknown = [u for u in member.state.unknown if u not in kept]
    return MemberView(entity=EntityRef(entity_ids=sorted(member.entity.ids, key=str), kind=member.entity.kind,
                                       label=member.entity.label), role=member.role, traits=traits, unknown=unknown)


def compose(db, actor, work_id: uuid.UUID, request: VisualizationRequest, correlation_id: str):
    plan = query_plan.plan_query(db, actor, work_id, request)
    if isinstance(plan, query_plan.NeedsContext):
        return NeedsContext(outcome="needs_context", schema_version="1.0",
                            choices=[ContextChoice(id=c.value, label=c.label, field=c.field) for c in plan.choices])
    if isinstance(plan, query_plan.InsufficientEvidence):
        return insufficient(*plan.missing)
    adapter = consolidation_adapter()
    if adapter is None:
        return failed("PROVIDER_NOT_ENABLED", "Query-time consolidation is not configured.", correlation_id)

    view = visible_narrative(db, db.get(SourceGeneration, plan.generation_id), plan.cutoff)
    lookup = SubjectLookup(view)
    embedder = pipeline.local_embedder()
    similar = semantic(db, plan, embedder)
    found = collect(entity_linked(db, plan, view), appearance_linked(db, plan, view),
                    lexical(db, plan, lookup.names(plan.subject), terms(plan)), similar or [])
    infos = passage_infos(db, plan)
    selection = select(fuse(found), infos)
    expanded = expand(selection, infos, {c.passage_id: c.anchors for c in found if c.anchors})
    derivation_id = consolidate(db.get_bind(), plan, expanded, adapter)
    db.expire_all()
    derivation = db.get(Derivation, derivation_id)
    if derivation.status != "succeeded":
        return failed(derivation.error_code or "CONSOLIDATION_FAILED", "The evidence could not be consolidated.",
                      correlation_id)

    composed, labels = scene(db, plan, derivation_id)
    if not hasattr(composed, "members"):  # a subject state: no single moment applies
        if composed.outcome == "needs_context":
            return NeedsContext(outcome="needs_context", schema_version="1.0", choices=[
                ContextChoice(id=str(e), label=labels[e][:256], field="moment") for e in composed.choices])
        return insufficient(*(f"The eligible text does not establish {u}." for u in composed.unknown or ["the moment"]))
    if composed.outcome != "resolved":
        return insufficient("The eligible text does not describe this subject at this moment.")

    judge = adjudicator(adapter)
    verified, removed, adjudication = [], 0, "not_requested"
    for member in [*composed.members, *composed.world]:
        subject = lookup.subject(next(iter(member.entity.ids)))
        result = verify_state(db, plan, derivation_id, member.state, member.entity.ids, lookup.names(subject),
                              judge if member.role == "subject" else None)
        removed += len(result.removed)
        if member.role == "subject":
            adjudication = result.adjudication
        verified.append(member_view(member, result))
    subject_view, participants, world = verified[0], verified[1:len(composed.members)], verified[len(composed.members):]
    if not subject_view.traits:
        return insufficient("No verified trait of the subject survives at this moment.")

    creative = [CreativeAddition(attribute="style", value=plan.style, reason="Artistic style, not a claim about the book.")
                ] if plan.style else []
    if plan.creative_mode == "interpretation":
        creative += [CreativeAddition(attribute=u, value="artist's choice", reason="Not established by the eligible text.")
                     for u in subject_view.unknown]
    # Only values the text rules out here belong in the negative prompt; a value from another moment is unknown,
    # not contradicted ("chestnut" childhood hair says nothing about adult hair).
    excluded_ids = [f for m in [*composed.members, *composed.world] for f, reason in m.state.excluded.items()
                    if reason in RULED_OUT]
    excluded_values = list(db.scalars(select_rows(VisualFact.value).where(VisualFact.id.in_(excluded_ids))))
    prompt, negative = compose_prompt(subject_view, participants, world, creative, plan.style,
                                      plan.creative_mode == "interpretation", excluded_values)
    gate = Verification(composed.event, {f"{m.entity.label}:{t.attribute}": VerifiedTrait(
        t.attribute, t.status, t.values, [], {}) for m in verified for t in m.traits})
    if prompt_problems(prompt, gate, excluded_values, {}, [c.value for c in creative]):
        return failed("PROMPT_GATE_FAILED", "The composed prompt did not pass verification.", correlation_id)

    spec = VisualSpecification(
        spec_version=SPEC_VERSION,
        lineage=Lineage(consolidation_id=derivation_id, processing={
            "query_plan": plan.rules_version, "consolidation": derivation.processing_version,
            "index": index_version(embedder) if similar is not None else "unavailable",
            "parser": plan.parser_revision}),
        scope=ScopeView(generation_id=plan.generation_id, parser_revision=plan.parser_revision,
                        through_chapter_id=plan.cutoff_chapter_id, moment=plan.moment,
                        resolved_moment=labels[composed.event][:256] if composed.event in labels else None,
                        context=plan.context, creative_mode=plan.creative_mode),
        subject=subject_view, participants=participants, world=world,
        excluded=[ExclusionView(label=label[:256], reason=reason) for label, reason in composed.excluded.items()],
        unknown=composed.unknown, creative=creative,
        generation=GenerationIntent(style=plan.style, prompt=prompt, negative_prompt=negative),
        verification=VerificationView(adjudication=adjudication, removed=removed, selection=selection.outcome))
    return ResolvedSpecification(outcome="resolved", schema_version="1.0", data=spec)
