"""
inventory.py - Endpoints para gestión de inventario

Utiliza InfluxDB para datos en tiempo real y Supabase para operaciones.
"""

import logging
from typing import List
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.config import settings
from app.models.rpi_models import Shelf, Esp32Node, Gateway
from app.models.product import Product
from app.models.inventory import InventoryMovement
from app.services.influx_detector import InfluxDetector
from app.schemas.inventory import (
    ShelfStatus,
    InventoryMovement as InventoryMovementSchema,
    ChangeProductRequest
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/inventory", tags=["inventory"])

# Inicializar detector
detector = InfluxDetector()


@router.get("/shelf/{shelf_id}/status", response_model=ShelfStatus)
async def get_shelf_status(shelf_id: str, db: Session = Depends(get_db)):
    """
    Obtiene el estado actual de un estante (Online/Offline)
    
    Consulta InfluxDB para determinar si hay datos recientes
    """
    result = detector.detect_movement(db, shelf_id)
    
    if result.get("status") == "error":
        raise HTTPException(status_code=404, detail=result.get("error"))
    
    return result


@router.get("/branch/{branch_id}/shelves")
async def get_branch_shelves(
    branch_id: str,
    db: Session = Depends(get_db)
):
    """
    Obtiene el estado actual de todos los estantes de una sucursal
    
    Combina datos de InfluxDB (peso, status) + Supabase (producto, configuración)
    """
    try:
        # Obtener estantes de la sucursal
        shelves = db.query(Shelf)\
            .filter(Shelf.branch_id == branch_id)\
            .filter(Shelf.is_active == True)\
            .all()
        
        if not shelves:
            return {
                "branch_id": branch_id,
                "total_shelves": 0,
                "shelves": []
            }
        
        result_shelves = []
        
        for shelf in shelves:
            # Detectar estado actual
            detection = detector.detect_movement(db, str(shelf.id))
            
            result_shelves.append({
                "id": str(shelf.id),
                "name": shelf.name,
                "status": detection.get("status"),
                "product": {
                    "id": str(shelf.product.id) if shelf.product else None,
                    "name": shelf.product.name if shelf.product else "No asignado",
                    "unit_weight_grams": float(shelf.product.unit_weight_grams) 
                                        if shelf.product and shelf.product.unit_weight_grams 
                                        else None
                },
                "metrics": {
                    "current_weight_grams": detection.get("current_weight_grams"),
                    "units_now": detection.get("units_now"),
                    "units_before": detection.get("units_before"),
                    "units_removed": detection.get("units_removed")
                } if detection.get("status") == "online" else None,
                "movement_detected": detection.get("movement_detected", False),
                "last_seen": detection.get("last_seen")
            })
        
        return {
            "branch_id": branch_id,
            "total_shelves": len(shelves),
            "shelves": result_shelves
        }
    
    except Exception as e:
        logger.error(f"Error obteniendo estantes: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/branch/{branch_id}/movements")
async def get_branch_movements(
    branch_id: str,
    days: int = Query(7, ge=1, le=90),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db)
):
    """
    Obtiene el historial de movimientos de inventario de una sucursal
    
    Datos vienen de Supabase (inventory_movement)
    """
    try:
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        movements = db.query(InventoryMovement)\
            .filter(InventoryMovement.branch_id == branch_id)\
            .filter(InventoryMovement.created_at >= cutoff_date)\
            .order_by(InventoryMovement.created_at.desc())\
            .limit(limit)\
            .all()
        
        return {
            "branch_id": branch_id,
            "period_days": days,
            "total_movements": len(movements),
            "movements": [
                {
                    "id": str(m.id),
                    "product": m.product.name if m.product else "Unknown",
                    "quantity": m.quantity,
                    "type": m.movement_type,
                    "reason": m.reason,
                    "timestamp": m.created_at.isoformat()
                }
                for m in movements
            ]
        }
    
    except Exception as e:
        logger.error(f"Error obteniendo movimientos: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/shelf/{shelf_id}/change-product")
async def change_shelf_product(
    shelf_id: str,
    request: ChangeProductRequest,
    db: Session = Depends(get_db)
):
    """
    Cambia el producto de un estante sin generar evento falso
    
    Obtiene peso actual, calcula unidades con el nuevo producto,
    y actualiza correctamente en Supabase
    """
    try:
        result = detector.change_product(db, shelf_id, request.new_product_id)
        
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("error"))
        
        return result
    
    except Exception as e:
        logger.error(f"Error cambiando producto: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/detect-all-movements")
async def detect_all_movements_endpoint(db: Session = Depends(get_db)):
    """
    Detecta movimientos en TODOS los estantes activos
    
    Endpoint para testing y debugging
    Normalmente se ejecuta como tarea Celery periódicamente
    """
    try:
        result = detector.detect_all_movements(db)
        return result
    
    except Exception as e:
        logger.error(f"Error detectando movimientos: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
