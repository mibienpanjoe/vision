"""Provider-neutral prompt intent built only from verified traits, creative additions and style.

Disputed traits never enter the prompt; inferred traits enter only in
interpretation mode and are marked as possible. Values excluded at this moment
go to the negative prompt. Provider-specific payloads are later adapters.
"""

from app.schemas.visualization import CreativeAddition, MemberView

COMPOSE_VERSION = "compose-v3"


def member_text(member: MemberView, interpretation: bool) -> str:
    details = [f"{t.attribute.replace('_', ' ')}: {', '.join(t.values)}" for t in member.traits if t.status == "canonical"]
    if interpretation:
        details += [f"{t.attribute.replace('_', ' ')}: possibly {', '.join(t.values)}"
                    for t in member.traits if t.status == "inferred"]
    return member.entity.label + (f" ({'; '.join(details)})" if details else "")


def compose_prompt(subject: MemberView, participants: list[MemberView], world: list[MemberView],
                   creative: list[CreativeAddition], style: str | None, interpretation: bool,
                   excluded: list[str]) -> tuple[str, str]:
    # Image models merge loosely listed people, redraw repeated objects and split counted people
    # into panels, so the scene is stated as one, people are counted and an object already named as
    # someone's trait value is not listed again.
    members = [subject, *participants, *world]
    held = {v.casefold() for m in members for t in m.traits for v in t.values}
    people = [m for m in participants if m.entity.kind == "character"]
    things = [m for m in participants if m.entity.kind != "character"
              and not (m.entity.label.casefold() in held and member_text(m, interpretation) == m.entity.label)]
    parts = ["One single scene, not a grid or panels, showing " + member_text(subject, interpretation)]
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
    negative = [value for value in dict.fromkeys(excluded) if value.casefold() not in kept]
    return ". ".join(parts)[:4_000], ", ".join(negative)[:2_000]
