"""Compose one scene: who and what is admissibly present at an event, each with its own state.

Every member is reconstructed separately at the same event, so a prop or an
injury stays with the subject the text gives it to. A person is present only
when the event names them or a claim ties them to it, and never when the text
says they were absent; a requested participant without such evidence is
reported, not invented. An object is present when a claim at the event
describes it or a present member holds it. The world context is the state of
the places present: lighting, architecture and atmosphere follow the same
explicit/inferred split, and with no place evidence the setting is unknown.
"""

import re
import unicodedata
from collections.abc import Hashable
from dataclasses import dataclass, field

from app.services.narrative.chronology import Chronology
from app.services.reconstruction.state import Fact, State, position, reconstruct

ABSENT = r"\b(?:was|were)\s+(?:absent|away|elsewhere|not there|not present|gone)\b"
HELD = re.compile(r"^(held_object|holding|carried_object|carrying|prop|props|accessory)$")


@dataclass(frozen=True)
class Entity:
    ids: frozenset
    kind: str
    label: str


@dataclass
class Member:
    entity: Entity
    role: str  # subject, participant, place or object
    state: State


@dataclass
class Scene:
    outcome: str  # resolved or insufficient_evidence
    event: Hashable
    members: list[Member] = field(default_factory=list)
    excluded: dict[str, str] = field(default_factory=dict)  # entity label -> reason
    world: list[Member] = field(default_factory=list)  # the places present, with their own states
    unknown: list[str] = field(default_factory=list)


def sort_key(label: str) -> str:
    """Accent-insensitive order, so "Élodie" sorts with E rather than after Z."""
    return "".join(c for c in unicodedata.normalize("NFKD", label.casefold()) if not unicodedata.combining(c))


def absentees(texts: list[str], entities: list[Entity]) -> set[str]:
    """Labels the text says were absent ("Brann and his sword were absent"), sentence by sentence."""
    found = set()
    for text in texts:
        for sentence in re.findall(r"[^.!?]+[.!?]?", text):
            if re.search(ABSENT, sentence, re.I):
                head = re.split(ABSENT, sentence, flags=re.I)[0]
                found |= {e.label for e in entities if re.search(rf"\b{re.escape(e.label)}\b", head, re.I)}
    return found


def compose_scene(facts: list[Fact], chronology: Chronology, event, subject: Entity, entities: list[Entity],
                  event_participants: set, requested: list[Entity], absent: set[str],
                  carriers: dict[str, str] | None = None) -> Scene:
    """`entities` are the eligible identities; `event_participants` the entity ids the event names;
    `carriers` maps an object's label to the label of whoever the text says carries it."""
    carriers = carriers or {}
    scene = Scene("resolved", event)
    tied = {f.subject for f in facts if f.events and position(f, event, chronology) == "direct"}

    def present(entity: Entity) -> bool:
        return bool(entity.ids & (event_participants | tied))

    members: list[tuple[Entity, str]] = [(subject, "subject")]
    entities = sorted(entities, key=lambda e: (sort_key(e.label), sorted(map(str, e.ids))))
    for entity in entities:
        if entity is subject or entity.kind == "object":
            continue
        if entity.label in absent:
            scene.excluded[entity.label] = "absent from this scene"
        elif present(entity):
            members.append((entity, "place" if entity.kind == "place" else "participant"))
        elif entity in requested:
            scene.excluded[entity.label] = "not established at this moment"
    for entity, role in members:
        state = reconstruct(facts, entity.ids, entity.kind, event, chronology)
        (scene.world if role == "place" else scene.members).append(Member(entity, role, state))

    held = " ".join(v.casefold() for m in scene.members for t in m.state.traits.values()
                    if t.status == "canonical" and HELD.match(t.attribute) for v in t.values)
    for entity in (e for e in entities if e.kind == "object"):
        if entity.label in absent or carriers.get(entity.label) in absent:
            scene.excluded[entity.label] = "absent from this scene"
        elif entity.ids & tied or re.search(rf"\b{re.escape(entity.label.casefold())}\b", held):
            scene.members.append(Member(entity, "object", reconstruct(facts, entity.ids, "object", event, chronology)))
        elif entity in requested:
            scene.excluded[entity.label] = "not established at this moment"
    if not scene.world:
        scene.unknown.append("setting")
    if not any(m.state.traits for m in [*scene.members, *scene.world]):
        scene.outcome = "insufficient_evidence"
    return scene
