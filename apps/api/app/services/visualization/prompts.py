"""Provider-neutral prompt intent built only from verified traits, creative additions and style.

Disputed traits never enter the prompt; inferred traits enter only in
interpretation mode and are marked as possible. Values excluded at this moment
go to the negative prompt. Provider-specific payloads are later adapters.
"""

from app.schemas.visualization import CreativeAddition, MemberView

COMPOSE_VERSION = "compose-v5"
# Skin regions where a scar or mark is easily lost in a full scene unless the prompt asks to see it.
FACE = {"face", "cheek", "forehead", "brow", "temple", "chin", "jaw", "nose", "neck"}
# Facing the viewer, a person's left is the image's right; image models mirror sides unless told.
MIRROR = {"left": "right", "right": "left"}


def facial(attribute: str) -> bool:
    return not FACE.isdisjoint(attribute.split("_"))


def side(attribute: str, facing: str | None) -> str:
    sides = [MIRROR[word] for word in attribute.split("_") if word in MIRROR]
    return f", on the {sides[0]} side of the image as {facing} faces the viewer" if facing and len(sides) == 1 else ""


def details(member: MemberView, interpretation: bool, facing: str | None = None) -> list[str]:
    traits = [(t, "") for t in member.traits if t.status == "canonical"]
    if interpretation:
        traits += [(t, "possibly ") for t in member.traits if t.status == "inferred"]
    traits.sort(key=lambda item: not facial(item[0].attribute))
    return [t.attribute.replace("_", " ") + (f" in clear view{side(t.attribute, facing)}, showing " if facial(t.attribute)
                                             else ": ") + possibly + ", ".join(t.values) for t, possibly in traits]


def member_text(member: MemberView, interpretation: bool) -> str:
    text = details(member, interpretation)
    return member.entity.label + (f" ({'; '.join(text)})" if text else "")


def compose_prompt(subject: MemberView, participants: list[MemberView], world: list[MemberView],
                   creative: list[CreativeAddition], style: str | None, interpretation: bool,
                   excluded: list[str]) -> tuple[str, str]:
    # Image models merge loosely listed people, redraw repeated objects and split counted people
    # into panels, so the scene is stated as one, people are counted and an object already named as
    # someone's trait value is not listed again. A parenthesised facial mark was never drawn, so the
    # subject's traits are separate sentences, marks first, and the face is turned toward the viewer
    # with each mark's side named as it appears in the image.
    members = [subject, *participants, *world]
    held = {v.casefold() for m in members for t in m.traits for v in t.values}
    people = [m for m in participants if m.entity.kind == "character"]
    things = [m for m in participants if m.entity.kind != "character"
              and not (m.entity.label.casefold() in held and member_text(m, interpretation) == m.entity.label)]
    label = subject.entity.label
    face = any(facial(t.attribute) for t in subject.traits if t.status == "canonical" or (interpretation and t.status == "inferred"))
    parts = [f"One single scene, not a grid or panels, with {label} in the foreground" + (" facing the viewer" if face else "")]
    parts += [f"{label}'s {detail}" for detail in details(subject, interpretation, label if face else None)]
    if people:
        noun = "other person" if len(people) == 1 else "distinct people"
        parts.append(f"Also in the scene, {len(people)} {noun}: " + "; ".join(member_text(m, interpretation) for m in people))
    if things:
        parts.append("Objects: " + "; ".join(member_text(m, interpretation) for m in things))
    if world:
        parts.append("Setting: " + "; ".join(member_text(m, interpretation) for m in world))
    parts += [f"{c.attribute.replace('_', ' ')}: {c.value}" for c in creative if c.attribute != "style"]
    if style:
        parts.append(f"Style: {style}")
    kept = " ".join(v.casefold() for m in members for t in m.traits for v in t.values)
    kept += " " + " ".join(m.entity.label.casefold() for m in members)
    negative = [value for value in dict.fromkeys(excluded) if value.casefold() not in kept]
    return ". ".join(parts)[:4_000], ", ".join(negative)[:2_000]
