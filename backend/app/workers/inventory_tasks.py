"""
inventory_tasks.py - Tareas Celery para detección de movimientos de inventario
"""

import logging
from celery import shared_task
from app.db.session import SessionLocal
from app.services.influx_detector import InfluxDetector

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def detect_all_movements_task(self):
    """
    Tarea Celery que detecta movimientos en TODOS los estantes
    
    Se ejecuta cada 30 segundos automáticamente
    """
    db = SessionLocal()
    
    try:
        detector = InfluxDetector()
        
        if not detector.is_connected:
            logger.warning("[Task] InfluxDB no conectado")
            return {
                "status": "error",
                "message": "InfluxDB not connected"
            }
        
        # Detectar movimientos en todos los estantes
        result = detector.detect_all_movements(db)
        
        logger.info(
            f"[Task] Detección completada: "
            f"{result.get('total_shelves')} estantes, "
            f"{result.get('movements_detected')} movimientos detectados"
        )
        
        return result
    
    except Exception as e:
        logger.error(f"[Task] Error en detección de movimientos: {str(e)}")
        
        # Reintentar después de 10 segundos
        raise self.retry(exc=e, countdown=10)
    
    finally:
        db.close()
        detector.close()
