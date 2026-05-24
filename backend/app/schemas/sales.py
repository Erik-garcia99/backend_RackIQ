from pydantic import BaseModel
from typing import Optional, List
from uuid import UUID
from datetime import datetime

class SaleItemResponse(BaseModel):
    id: UUID
    product_id: UUID
    quantity: int
    unit_price: float
    subtotal: float

    class Config:
        from_attributes = True

class SaleResponse(BaseModel):
    id: UUID
    sale_number: str
    subtotal: float
    tax: float
    total: float
    created_at: datetime
    items: List[SaleItemResponse] = []

    class Config:
        from_attributes = True

class DashboardStatsResponse(BaseModel):
    inventory_value: float = 0.0
    sales_today: float = 0.0
    sales_count_today: int = 0
    products_count: int = 0
    low_stock_count: int = 0
    sales_last_7_days: List[dict] = []
    daily_sales_data: List[dict] = []
    margins: dict = {}
    # NUVOS CAMPOS PARA LAS ALERTAS Y VISTA GLOBAL
    alerts: List[dict] = [] 
    branch_statuses: List[dict] = []

