import uuid
from sqlalchemy import Column, Text, Boolean, TIMESTAMP, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.models.base import Base

class Branch(Base):
    __tablename__ = "branch"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organization.id", ondelete="CASCADE"), nullable=False)
    name = Column(Text, nullable=False)
    address = Column(Text)
    timezone = Column(Text, nullable=False, default="UTC")
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    branch_code = Column(Text, unique=True)

    organization = relationship("Organization", back_populates="branches")
    gateway = relationship("Gateway", back_populates="branch", uselist=False)