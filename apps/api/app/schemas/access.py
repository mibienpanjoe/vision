import uuid

from pydantic import Field

from app.schemas.base import ContractModel


class LoginRequest(ContractModel):
    username: str = Field(pattern=r"^[a-z][a-z0-9_-]{2,31}$")
    password: str = Field(min_length=12, max_length=128)


class PrincipalView(ContractModel):
    id: uuid.UUID
    username: str
