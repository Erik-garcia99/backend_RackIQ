from pydantic import BaseModel
from uuid import UUID

class TokenValidateRequest(BaseModel):
    token: str

class TokenValidateResponse(BaseModel):
    is_valid: bool
    organization_id: UUID | None = None
    organization_name: str | None = None
    message: str

class TokenGenerateRequest(BaseModel):
    organization_id: UUID
    label: str | None = None

class TokenGenerateResponse(BaseModel):
    token: str
    label: str | None = None
    organization_id: UUID