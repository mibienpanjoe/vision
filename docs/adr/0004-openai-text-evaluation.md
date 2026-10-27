# ADR-0004 — Opt-in OpenAI text evaluation

**Status:** accepted for synthetic integration/evaluation (DEC-53).
**Recorded:** 2026-10-27.

## Context

The maintainer asked to evaluate using their existing OpenAI API key for text
reconstruction, including GPT-6 Luna, to assess cost, quality and smoother use.
The key was already configured for optional images. The text path selected Groq
directly; replacing that key or silently rerouting its requests would mislabel
lineage and change ADR-0003's data-handling policy.

## Decision

Add explicit `VISION_QUERY_PROVIDER=openai` selection for the synthetic
evaluation. Keep Groq as the default and keep local ingestion, retrieval,
grounding, temporal/attribution gates and stored-specification behavior intact.
The selected adapter also adjudicates surviving claims when adjudication is on.
An unknown selector or unconfigured adapter fails closed; it never selects a
different provider automatically.

Use the Responses API with strict JSON schemas, no tools or conversation
history, bounded output, and `store=false`. Adapt mandatory/defaulted properties
only in a copied wire schema; retain the domain schemas and final validation.
Reasoning effort is configurable and participates in derivation/result-cache
identity and safe run metadata. Count reported output tokens including reasoning.
The synthetic comparison selects `none` by default: `low` exhausted the existing
consolidation output cap in nine cases. This does not raise any token limit.
Incomplete/refused output cannot publish facts; retain its reported usage.
Do not automatically repeat a transport failure that may already have charged.

## Consequences

The finite 17-case evaluation and browser gate use only the committed synthetic
story. Preserve separate reports for provider/effort variants and the historical
Groq baseline. Numerical quality, latency and token-cost estimates are evidence,
not an assumption that a cheaper model is equivalent or that any API key has
unlimited capacity. No automatic model escalation or daily spending cap is added.

`store=false` does not establish Zero Data Retention. OpenAI default abuse
monitoring can retain content for up to 30 days and ZDR requires approval.
Private-book use needs an explicit data-handling decision; DEC-37 remains the
default. An existing image credential alone does not enable OpenAI text calls.
No data migration is required. Existing saved specifications remain readable;
provider/effort changes select different inference/cache identities.

See the [operations guide](../operations/development-and-operations.md#openai-text-evaluation--q01)
for configuration and the [acceptance strategy](../testing/acceptance-strategy.md)
for measured results and limits.
