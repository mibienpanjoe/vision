"""Image-provider selection stays disabled until D5 supplies its policy and adapter."""

from dataclasses import dataclass


@dataclass(frozen=True)
class RenderPolicy:
    provider: str
    model: str
    max_reservations_per_owner: int


def configured_policy() -> RenderPolicy | None:
    return None
