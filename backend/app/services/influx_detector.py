"""
influx_detector.py - Servicio para detectar movimientos de inventario consultando InfluxDB

Compara peso actual (InfluxDB) con unidades registradas (Supabase) para detectar cambios.
"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.rpi_models import Shelf
from app.models.product import Product
from app.models.inventory import InventoryMovement

logger = logging.getLogger(__name__)


class InfluxDetector:
    """Detector de movimientos de inventario usando InfluxDB + Supabase"""
    
    def __init__(self):
        """Inicializa el cliente de InfluxDB"""
        self.url = settings.INFLUX_URL
        self.token = settings.INFLUX_TOKEN
        self.org = settings.INFLUX_ORG
        self.bucket = settings.INFLUX_BUCKET
        self.is_connected = False
        
        try:
            from influxdb_client import InfluxDBClient
            
            self.client = InfluxDBClient(
                url=self.url,
                token=self.token,
                org=self.org
            )
            self.query_api = self.client.query_api()
            self.is_connected = True
            logger.info(f"[InfluxDetector] Conectado a InfluxDB: {self.url}")
            
        except ImportError:
            logger.error("[InfluxDetector] influxdb-client no instalado")
            logger.error("Instala: pip install influxdb-client")
            self.is_connected = False
            
        except Exception as e:
            logger.error(f"[InfluxDetector] Error conectando a InfluxDB: {str(e)}")
            self.is_connected = False
    
    def get_current_weight(self, shelf_id: str, timeout_seconds: int = 30) -> Optional[float]:
        """
        Obtiene el peso ACTUAL de un estante desde InfluxDB
        
        Args:
            shelf_id: ID del estante
            timeout_seconds: Considera offline si no hay lectura en este tiempo
        
        Returns:
            Peso en gramos o None si está offline
        """
        if not self.is_connected:
            logger.warning(f"[InfluxDetector] No conectado a InfluxDB")
            return None
        
        try:
            # Query para obtener la última lectura de peso
            query = f"""
            from(bucket: "{self.bucket}")
                |> range(start: -{timeout_seconds}s)
                |> filter(fn: (r) => r._measurement == "weight_reading")
                |> filter(fn: (r) => r.shelf_id == "{shelf_id}")
                |> last()
            """
            
            tables = self.query_api.query(query)
            
            if tables and len(tables) > 0:
                for record in tables[0].records:
                    if record.field == "net_weight":
                        weight = float(record.value)
                        logger.debug(f"[InfluxDetector] Peso de {shelf_id}: {weight}g")
                        return weight
            
            logger.debug(f"[InfluxDetector] Sin datos recientes para {shelf_id}")
            return None
            
        except Exception as e:
            logger.error(f"[InfluxDetector] Error consultando peso: {str(e)}")
            return None
    
    def detect_movement(self, db: Session, shelf_id: str) -> Dict[str, Any]:
        """
        Detecta si hubo movimiento en un estante comparando:
        1. Peso actual de InfluxDB
        2. Unidades registradas en Supabase (shelf.last_recorded_units)
        3. Peso unitario del producto (product.unit_weight_grams)
        
        Args:
            db: Sesión de base de datos
            shelf_id: ID del estante
        
        Returns:
            Dict con resultado de la detección
        """
        
        # 1. Obtener estante y producto ACTUAL
        try:
            shelf = db.query(Shelf).filter(Shelf.id == shelf_id).first()
            if not shelf:
                return {"error": "Shelf not found", "status": "error"}
            
            product = shelf.product
            if not product:
                return {"error": "Product not configured", "status": "no_product"}
            
            if not product.unit_weight_grams or product.unit_weight_grams == 0:
                return {"error": "Product unit weight not set", "status": "invalid_product"}
            
        except Exception as e:
            logger.error(f"[InfluxDetector] Error obteniendo shelf/product: {str(e)}")
            return {"error": str(e), "status": "error"}
        
        # 2. Obtener peso ACTUAL de InfluxDB
        current_weight = self.get_current_weight(str(shelf_id))
        
        if current_weight is None:
            # Offline - sin datos recientes
            return {
                "shelf_id": str(shelf_id),
                "shelf_name": shelf.name,
                "status": "offline",
                "last_seen": shelf.last_reading_at.isoformat() if shelf.last_reading_at else None
            }
        
        # 3. Calcular unidades ACTUALES basado en el producto
        unit_weight = float(product.unit_weight_grams)
        units_now = int(current_weight / unit_weight)
        
        # 4. Obtener unidades registradas anteriormente
        # TODO: Usar last_recorded_units una vez que la migración de BD se cree
        # Por ahora, asumimos 0 como referencia (simple detector)
        units_before = 0  # shelf.last_recorded_units or 0
        
        # 5. Calcular delta (cambio)
        units_removed = units_before - units_now
        
        logger.info(
            f"[InfluxDetector] Estante '{shelf.name}': "
            f"Peso={current_weight}g, "
            f"Producto='{product.name}', "
            f"UnitW={unit_weight}g, "
            f"UnitesANTES={units_before}, "
            f"UnidadesAHORA={units_now}, "
            f"DELTA={units_removed}"
        )
        
        result = {
            "shelf_id": str(shelf_id),
            "shelf_name": shelf.name,
            "status": "online",
            "product_id": str(product.id),
            "product_name": product.name,
            "unit_weight_grams": unit_weight,
            "current_weight_grams": current_weight,
            "units_before": units_before,
            "units_now": units_now,
            "units_removed": units_removed,
            "movement_detected": False,
            "movement_id": None
        }
        
        # 6. Si hubo movimiento >= 1 unidad, registrar en Supabase
        if abs(units_removed) >= 1:
            try:
                # Registrar movimiento
                movement = InventoryMovement(
                    product_id=product.id,
                    branch_id=shelf.branch_id,
                    movement_type='out' if units_removed > 0 else 'in',
                    quantity=-units_removed,  # Negativo = salida
                    reason='auto_detected_from_sensor'
                )
                
                db.add(movement)
                
                # Actualizar el timestamp de lectura
                shelf.last_reading_at = datetime.utcnow()
                # TODO: Descomentar cuando se agregue last_recorded_units a BD
                # shelf.last_recorded_units = units_now
                
                db.commit()
                
                result["movement_detected"] = True
                result["movement_id"] = str(movement.id)
                
                logger.info(
                    f"✅ [InfluxDetector] Movimiento registrado: "
                    f"'{product.name}' -{units_removed} unidades "
                    f"(Estante: {shelf.name})"
                )
                
            except Exception as e:
                logger.error(f"[InfluxDetector] Error registrando movimiento: {str(e)}")
                db.rollback()
                result["movement_detected"] = False
                result["error"] = str(e)
        
        return result
    
    def detect_all_movements(self, db: Session) -> Dict[str, Any]:
        """
        Detecta movimientos en TODOS los estantes activos
        
        Args:
            db: Sesión de base de datos
        
        Returns:
            Dict con resultados de todas las detecciones
        """
        try:
            # Obtener todos los estantes activos
            shelves = db.query(Shelf).filter(Shelf.is_active == True).all()
            
            results = {
                "total_shelves": len(shelves),
                "movements_detected": 0,
                "shelves": []
            }
            
            for shelf in shelves:
                try:
                    result = self.detect_movement(db, str(shelf.id))
                    results["shelves"].append(result)
                    
                    if result.get("movement_detected"):
                        results["movements_detected"] += 1
                
                except Exception as e:
                    logger.error(f"[InfluxDetector] Error detectando movimiento en {shelf.id}: {str(e)}")
                    results["shelves"].append({
                        "shelf_id": str(shelf.id),
                        "error": str(e),
                        "status": "error"
                    })
            
            return results
        
        except Exception as e:
            logger.error(f"[InfluxDetector] Error en detect_all_movements: {str(e)}")
            return {"error": str(e), "status": "error"}
    
    def change_product(self, db: Session, shelf_id: str, new_product_id: str) -> Dict[str, Any]:
        """
        Cambia el producto de un estante sin generar evento falso
        
        Obtiene el peso actual, calcula unidades con el NUEVO producto,
y registra movimientos sin depender de last_recorded_units.
        
        Args:
            db: Sesión de base de datos
            shelf_id: ID del estante
            new_product_id: ID del nuevo producto
        
        Returns:
            Dict con resultado del cambio
        """
        try:
            shelf = db.query(Shelf).filter(Shelf.id == shelf_id).first()
            if not shelf:
                return {"error": "Shelf not found", "status": "error"}
            
            new_product = db.query(Product).filter(Product.id == new_product_id).first()
            if not new_product:
                return {"error": "Product not found", "status": "error"}
            
            if not new_product.unit_weight_grams or new_product.unit_weight_grams == 0:
                return {"error": "Product unit weight not set", "status": "error"}
            
            # Obtener peso actual de InfluxDB
            current_weight = self.get_current_weight(str(shelf_id))
            if current_weight is None:
                return {
                    "error": "Shelf is offline",
                    "status": "offline"
                }
            
            # Calcular unidades con el NUEVO producto
            unit_weight = float(new_product.unit_weight_grams)
            units_with_new_product = int(current_weight / unit_weight)
            
            # Actualizar shelf
            old_product_name = shelf.product.name if shelf.product else "Unknown"
            shelf.product_id = new_product_id
            shelf.last_recorded_units = units_with_new_product
            shelf.last_reading_at = datetime.utcnow()
            
            db.commit()
            
            logger.info(
                f"✅ Producto cambiado en estante '{shelf.name}': "
                f"'{old_product_name}' → '{new_product.name}' "
                f"(Unidades: {units_with_new_product})"
            )
            
            return {
                "status": "success",
                "shelf_id": str(shelf_id),
                "shelf_name": shelf.name,
                "old_product": old_product_name,
                "new_product": new_product.name,
                "current_weight_grams": current_weight,
                "unit_weight_grams": unit_weight,
                "units": units_with_new_product
            }
        
        except Exception as e:
            logger.error(f"[InfluxDetector] Error cambiando producto: {str(e)}")
            db.rollback()
            return {"error": str(e), "status": "error"}
    
    def close(self):
        """Cierra la conexión a InfluxDB"""
        try:
            if self.is_connected:
                self.client.close()
                logger.info("[InfluxDetector] Conexión cerrada")
        except Exception as e:
            logger.error(f"[InfluxDetector] Error cerrando: {str(e)}")
