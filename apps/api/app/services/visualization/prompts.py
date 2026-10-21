"""Provider-neutral prompt intent built only from verified traits, creative additions and style.

Disputed traits never enter the prompt; inferred traits enter only in
interpretation mode and are marked as possible. Values excluded at this moment
go to the negative prompt. Provider-specific payloads are later adapters.
"""

from app.schemas.visualization import CreativeAddition, MemberView


def member_text(member: MemberView, interpretation: bool) -> str:
    details = [f"{t.attribute.replace('_', ' ')}: {', '.join(t.values)}" for t in member.traits if t.status == "canonical"]
    if interpretation:
        details += [f"{t.attribute.replace('_', ' ')}: possibly {', '.join(t.values)}"
                    for t in member.traits if t.status == "inferred"]
    return member.entity.label + (f" ({'; '.join(details)})" if details else "")


def compose_prompt(subject: MemberView, participants: list[MemberView], world: list[MemberView],
                   creative: list[CreativeAddition], style: str | None, interpretation: bool,
                   excluded: list[str]) -> tuple[str, str]:
    parts = [member_text(subject, interpretation)]
    if participants:
        parts.append("with " + ", ".join(member_text(m, interpretation) for m in participants))
    if world:
        parts.append("setting: " + ", ".join(member_text(m, interpretation) for m in world))
    parts += [f"{c.attribute.replace('_', ' ')}: {c.value}" for c in creative if c.attribute != "style"]
    if style:
        parts.append(f"style: {style}")
    kept = " ".join(v.casefold() for m in [subject, *participants, *world] for t in m.traits for v in t.values)
    negative = [value for value in dict.fromkeys(excluded) if value.casefold() not in kept]
    return "; ".join(parts)[:4_000], ", ".join(negative)[:2_000]
