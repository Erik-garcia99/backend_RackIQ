import uuid
from typing import TYPE_CHECKING
from sqlalchemy import Column, Text, Integer, TIMESTAMP, ForeignKey, func, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.models.base import Base
from enum import Enum as PyEnum

if TYPE_CHECKING:
    from app.models.product import Product

class MovementType(str, PyEnum):
    IN = "in"  # Entrada
    OUT = "out"  # Salida
    ADJUSTMENT = "adjustment"  # Ajuste

class InventoryMovement(Base):
    __tablename__ = "inventory_movement"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id = Column(UUID(as_uuid=True), ForeignKey("product.id", ondelete="CASCADE"), nullable=False)
    branch_id = Column(UUID(as_uuid=True), ForeignKey("branch.id", ondelete="CASCADE"), nullable=False)
    
    movement_type = Column(Enum(MovementType), nullable=False)
    quantity = Column(Integer, nullable=False)
    reason = Column(Text)  # Compra, Venta, Ajuste, etc.
    
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

    # Relationships
    product = relationship("Product", back_populates="inventory_movements", foreign_keys="InventoryMovement.product_id")
    branch = relationship("Branch", backref="inventory_movements")
