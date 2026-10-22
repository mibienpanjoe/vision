"""Composed prompts keep members distinct for image models: counted people, no repeated held objects."""

import uuid

from app.schemas.visualization import EntityRef, MemberView, TraitView
from app.services.visualization.prompts import compose_prompt

SPAN = {"document_revision_id": str(uuid.uuid4()), "passage_id": str(uuid.uuid4()), "start": 0, "end": 4, "quote": "text"}


def member(label, kind, role, **traits):
    return MemberView(entity=EntityRef(entity_ids=[uuid.uuid4()], kind=kind, label=label), role=role, unknown=[],
                      traits=[TraitView(attribute=attribute, status="canonical", values=[value], evidence=[SPAN])
                              for attribute, value in traits.items()])


def test_people_are_counted_and_a_held_object_is_not_repeated():
    arthur = member("Arthur", "character", "subject", attire="plain linen shirt", left_cheek="scar still visible")
    participants = [member("Élodie", "character", "participant"),
                    member("Mira", "character", "participant", held_object="brass compass"),
                    member("brass compass", "object", "object")]
    world = [member("house by the ash tree", "place", "place", roof="missing")]
    prompt, negative = compose_prompt(arthur, participants, world, [], "charcoal", False, ["steel armor"])
    assert prompt == ("Arthur (attire: plain linen shirt; left cheek: scar still visible). "
                      "2 other people, each shown separately: Élodie; Mira (held object: brass compass). "
                      "Setting: house by the ash tree (roof: missing). Style: charcoal")
    assert prompt.count("brass compass") == 1 and negative == "steel armor"


def test_unheld_objects_and_single_people_keep_their_own_phrases():
    subject = member("Wren", "character", "subject")
    participants = [member("Brann", "character", "participant"), member("silver sword", "object", "object")]
    prompt, _ = compose_prompt(subject, participants, [], [], None, False, [])
    assert prompt == "Wren. 1 other person: Brann. Objects: silver sword"
