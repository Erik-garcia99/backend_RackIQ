from pydantic import BaseModel
from typing import Optional
from uuid import UUID

class ProductResponse(BaseModel):
    id: UUID
    name: str
    sku: str
    unit_cost: float
    unit_price: float
    quantity_on_hand: int

    class Config:
        from_attributes = True

class ProductCreateRequest(BaseModel):
    name: str
    sku: str
    description: Optional[str] = None
    unit_cost: float
    unit_price: float
    reorder_level: int = 10
