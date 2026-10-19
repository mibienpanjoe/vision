from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

OpaqueId = Annotated[str, Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")]


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
