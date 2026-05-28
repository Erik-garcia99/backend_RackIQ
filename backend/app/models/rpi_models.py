import uuid
from sqlalchemy import Column, Text, TIMESTAMP, ForeignKey, Numeric, Integer, Boolean, func, SmallInteger
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.models.base import Base


class Gateway(Base):
    """Raspberry Pi Gateway - representa cada RPI en una sucursal"""
    __tablename__ = "gateway"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    branch_id = Column(UUID(as_uuid=True), ForeignKey("branch.id", ondelete="CASCADE"), nullable=False)
    rpi_identifier = Column(Text, nullable=False, unique=True)  # ej: RPI-ABC123DEF456
    mac_address = Column(Text, unique=True)  # MAC address de la RPI
    firmware_version = Column(Text)
    hostname = Column(Text)
    ip_address = Column(Text)
    wifi_rssi = Column(Numeric(6, 2))
    last_heartbeat_at = Column(TIMESTAMP(timezone=True))
    is_online = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())

    branch = relationship("Branch", back_populates="gateway")
    esp32_nodes = relationship("Esp32Node", back_populates="gateway")
    # TODO: Descomentar cuando influx_config table exista en Supabase
    # influx_config = relationship("InfluxConfig", back_populates="gateway", uselist=False)


class Esp32Node(Base):
    """Nodo ESP32 - sensor conectado a la RPI"""
    __tablename__ = "esp32_node"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    gateway_id = Column(UUID(as_uuid=True), ForeignKey("gateway.id", ondelete="CASCADE"), nullable=False)
    mac_address = Column(Text, nullable=False, unique=True)
    name = Column(Text)  # Nombre personalizado del nodo
    firmware_version = Column(Text)
    last_heartbeat_at = Column(TIMESTAMP(timezone=True))
    is_online = Column(Boolean, default=False)
    wifi_rssi = Column(Numeric(6, 2))
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())

    gateway = relationship("Gateway", back_populates="esp32_nodes")
    shelves = relationship("Shelf", back_populates="esp32_node")


class Shelf(Base):
    """Estante con sensor HX711 - representa una báscula en una sucursal"""
    __tablename__ = "shelf"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    branch_id = Column(UUID(as_uuid=True), ForeignKey("branch.id", ondelete="CASCADE"), nullable=False)
    product_id = Column(UUID(as_uuid=True), ForeignKey("product.id", ondelete="SET NULL"), nullable=True)
    esp32_node_id = Column(UUID(as_uuid=True), ForeignKey("esp32_node.id", ondelete="SET NULL"), nullable=True)
    
    name = Column(Text, nullable=False)  # ej: "Estante Carnes A"
    hx711_channel = Column(SmallInteger, nullable=False)  # Canal del HX711 (0-3)
    hx711_pin = Column(Integer, nullable=False)  # Pin del ESP32 (4, 22, 23, 12, 14)
    hx711_position = Column(SmallInteger, nullable=False)  # Posición (1-5) para orden
    is_connected = Column(Boolean, default=False)  # Si el HX711 está conectado
    last_reading_at = Column(TIMESTAMP(timezone=True))  # Última lectura recibida
    
    tare_weight_grams = Column(Numeric(10, 4), default=0)
    scale_factor = Column(Numeric(14, 8), default=1)
    max_capacity_grams = Column(Numeric(10, 4))
    low_stock_threshold_pct = Column(Numeric(5, 2))
    low_stock_threshold_kg = Column(Numeric(10, 4))
    alert_mode = Column(Text, default="auto")  # auto, manual, disabled
    last_calibrated_at = Column(TIMESTAMP(timezone=True))
    is_active = Column(Boolean, default=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())

    esp32_node = relationship("Esp32Node", back_populates="shelves")
    weight_readings = relationship("WeightReading", back_populates="shelf")
    stock_events = relationship("StockEvent", back_populates="shelf")
    anomaly_events = relationship("AnomalyEvent", back_populates="shelf")
    alerts = relationship("Alert", back_populates="shelf")


class WeightReading(Base):
    """Lecturas de peso del HX711"""
    __tablename__ = "weight_reading"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    shelf_id = Column(UUID(as_uuid=True), ForeignKey("shelf.id", ondelete="CASCADE"), nullable=False)
    raw_weight_grams = Column(Numeric(10, 4), nullable=False)
    net_weight_grams = Column(Numeric(10, 4), nullable=False)
    recorded_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

    shelf = relationship("Shelf", back_populates="weight_readings")


class StockEvent(Base):
    """Evento de cambio de inventario (venta, reabastecimiento)"""
    __tablename__ = "stock_event"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    shelf_id = Column(UUID(as_uuid=True), ForeignKey("shelf.id", ondelete="CASCADE"), nullable=False)
    event_type = Column(Text, nullable=False)  # in, out, adjustment
    weight_delta_grams = Column(Numeric(10, 4))
    units_delta = Column(Numeric(10, 4))
    weight_before = Column(Numeric(10, 4))
    weight_after = Column(Numeric(10, 4))
    occurred_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    is_consolidated = Column(Boolean, default=False)

    shelf = relationship("Shelf", back_populates="stock_events")


class AnomalyEvent(Base):
    """Detectar anomalías - robo hormiga"""
    __tablename__ = "anomaly_event"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    shelf_id = Column(UUID(as_uuid=True), ForeignKey("shelf.id", ondelete="CASCADE"), nullable=False)
    anomaly_type = Column(Text, nullable=False)  # ant_theft, weight_jump, missing_product
    weight_delta_grams = Column(Numeric(10, 4))
    rate_per_minute = Column(Numeric(10, 4))
    out_of_hours = Column(Boolean, default=False)
    status = Column(Text, default="open")  # open, acknowledged, resolved
    detected_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    confidence_score = Column(Numeric(5, 4))

    shelf = relationship("Shelf", back_populates="anomaly_events")


class Alert(Base):
    """Alertas generadas (bajo stock, robo, etc.)"""
    __tablename__ = "alert"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    shelf_id = Column(UUID(as_uuid=True), ForeignKey("shelf.id", ondelete="SET NULL"), nullable=True)
    branch_id = Column(UUID(as_uuid=True), ForeignKey("branch.id", ondelete="CASCADE"), nullable=False)
    alert_type = Column(Text, nullable=False)  # low_stock, theft, anomaly, offline
    status = Column(Text, default="open")  # open, acknowledged, resolved
    alert_metadata = Column(JSONB, name="metadata", nullable=True)  # Metadatos adicionales en formato JSON
    triggered_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    resolved_at = Column(TIMESTAMP(timezone=True))
    resolved_by = Column(UUID(as_uuid=True), nullable=True)  # User ID who resolved it

    shelf = relationship("Shelf", back_populates="alerts")

class PendingCommand(Base):
    """Comando pendiente de ejecución por la RPI sobre un estante"""
    __tablename__ = "pending_commands"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    shelf_id = Column(UUID(as_uuid=True), ForeignKey("shelf.id", ondelete="CASCADE"), nullable=False)
    command_type = Column(Text, nullable=False)  # 'tare' o 'scale'
    reference_weight_kg = Column(Numeric(10, 4))  # solo para scale
    status = Column(Text, default="pending")  # pending, executed, failed
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    executed_at = Column(TIMESTAMP(timezone=True))

    # relaciones
    shelf = relationship("Shelf")


class InfluxConfig(Base):
    """Credenciales InfluxDB para cada RPI"""
    __tablename__ = "influx_config"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    gateway_id = Column(UUID(as_uuid=True), ForeignKey("gateway.id", ondelete="CASCADE"), nullable=False, unique=True)
    influx_url = Column(Text, nullable=False)
    influx_token = Column(Text, nullable=False)
    influx_org = Column(Text, nullable=False)
    influx_bucket = Column(Text, nullable=False)
    grafana_url = Column(Text)
    grafana_api_key = Column(Text)
    is_active = Column(Boolean, default=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())

    # TODO: Descomentar cuando gateway pueda tener relación a esta tabla
    # gateway = relationship("Gateway", back_populates="influx_config")
    
    
class SupplierReceipt(Base):
    """Registro de mercancía recibida por un proveedor"""
    __tablename__ = "supplier_receipt"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    shelf_id = Column(UUID(as_uuid=True), ForeignKey("shelf.id", ondelete="SET NULL"), nullable=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("user.id", ondelete="SET NULL"), nullable=True)
    declared_weight_grams = Column(Numeric(10, 4))
    measured_weight_grams = Column(Numeric(10, 4))
    discrepancy_grams = Column(Numeric(10, 4))
    status = Column(Text, default="pending", nullable=False)
    received_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

    # Relación con el estante (opcional, pero recomendada)
    shelf = relationship("Shelf", backref="supplier_receipts")
