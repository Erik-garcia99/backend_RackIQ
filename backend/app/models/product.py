import uuid
from sqlalchemy import Column, Text, Float, Boolean, TIMESTAMP, ForeignKey, Integer, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.models.base import Base

class Product(Base):
    __tablename__ = "product"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    branch_id = Column(UUID(as_uuid=True), ForeignKey("branch.id", ondelete="CASCADE"), nullable=False)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organization.id", ondelete="CASCADE"), nullable=False)
    
    name = Column(Text, nullable=False)
    sku = Column(Text, nullable=False)
    description = Column(Text)
    
    unit_cost = Column(Float, nullable=False, default=0.0)  # Costo unitario
    unit_price = Column(Float, nullable=False, default=0.0)  # Precio de venta
    
    quantity_on_hand = Column(Integer, nullable=False, default=0)  # Stock actual
    reorder_level = Column(Integer, nullable=False, default=10)  # Nivel de reorden
    
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    branch = relationship("Branch", backref="products")
    organization = relationship("Organization", backref="products")
    inventory_movements = relationship("InventoryMovement", back_populates="product", cascade="all, delete-orphan")
    sale_items = relationship("SaleItem", back_populates="product", cascade="all, delete-orphan")
