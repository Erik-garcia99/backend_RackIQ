import uuid
from sqlalchemy import Column, Text, Boolean, TIMESTAMP, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from app.models.base import Base

class User(Base):
    __tablename__ = "user"

    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organization.id", ondelete="CASCADE"), nullable=False)
    branch_id       = Column(UUID(as_uuid=True), ForeignKey("branch.id", ondelete="SET NULL"), nullable=True)
    email           = Column(Text, nullable=False, unique=True)
    name            = Column(Text, nullable=False)
    role            = Column(Text, nullable=False)
    password_hash   = Column(Text, nullable=True)
    push_token      = Column(Text, nullable=True)
    account_status  = Column(Text, nullable=False, default="active")
    created_at      = Column(TIMESTAMP(timezone=True), server_default=func.now())