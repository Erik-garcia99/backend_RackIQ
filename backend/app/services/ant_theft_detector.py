"""
Servicio de detección de anomalías - Robo Hormiga

Detecta patrones sospechosos de pérdida de inventario que sugieren robo.
"""

from sqlalchemy.orm import Session
from sqlalchemy.sql import func
from datetime import datetime, timedelta
from typing import Optional, Tuple
from uuid import UUID
import statistics

from app.models.rpi_models import (
    Shelf, WeightReading, StockEvent, AnomalyEvent, Alert, Store Hours
)


class AntTheftDetector:
    """Detecta patrones de robo hormiga"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def analyze_shelf(self, shelf_id: UUID) -> Optional[dict]:
        """
        Analiza un estante para detectar anomalías.
        Retorna None si todo es normal, o un dict con detalles de la anomalía.
        """
        shelf = self.db.query(Shelf).filter(Shelf.id == shelf_id).first()
        if not shelf or not shelf.is_active:
            return None
        
        # Obtener lecturas de los últimos 7 días
        since = datetime.utcnow() - timedelta(days=7)
        readings = self.db.query(WeightReading).filter(
            WeightReading.shelf_id == shelf_id,
            WeightReading.recorded_at >= since
        ).order_by(WeightReading.recorded_at.desc()).limit(1000).all()
        
        if len(readings) < 10:  # No hay suficientes datos
            return None
        
        # Invertir para análisis cronológico
        readings = list(reversed(readings))
        
        # 1. Detectar tasa de pérdida constante
        losses = self._calculate_losses(readings)
        if not losses:
            return None
        
        ant_theft_score, reason = self._evaluate_ant_theft(
            shelf, losses, readings
        )
        
        if ant_theft_score > 0.6:  # Threshold de confianza
            return {
                "anomaly_type": "ant_theft",
                "confidence_score": ant_theft_score,
                "reason": reason,
                "loss_rate_grams_per_day": self._calculate_loss_rate(losses),
                "out_of_hours": self._is_out_of_hours(shelf),
                "recommendation": self._get_recommendation(ant_theft_score)
            }
        
        return None
    
    def _calculate_losses(self, readings: list) -> list:
        """Calcula pérdidas entre lecturas consecutivas"""
        losses = []
        
        for i in range(1, len(readings)):
            prev_weight = readings[i-1].net_weight_grams
            curr_weight = readings[i].net_weight_grams
            
            # Si hay pérdida (peso disminuye sin ser reabastecimiento)
            if prev_weight > curr_weight:
                loss = prev_weight - curr_weight
                losses.append({
                    "weight_loss": loss,
                    "timestamp": readings[i].recorded_at,
                    "interval_minutes": (
                        readings[i].recorded_at - readings[i-1].recorded_at
                    ).total_seconds() / 60
                })
        
        return losses
    
    def _evaluate_ant_theft(self, shelf, losses: list, readings: list) -> Tuple[float, str]:
        """
        Evalúa la probabilidad de robo hormiga basado en:
        - Frecuencia y consistencia de pequeñas pérdidas
        - Patrones fuera de horario
        - Falta de patrones de venta normal
        """
        if not losses:
            return 0.0, "Sin pérdidas detectadas"
        
        score = 0.0
        reasons = []
        
        # Análisis 1: ¿Son pérdidas pequeñas y frecuentes?
        small_losses = [l for l in losses if l["weight_loss"] < 500]  # Menos de 500g
        if len(small_losses) / len(losses) > 0.7:  # >70% pérdidas pequeñas
            score += 0.25
            reasons.append("Múltiples pérdidas pequeñas y consistentes")
        
        # Análisis 2: ¿Hay variabilidad en las pérdidas? (robo hormiga es constante)
        if len(losses) > 5:
            loss_amounts = [l["weight_loss"] for l in losses]
            std_dev = statistics.stdev(loss_amounts)
            mean = statistics.mean(loss_amounts)
            
            # Coeficiente de variación bajo = robo hormiga (consistente)
            cv = std_dev / mean if mean > 0 else 0
            if cv < 0.3:  # Baja variabilidad
                score += 0.25
                reasons.append("Pérdidas muy consistentes (patrón sospechoso)")
        
        # Análisis 3: ¿Ocurre fuera de horario?
        out_of_hours_count = sum(
            1 for l in losses 
            if self._is_timestamp_out_of_hours(l["timestamp"], shelf)
        )
        if len(losses) > 0 and (out_of_hours_count / len(losses)) > 0.5:
            score += 0.20
            reasons.append("Pérdidas principalmente fuera de horario")
        
        # Análisis 4: Tasa de pérdida por hora
        total_loss = sum(l["weight_loss"] for l in losses)
        total_minutes = (
            readings[-1].recorded_at - readings[0].recorded_at
        ).total_seconds() / 60
        
        if total_minutes > 0:
            loss_rate_per_hour = (total_loss / total_minutes) * 60
            if 10 < loss_rate_per_hour < 500:  # Rango sospechoso
                score += 0.30
                reasons.append(f"Tasa de pérdida sospechosa: {loss_rate_per_hour:.1f}g/hora")
        
        return min(score, 1.0), "; ".join(reasons)
    
    def _calculate_loss_rate(self, losses: list) -> float:
        """Calcula la tasa promedio de pérdida en gramos por día"""
        if not losses:
            return 0.0
        
        total_loss = sum(l["weight_loss"] for l in losses)
        if losses:
            total_minutes = sum(l["interval_minutes"] for l in losses)
            if total_minutes > 0:
                return (total_loss / total_minutes) * 60 * 24  # Convertir a gramos/día
        
        return 0.0
    
    def _is_out_of_hours(self, shelf: Shelf) -> bool:
        """Verifica si es fuera del horario de operación"""
        now = datetime.utcnow()
        day_of_week = now.weekday()
        current_time = now.time()
        
        # TODO: Obtener horario de la sucursal desde store_hours
        # Por ahora, asumir horario estándar 6:00 - 22:00
        opening = 6
        closing = 22
        
        is_open = opening <= now.hour < closing
        return not is_open
    
    def _is_timestamp_out_of_hours(self, timestamp, shelf: Shelf) -> bool:
        """Verifica si un timestamp es fuera de horario"""
        day_of_week = timestamp.weekday()
        hour = timestamp.hour
        
        # TODO: Obtener horario de la sucursal
        opening = 6
        closing = 22
        
        return not (opening <= hour < closing)
    
    def _get_recommendation(self, confidence_score: float) -> str:
        """Genera una recomendación basada en el score"""
        if confidence_score > 0.8:
            return "CRÍTICO: Revisar inmediatamente. Evidencia muy fuerte de robo."
        elif confidence_score > 0.7:
            return "ALTO: Investigar posible robo hormiga. Aumentar vigilancia."
        elif confidence_score > 0.6:
            return "MEDIO: Anomalía sospechosa. Revisar patrones de inventario."
        else:
            return "Posible anomalía. Monitorear continuamente."


def detect_weight_anomalies(db: Session, shelf_id: UUID) -> Optional[AnomalyEvent]:
    """
    Función pública para detectar anomalías en un estante.
    Si se detecta, crea un evento de anomalía y una alerta.
    """
    detector = AntTheftDetector(db)
    anomaly_data = detector.analyze_shelf(shelf_id)
    
    if not anomaly_data:
        return None
    
    shelf = db.query(Shelf).filter(Shelf.id == shelf_id).first()
    
    # Crear evento de anomalía
    anomaly = AnomalyEvent(
        shelf_id=shelf_id,
        anomaly_type=anomaly_data["anomaly_type"],
        weight_delta_grams=anomaly_data.get("loss_rate_grams_per_day"),
        rate_per_minute=0,
        out_of_hours=anomaly_data.get("out_of_hours", False),
        confidence_score=anomaly_data["confidence_score"],
        status="open"
    )
    db.add(anomaly)
    
    # Crear alerta
    alert = Alert(
        shelf_id=shelf_id,
        branch_id=shelf.branch_id,
        alert_type="theft",
        status="open",
        metadata=f"Sospecha de robo: {anomaly_data['reason']}"
    )
    db.add(alert)
    db.commit()
    
    return anomaly
