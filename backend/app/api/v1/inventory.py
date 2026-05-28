"""
inventory.py - Endpoints para gestión de inventario

Utiliza InfluxDB para datos en tiempo real y Supabase para operaciones.
"""

import logging
from typing import List
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.database import get_db
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

# Inicializar detector (será tolerante a fallos)
try:
    detector = InfluxDetector()
except Exception as e:
    logger.warning(f"InfluxDetector inicializado en modo offline: {e}")
    detector = None


@router.get("/branch/{branch_id}/nodes")
async def get_branch_nodes(
    branch_id: str,
    db: Session = Depends(get_db)
):
    """
    Lista todos los nodos (Esp32Node) de una sucursal
    
    Devuelve:
    - Información del nodo
    - Estantes asociados al nodo
    - Status (online/offline si InfluxDB está disponible)
    """
    try:
        # Obtener todos los nodos de la sucursal
        nodes = db.query(Esp32Node)\
            .filter(Esp32Node.branch_id == branch_id)\
            .filter(Esp32Node.is_active == True)\
            .all()
        
        if not nodes:
            return {
                "branch_id": branch_id,
                "total_nodes": 0,
                "nodes": []
            }
        
        result_nodes = []
        
        for node in nodes:
            # Obtener estantes del nodo
            shelves = db.query(Shelf)\
                .filter(Shelf.node_id == node.id)\
                .filter(Shelf.is_active == True)\
                .all()
            
            # Intentar obtener status si InfluxDB está disponible
            node_status = "unknown"
            if detector and detector.is_connected:
                try:
                    # Chequear si hay datos recientes de cualquier estante del nodo
                    for shelf in shelves:
                        weight = detector.get_current_weight(str(shelf.id), timeout_seconds=30)
                        if weight is not None:
                            node_status = "online"
                            break
                    if node_status == "unknown":
                        node_status = "offline"
                except Exception as e:
                    logger.debug(f"Error obteniendo status de nodo {node.id}: {e}")
                    node_status = "unknown"
            
            result_nodes.append({
                "id": str(node.id),
                "name": node.name,
                "mac_address": node.mac_address,
                "status": node_status,
                "shelves_count": len(shelves),
                "shelves": [
                    {
                        "id": str(shelf.id),
                        "name": shelf.name,
                        "product": {
                            "id": str(shelf.product.id) if shelf.product else None,
                            "name": shelf.product.name if shelf.product else "No asignado"
                        } if shelf.product else None
                    }
                    for shelf in shelves
                ]
            })
        
        return {
            "branch_id": branch_id,
            "total_nodes": len(nodes),
            "nodes": result_nodes
        }
    
    except Exception as e:
        logger.error(f"Error listando nodos: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error listando nodos: {str(e)}")


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
    
    Si InfluxDB no está disponible, devuelve status="offline"
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
            shelf_result = {
                "id": str(shelf.id),
                "name": shelf.name,
                "status": "unknown",
                "product": {
                    "id": str(shelf.product.id) if shelf.product else None,
                    "name": shelf.product.name if shelf.product else "No asignado",
                    "unit_weight_grams": float(shelf.product.unit_weight_grams) 
                                        if shelf.product and shelf.product.unit_weight_grams 
                                        else None
                } if shelf.product else None,
                "metrics": None,
                "movement_detected": False,
                "last_seen": shelf.last_reading_at.isoformat() if shelf.last_reading_at else None
            }
            
            # Intentar obtener datos de InfluxDB si está disponible
            if detector and detector.is_connected:
                try:
                    # Obtener peso actual
                    weight = detector.get_current_weight(str(shelf.id), timeout_seconds=30)
                    
                    if weight is not None and shelf.product and shelf.product.unit_weight_grams:
                        # Calcular unidades
                        units_now = int(weight / float(shelf.product.unit_weight_grams))
                        # TODO: Usar last_recorded_units cuando exista en BD
                        units_before = 0  # shelf.last_recorded_units or 0
                        
                        shelf_result["status"] = "online"
                        shelf_result["metrics"] = {
                            "current_weight_grams": weight,
                            "units_now": units_now,
                            "units_before": units_before,
                            "units_removed": units_before - units_now
                        }
                    else:
                        shelf_result["status"] = "offline"
                
                except Exception as e:
                    logger.debug(f"Error obteniendo datos de InfluxDB para {shelf.id}: {e}")
                    shelf_result["status"] = "offline"
            else:
                shelf_result["status"] = "offline"
            
            result_shelves.append(shelf_result)
        
        return {
            "branch_id": branch_id,
            "total_shelves": len(shelves),
            "shelves": result_shelves
        }
    
    except Exception as e:
        logger.error(f"Error obteniendo estantes: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error obteniendo estantes: {str(e)}")


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
