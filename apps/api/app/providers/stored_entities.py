"""Reapply local identity rules to previously grounded model spans, without new neural inference."""
import hashlib
import json
from collections import defaultdict

from app.models.entities import Entity, EntityMention, MentionCandidate
from app.models.generations import SourceGeneration
from app.models.model_runs import Derivation
from app.models.passages import Passage
from app.providers.contracts import ProviderUnavailable
from app.providers.extraction import KNOWN_REF
from app.providers.local_entities import PERSONAL, RULES_VERSION, LocalEntities
from sqlalchemy import select
from sqlalchemy.orm import Session


class StoredEntities:
    provider = "local"

    def __init__(self, engine, generation_id, source_id):
        self.sources = {}
        with Session(engine) as db:
            derivation = db.get(Derivation, source_id)
            generation = db.get(SourceGeneration, generation_id)
            if derivation is None or generation is None or derivation.stage != "entities" or derivation.generation_id != generation.id:
                raise ProviderUnavailable()
            if derivation.status != "succeeded" and derivation.error_code != "IDENTITY_REVIEW_FAILED":
                raise ProviderUnavailable()
            for passage in db.scalars(select(Passage).where(Passage.document_id == generation.document_id, Passage.parser_revision == generation.parser_revision)):
                self.sources[f"p{passage.ordinal}"] = {"text": passage.text, "mentions": set()}
            self.configuration = {"source_entities": str(source_id), "rules": RULES_VERSION,
                                  "recognizer": "stored-grounded-spans", "source_processing": derivation.processing_version}
            rows = db.execute(select(EntityMention, Passage, Entity).join(Passage, Passage.id == EntityMention.passage_id)
                              .join(MentionCandidate, MentionCandidate.mention_id == EntityMention.id)
                              .join(Entity, Entity.id == MentionCandidate.entity_id)
                              .where(EntityMention.derivation_id == source_id)).all()
            for mention, passage, entity in rows:
                if passage.document_id != generation.document_id or passage.parser_revision != generation.parser_revision:
                    raise ProviderUnavailable()
                source = self.sources.setdefault(f"p{passage.ordinal}", {"text": passage.text, "mentions": set()})
                if not 0 <= mention.start < mention.end <= len(passage.text):
                    raise ProviderUnavailable()
                source["mentions"].add((mention.start, mention.end, entity.kind, mention.entity_id))
        self.model = f"stored-spans-{hashlib.sha256(str(source_id).encode()).hexdigest()[:12]}+{RULES_VERSION}"

    def complete(self, call):
        items = [item for item in json.loads(call.data)["sources"] if item["ref"] != KNOWN_REF]
        # Passages with no prior model span are valid empty inputs; changed text never reuses a span.
        records = []
        for item in items:
            source = self.sources.get(item["ref"])
            if source is None or source["text"] != item["text"]:
                raise ProviderUnavailable()
            records.append(source)

        def recognize(texts):
            return [[(start, end, kind) for start, end, kind, _ in sorted(record["mentions"], key=lambda row: row[:3])
                     if record["text"][start:end].casefold() not in PERSONAL | {"his", "hers", "himself", "herself", "their", "they", "them"}]
                    for record in records]

        def corefer(_):
            groups, offset = defaultdict(set), 0
            for record in records:
                for start, end, _, entity_id in record["mentions"]:
                    if entity_id is not None:
                        groups[entity_id].add((offset + start, offset + end))
                offset += len(record["text"]) + 2
            return [sorted(spans) for spans in groups.values()]

        return LocalEntities(recognize, corefer).complete(call)
