from pydantic import BaseModel
from uuid import UUID
from datetime import datetime

class BranchRegisterRequest(BaseModel):
    token: str
    name: str
    address: str | None = None
    timezone: str = "America/Tijuana"

class BranchResponse(BaseModel):
    id: UUID
    organization_id: UUID
    name: str
    address: str | None
    timezone: str
    is_active: bool
    created_at: datetime
    branch_code: str | None

    model_config = {"from_attributes": True}