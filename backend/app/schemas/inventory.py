"""
inventory.py - Pydantic schemas para endpoints de inventario
"""

from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime
from uuid import UUID


class ShelfMetrics(BaseModel):
    """Métricas de un estante online"""
    current_weight_grams: Optional[float] = None
    units_now: Optional[int] = None
    units_before: Optional[int] = None
    units_removed: Optional[int] = None


class ProductInfo(BaseModel):
    """Información del producto en un estante"""
    id: Optional[str] = None
    name: str
    unit_weight_grams: Optional[float] = None


class ShelfStatus(BaseModel):
    """Estado actual de un estante"""
    shelf_id: str
    shelf_name: str
    status: str  # 'online', 'offline', 'error', 'no_product'
    product_id: Optional[str] = None
    product_name: Optional[str] = None
    unit_weight_grams: Optional[float] = None
    current_weight_grams: Optional[float] = None
    units_before: Optional[int] = None
    units_now: Optional[int] = None
    units_removed: Optional[int] = None
    movement_detected: bool = False
    movement_id: Optional[str] = None
    last_seen: Optional[str] = None
    error: Optional[str] = None


class InventoryMovement(BaseModel):
    """Movimiento de inventario registrado"""
    id: str
    product: str
    quantity: int
    type: str  # 'in', 'out', 'adjustment'
    reason: str
    timestamp: str


class ChangeProductRequest(BaseModel):
    """Request para cambiar el producto de un estante"""
    new_product_id: str


class ChangeProductResponse(BaseModel):
    """Response al cambiar producto"""
    status: str
    shelf_id: str
    shelf_name: str
    old_product: str
    new_product: str
    current_weight_grams: float
    unit_weight_grams: float
    units: int


class BranchInventorySummary(BaseModel):
    """Resumen del inventario de una sucursal"""
    branch_id: str
    total_shelves: int
    shelves: list


class BranchMovements(BaseModel):
    """Movimientos de inventario de una sucursal"""
    branch_id: str
    period_days: int
    total_movements: int
    movements: list
