"""Composed prompts keep members distinct for image models: counted people, no repeated held objects,
and facial marks stated first in plain sentences so they are drawn."""

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
    assert prompt == ("One single scene, not a grid or panels, with Arthur in the foreground facing the viewer. "
                      "Arthur's left cheek in clear view, on the right side of the image as Arthur faces the viewer, "
                      "showing scar still visible. Arthur's attire: plain linen shirt. "
                      "Also in the scene, 2 distinct people: Élodie; Mira (held object: brass compass). "
                      "Setting: house by the ash tree (roof: missing). Style: charcoal")
    assert prompt.count("brass compass") == 1 and negative == "steel armor"


def test_unheld_objects_and_single_people_keep_their_own_phrases():
    subject = member("Wren", "character", "subject")
    participants = [member("Brann", "character", "participant"), member("silver sword", "object", "object")]
    prompt, _ = compose_prompt(subject, participants, [], [], None, False, [])
    assert prompt == ("One single scene, not a grid or panels, with Wren in the foreground. "
                      "Also in the scene, 1 other person: Brann. Objects: silver sword")


def test_marks_on_the_face_come_first_for_every_person():
    subject = member("Wren", "character", "subject", hair="red", forehead="burn mark", right_temple="tattoo")
    participants = [member("Brann", "character", "participant", attire="cloak", left_jaw="old scar")]
    prompt, _ = compose_prompt(subject, participants, [], [], None, False, [])
    assert prompt == ("One single scene, not a grid or panels, with Wren in the foreground facing the viewer. "
                      "Wren's forehead in clear view, showing burn mark. Wren's right temple in clear view, on the left "
                      "side of the image as Wren faces the viewer, showing tattoo. Wren's hair: red. "
                      "Also in the scene, 1 other person: Brann (left jaw in clear view, showing old scar; attire: cloak)")
