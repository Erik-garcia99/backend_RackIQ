from pydantic import BaseModel, EmailStr
from uuid import UUID
from typing import Optional

class LoginRequest(BaseModel):
    email: str
    password: str
    push_token: Optional[str] = None  # Token FCM del dispositivo

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: UUID
    name: str
    role: str
    account_status: str          # ← nuevo, necesario para el front
    organization_id: UUID
    branch_id: Optional[UUID] = None

class RegisterRequest(BaseModel):
    full_name: str
    email: str
    password: str
    organization_token: str      # Token de invitación de la organización
    push_token: Optional[str] = None  # Token FCM del dispositivo

class RegisterResponse(BaseModel):
    user_id: UUID
    name: str
    email: str
    account_status: str
    message: str