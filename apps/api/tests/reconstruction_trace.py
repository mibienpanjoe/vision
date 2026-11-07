"""Synthetic capture/replay and identity diagnostic tooling; never in the application path."""

from app.providers.contracts import ProviderResult, ProviderUnavailable, call_digest


class CallBudget:
    def __init__(self, limit):
        self.limit, self.used, self.exhausted = limit, 0, False

    def take(self):
        if self.used >= self.limit:
            self.exhausted = True
            raise ProviderUnavailable()
        self.used += 1


class CaptureAdapter:
    def __init__(self, adapter):
        self.adapter = adapter
        self.provider, self.model = adapter.provider, adapter.model
        self.configuration = getattr(adapter, "configuration", {})
        self.calls = []

    def complete(self, call):
        entry = {"request": call.model_dump(), "digest": call_digest(call)}
        self.calls.append(entry)
        try:
            result = self.adapter.complete(call)
        except Exception as error:
            entry["error_type"] = type(error).__name__
            raise
        entry["response"] = result.model_dump()
        return result


class ReplayAdapter:
    provider, model = "synthetic", "replay-v1"

    def __init__(self, calls):
        self.calls, self.position = calls, 0

    def complete(self, call):
        if self.position >= len(self.calls):
            raise ValueError("Replay exhausted")
        entry = self.calls[self.position]
        if entry["digest"] != call_digest(call):
            raise ValueError("Replay request differs from captured request")
        self.position += 1
        if "error_type" in entry:
            from app.providers import contracts
            error = getattr(contracts, entry["error_type"], None)
            if error in {contracts.ProviderUnavailable, contracts.ProviderTimeout,
                         contracts.ProviderRateLimited, contracts.ProviderInputTooLarge}:
                raise error()
            raise ValueError("Captured unexpected failure; inspect the synthetic run")
        return ProviderResult.model_validate(entry["response"])


def call_metadata(capture, budget):
    if capture.provider == "openai":
        return {"provider_call_count": budget.used, "provider_call_cap": budget.limit,
                "call_cap_reached": budget.exhausted}
    return {"provider_call_count": len(capture.calls)}


def identity_diagnostic(case, recognize, through=None, corefer=None):
    """Run real local rules/lookup with controlled recognizer spans and an independent truth oracle.

    `gaps` records observed disagreements with that oracle; an expected gap is a
    reproduction of a defect, not evidence that identity quality passed.
    """
    import uuid
    from types import SimpleNamespace

    from app.providers.extraction import EntityExtraction
    from app.providers.local_entities import extract
    from app.services.narrative.eligibility import Narrative
    from app.services.retrieval.entity_lookup import SubjectLookup

    sources = {f"p{number}": text for number, text in enumerate(case["chapters"][:through], 1)}
    output = EntityExtraction.model_validate(extract(
        [{"ref": ref, "text": text} for ref, text in sources.items()], [], recognize, corefer or (lambda _: [])))

    def key(value):
        return uuid.uuid5(uuid.NAMESPACE_URL, f"vision-synthetic/{case['id']}/{value}")

    ids = {entity.key: key(entity.key) for entity in output.entities}
    view = Narrative({key(ref): (number, text) for number, (ref, text) in enumerate(sources.items(), 1)})
    for entity in output.entities:
        entity_id = ids[entity.key]
        view.entities[entity_id] = SimpleNamespace(id=entity_id, label=entity.label, kind=entity.kind)
        view.labels[entity_id] = entity.label
    for number, mention in enumerate(output.mentions):
        candidates = [mention.entity] if mention.entity else mention.candidates
        record = SimpleNamespace(id=key(f"mention-{number}"), passage_id=key(mention.ref),
                                 start=mention.start, end=mention.start + len(mention.quote),
                                 entity_id=ids.get(mention.entity))
        view.mentions.append(record)
        view.candidates[record.id] = [ids[candidate] for candidate in candidates]
    view.aliases = [SimpleNamespace(entity_id=ids[alias.entity], label=alias.label, status=alias.status)
                    for alias in output.aliases]
    view.relations = [SimpleNamespace(subject_id=ids[relation.subject], object_id=ids[relation.object],
                                     relation=relation.relation) for relation in output.relations]
    from app.services.narrative.entities import name_variants
    view.relations.extend(SimpleNamespace(subject_id=short, object_id=full, relation="same_as")
                          for short, full in name_variants(view.entities.values()))
    lookup = SubjectLookup(view)

    def subjects(name):
        return {subject for match in lookup.find(name) for subject in match.subjects}

    truth = case["before_reveal"] if through is not None else case
    observations, gaps = [], []
    for index, (left, right, expected) in enumerate(truth["pairs"]):
        a, b = subjects(left), subjects(right)
        observed = "missing" if not a or not b else "same" if a == b else "separate" if a.isdisjoint(b) else "ambiguous"
        observations.append({"left": left, "right": right, "expected": expected, "observed": observed})
        if observed != expected:
            gaps.append(f"pair:{index}")
    for name, expected in truth.get("expected_kinds", {}).items():
        kinds = {subject.kind for subject in subjects(name)}
        observations.append({"name": name, "expected_kind": expected, "observed_kinds": sorted(kinds)})
        if kinds != {expected}:
            gaps.append(f"kind:{name}")
    return {"sources": sources, "output": output.model_dump(), "lookup": lookup,
            "observations": observations, "gaps": gaps}
