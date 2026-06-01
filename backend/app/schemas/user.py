from pydantic import BaseModel
from uuid import UUID
from typing import Optional

class UserResponse(BaseModel):
    id: UUID
    name: str
    email: str
    role: str
    branch_id: Optional[UUID] = None
    branch_name: Optional[str] = None
    phone_number: Optional[str] = None
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

class AssignBranchRequest(BaseModel):
    branch_id: UUID
    supervisor_id: Optional[UUID] = None
    status: Optional[str] = None
    role: Optional[str] = None

class UpdateProfileRequest(BaseModel):
    email: Optional[str] = None
    phone_number: Optional[str] = None
    current_password: str  # Requerido para cambiar contraseña
    new_password: Optional[str] = None  # Solo se cambia si se proporciona

class UpdateProfileResponse(BaseModel):
    id: UUID
    name: str
    email: str
    phone_number: Optional[str] = None
    message: str
