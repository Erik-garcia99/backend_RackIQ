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
    """Response para estadísticas del dashboard"""
    inventory_value: float = 0.0  # Valor total del inventario
    sales_today: float = 0.0  # Ventas del día
    sales_count_today: int = 0  # Cantidad de transacciones hoy
    products_count: int = 0  # Cantidad de productos
    low_stock_count: int = 0  # Productos con stock bajo
    sales_last_7_days: List[dict] = []  # Ventas últimos 7 días
    daily_sales_data: List[dict] = []  # Datos para gráficos
    margins: dict = {}  # Márgenes de ganancia
