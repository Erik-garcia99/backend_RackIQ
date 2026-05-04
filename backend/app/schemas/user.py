from pydantic import BaseModel
from uuid import UUID
from typing import Optional

class UserResponse(BaseModel):
    id: UUID
    name: str
    email: str
    role: str
    account_status: str
    supervisor_id: Optional[UUID] = None
    supervisor_name: Optional[str] = None
    
    class Config:
        from_attributes = True

class UpdateUserStatusRequest(BaseModel):
    status: str  # active, pending, suspended, deleted

class UpdateUserStatusResponse(BaseModel):
    id: UUID
    name: str
    account_status: str
    message: str

class AssignSupervisorRequest(BaseModel):
    supervisor_id: UUID
