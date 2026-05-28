"""
celery_app.py - Configuración de Celery para tareas asincrónicas
"""

from celery import Celery
from app.core.config import settings

# Crear instancia de Celery
celery_app = Celery(
    "rackiq",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND
)

# Configuración de Celery
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # Configuración de reintentos
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    # Beat schedule para tareas periódicas
    beat_schedule={
        "detect-inventory-movements": {
            "task": "app.workers.inventory_tasks.detect_all_movements_task",
            "schedule": 30.0,  # Cada 30 segundos
        },
    }
)

@celery_app.task(bind=True)
def debug_task(self):
    print(f"Request: {self.request!r}")
