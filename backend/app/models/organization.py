import uuid
from sqlalchemy import Column, Text, TIMESTAMP, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.models.base import Base

class Organization(Base):
    __tablename__ = "organization"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(Text, nullable=False)
    slug = Column(Text, nullable=False, unique=True)
    plan_type = Column(Text, nullable=False)
    created_ad = Column(TIMESTAMP, server_default=func.now())

    branches = relationship("Branch", back_populates="organization")
    tokens = relationship("OrganizationToken", back_populates="organization")