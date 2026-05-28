"""
workers/__init__.py - Inicialización del módulo de workers
"""

from app.workers.celery_app import celery_app

__all__ = ["celery_app"]
