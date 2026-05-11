from pydantic import BaseModel
from uuid import UUID
from typing import Optional
from datetime import datetime


class OrganizationCreateRequest(BaseModel):
    name: str
    slug: str
    plan_type: str = "free"  # free, pro, enterprise


class OrganizationResponse(BaseModel):
    id: UUID
    name: str
    slug: str
    plan_type: str
    created_ad: Optional[datetime] = None

    class Config:
        from_attributes = True


class OrganizationTokenCreateRequest(BaseModel):
    label: str


class OrganizationTokenResponse(BaseModel):
    id: UUID
    token: str
    label: str
    is_active: bool

    class Config:
        from_attributes = True
