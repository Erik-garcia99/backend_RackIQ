import uuid
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from sqlalchemy.sql import func
from typing import List, Optional
from datetime import datetime

from app.db.database import get_db
from app.models.rpi_models import (
    Gateway, Esp32Node, Shelf, WeightReading, 
    StockEvent, AnomalyEvent, Alert, InfluxConfig
)
from app.models.branch import Branch
from app.models.organization_token import OrganizationToken
from pydantic import BaseModel
from uuid import UUID

router = APIRouter(prefix="/rpi", tags=["rpi"])


# ============ SCHEMAS ============

class RpiRegisterRequest(BaseModel):
    mac: str  # MAC address de la RPI
    branch_code: str  # Código de la sucursal
    firmware_version: Optional[str] = None


class RpiRegisterResponse(BaseModel):
    gateway_id: UUID
    rpi_identifier: str
    branch_id: UUID
    message: str


class WeightReadingRequest(BaseModel):
    shelf_id: str  # ID del estante
    raw_weight_grams: float
    net_weight_grams: float


class AnomalyEventRequest(BaseModel):
    shelf_id: str
    anomaly_type: str  # ant_theft, weight_jump, missing_product
    weight_delta_grams: Optional[float] = None
    rate_per_minute: Optional[float] = None
    out_of_hours: bool = False
    confidence_score: Optional[float] = None


class Esp32RegisterRequest(BaseModel):
    mac_address: str
    hx711_channel: int
    gateway_id: UUID
    branch_id: UUID


class Esp32RegisterResponse(BaseModel):
    esp32_node_id: UUID
    shelf_id: UUID
    hx711_channel: int
    message: str


class InfluxConfigRequest(BaseModel):
    influx_url: str
    influx_token: str
    influx_org: str
    influx_bucket: str
    grafana_url: Optional[str] = None
    grafana_api_key: Optional[str] = None


class InfluxConfigResponse(BaseModel):
    id: UUID
    gateway_id: UUID
    influx_url: str
    influx_org: str
    influx_bucket: str
    grafana_url: Optional[str] = None
    is_active: bool

    class Config:
        from_attributes = True


# ============ HELPERS ============

def extract_token(authorization: Optional[str]) -> str:
    """Extrae el token del header Authorization"""
    if not authorization:
        raise HTTPException(status_code=401, detail="Token no proporcionado")
    
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Formato de token inválido")
    
    return parts[1]


def verify_organization_token(db: Session, token: str) -> OrganizationToken:
    """Valida que el token exista y esté activo"""
    org_token = db.query(OrganizationToken).filter(
        OrganizationToken.token == token,
        OrganizationToken.is_active == True
    ).first()
    
    if not org_token:
        raise HTTPException(status_code=401, detail="Token de organización no válido o inactivo")
    
    return org_token


# ============ ENDPOINTS ============

@router.post("/register", status_code=201, response_model=RpiRegisterResponse)
def register_rpi(
    body: RpiRegisterRequest,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """
    Registra una RPI nueva en el sistema.
    
    Flujo:
    1. Valida el token de organización
    2. Busca la sucursal por branch_code
    3. Crea o actualiza el gateway con la MAC address
    4. Retorna gateway_id y rpi_identifier
    """
    
    # 1. Validar token
    token = extract_token(authorization)
    org_token = verify_organization_token(db, token)
    
    # 2. Buscar la sucursal por branch_code
    branch = db.query(Branch).filter(
        Branch.branch_code == body.branch_code,
        Branch.organization_id == org_token.organization_id,
        Branch.is_active == True
    ).first()
    
    if not branch:
        raise HTTPException(
            status_code=404,
            detail=f"Sucursal con código '{body.branch_code}' no encontrada o inactiva"
        )
    
    # 3. Buscar o crear gateway (solo uno por sucursal)
    gateway = db.query(Gateway).filter(
        Gateway.branch_id == branch.id
    ).first()
    
    if gateway:
        # Actualizar gateway existente
        gateway.mac_address = body.mac
        gateway.firmware_version = body.firmware_version
        gateway.last_heartbeat_at = func.now()
        gateway.is_online = True
    else:
        # Crear gateway nuevo
        rpi_identifier = f"RPI-{uuid.uuid4().hex[:12].upper()}"
        
        # Verificar que el identificador sea único
        while db.query(Gateway).filter(Gateway.rpi_identifier == rpi_identifier).first():
            rpi_identifier = f"RPI-{uuid.uuid4().hex[:12].upper()}"
        
        gateway = Gateway(
            branch_id=branch.id,
            mac_address=body.mac,
            rpi_identifier=rpi_identifier,
            firmware_version=body.firmware_version,
            is_online=True,
            is_active=True,
            last_heartbeat_at=func.now()
        )
        db.add(gateway)
    
    db.commit()
    db.refresh(gateway)
    
    # Actualizar last_used_at del token
    org_token.last_used_at = func.now()
    db.commit()
    
    return RpiRegisterResponse(
        gateway_id=gateway.id,
        rpi_identifier=gateway.rpi_identifier,
        branch_id=branch.id,
        message="RPI registrada exitosamente"
    )


@router.post("/weight-readings")
def receive_weight_reading(
    body: WeightReadingRequest,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """
    Recibe lecturas de peso desde la RPI.
    La RPI envía lecturas cada minuto.
    """
    token = extract_token(authorization)
    org_token = verify_organization_token(db, token)
    
    try:
        shelf_id = uuid.UUID(body.shelf_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="shelf_id inválido")
    
    # Validar que el estante existe
    shelf = db.query(Shelf).filter(Shelf.id == shelf_id).first()
    if not shelf:
        raise HTTPException(status_code=404, detail="Estante no encontrado")
    
    # Crear registro de lectura
    reading = WeightReading(
        gateway_id=shelf.gateway_id,
        shelf_id=shelf_id,
        raw_weight_grams=body.raw_weight_grams,
        net_weight_grams=body.net_weight_grams
    )
    db.add(reading)
    db.commit()
    
    return {"status": "received", "reading_id": str(reading.id)}


@router.post("/anomalies")
def report_anomaly(
    body: AnomalyEventRequest,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """
    Reporta anomalías detectadas (robo hormiga).
    
    Tipos de anomalía:
    - ant_theft: pérdida constante pequeña
    - weight_jump: cambio abrupto de peso
    - missing_product: producto desaparece
    """
    token = extract_token(authorization)
    org_token = verify_organization_token(db, token)
    
    try:
        shelf_id = uuid.UUID(body.shelf_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="shelf_id inválido")
    
    # Validar que el estante existe
    shelf = db.query(Shelf).filter(Shelf.id == shelf_id).first()
    if not shelf:
        raise HTTPException(status_code=404, detail="Estante no encontrado")
    
    # Crear evento de anomalía
    anomaly = AnomalyEvent(
        shelf_id=shelf_id,
        anomaly_type=body.anomaly_type,
        weight_delta_grams=body.weight_delta_grams,
        rate_per_minute=body.rate_per_minute,
        out_of_hours=body.out_of_hours,
        confidence_score=body.confidence_score,
        status="open"
    )
    db.add(anomaly)
    
    # Crear alerta asociada
    alert = Alert(
        shelf_id=shelf_id,
        branch_id=shelf.branch_id,
        alert_type="anomaly",
        status="open"
    )
    db.add(alert)
    db.commit()
    
    return {
        "status": "created",
        "anomaly_id": str(anomaly.id),
        "alert_id": str(alert.id),
        "message": "Anomalía reportada"
    }


@router.post("/esp32/register", status_code=201, response_model=Esp32RegisterResponse)
def register_esp32(
    body: Esp32RegisterRequest,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """
    Registra un ESP32 en el sistema.
    
    Crea o actualiza:
    - Esp32Node (con MAC address único)
    - Shelf (automáticamente asignado a un channel HX711)
    """
    token = extract_token(authorization)
    org_token = verify_organization_token(db, token)
    
    # Validar gateway
    gateway = db.query(Gateway).filter(Gateway.id == body.gateway_id).first()
    if not gateway:
        raise HTTPException(status_code=404, detail="Gateway no encontrado")
    
    # Validar branch
    branch = db.query(Branch).filter(Branch.id == body.branch_id).first()
    if not branch:
        raise HTTPException(status_code=404, detail="Rama no encontrada")
    
    # Verificar permisos: el branch debe pertenecer a la organización del token
    if branch.organization_id != org_token.organization_id:
        raise HTTPException(status_code=403, detail="No tienes acceso a esta rama")
    
    # Buscar o crear ESP32Node
    esp32_node = db.query(Esp32Node).filter(
        Esp32Node.mac_address == body.mac_address
    ).first()
    
    if not esp32_node:
        # Crear nuevo ESP32Node
        esp32_node = Esp32Node(
            gateway_id=body.gateway_id,
            mac_address=body.mac_address,
            firmware_version="3.0",
            is_online=False
        )
        db.add(esp32_node)
        db.flush()  # Para obtener el ID sin hacer commit
    else:
        # Actualizar ESP32Node existente
        esp32_node.gateway_id = body.gateway_id
        esp32_node.firmware_version = "3.0"
    
    # Buscar o crear Shelf para este canal HX711
    shelf = db.query(Shelf).filter(
        Shelf.esp32_node_id == esp32_node.id,
        Shelf.hx711_channel == body.hx711_channel
    ).first()
    
    if not shelf:
        # Crear nuevo Shelf
        shelf = Shelf(
            esp32_node_id=esp32_node.id,
            branch_id=body.branch_id,
            hx711_channel=body.hx711_channel,
            name=f"Estante {body.mac_address[-5:].upper()} Ch{body.hx711_channel}",
            is_active=True
        )
        db.add(shelf)
    else:
        # Actualizar Shelf existente
        shelf.is_active = True
    
    db.commit()
    db.refresh(esp32_node)
    db.refresh(shelf)
    
    return Esp32RegisterResponse(
        esp32_node_id=esp32_node.id,
        shelf_id=shelf.id,
        hx711_channel=body.hx711_channel,
        message="ESP32 registrado exitosamente"
    )


@router.post("/anomalies")


@router.get("/gateway/{gateway_id}/config")
def get_gateway_config(
    gateway_id: str,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """
    Obtiene la configuración del gateway (InfluxDB, etc.)
    """
    token = extract_token(authorization)
    org_token = verify_organization_token(db, token)
    
    try:
        gw_id = uuid.UUID(gateway_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="gateway_id inválido")
    
    gateway = db.query(Gateway).filter(Gateway.id == gw_id).first()
    if not gateway:
        raise HTTPException(status_code=404, detail="Gateway no encontrado")
    
    # Validar que el gateway pertenece a la organización
    branch = db.query(Branch).filter(Branch.id == gateway.branch_id).first()
    if branch.organization_id != org_token.organization_id:
        raise HTTPException(status_code=403, detail="No tienes acceso a este gateway")
    
    influx_config = db.query(InfluxConfig).filter(InfluxConfig.gateway_id == gw_id).first()
    
    return {
        "gateway_id": str(gateway.id),
        "rpi_identifier": gateway.rpi_identifier,
        "branch_id": str(gateway.branch_id),
        "influx_config": influx_config.dict() if influx_config else None
    }


@router.post("/gateway/{gateway_id}/heartbeat")
def gateway_heartbeat(
    gateway_id: str,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """
    Recibe heartbeat de una RPI para indicar que está en línea
    """
    token = extract_token(authorization)
    org_token = verify_organization_token(db, token)
    
    try:
        gw_id = uuid.UUID(gateway_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="gateway_id inválido")
    
    gateway = db.query(Gateway).filter(Gateway.id == gw_id).first()
    if not gateway:
        raise HTTPException(status_code=404, detail="Gateway no encontrado")
    
    # Verificar permisos
    branch = db.query(Branch).filter(Branch.id == gateway.branch_id).first()
    if branch.organization_id != org_token.organization_id:
        raise HTTPException(status_code=403, detail="No tienes acceso a este gateway")
    
    # Actualizar último heartbeat
    gateway.last_heartbeat_at = func.now()
    gateway.is_online = True
    db.commit()
    
    return {
        "status": "ok",
        "gateway_id": str(gateway.id),
        "rpi_identifier": gateway.rpi_identifier,
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get("/gateway/{gateway_id}/shelves", response_model=List[dict])
def get_gateway_shelves(
    gateway_id: str,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """
    Obtiene todos los estantes asociados a un gateway
    """
    token = extract_token(authorization)
    org_token = verify_organization_token(db, token)
    
    try:
        gw_id = uuid.UUID(gateway_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="gateway_id inválido")
    
    gateway = db.query(Gateway).filter(Gateway.id == gw_id).first()
    if not gateway:
        raise HTTPException(status_code=404, detail="Gateway no encontrado")
    
    # Verificar permisos
    branch = db.query(Branch).filter(Branch.id == gateway.branch_id).first()
    if branch.organization_id != org_token.organization_id:
        raise HTTPException(status_code=403, detail="No tienes acceso a este gateway")
    
    # Obtener estantes
    shelves = db.query(Shelf).filter(
        Shelf.gateway_id == gw_id,
        Shelf.is_active == True
    ).all()
    
    return [
        {
            "id": str(shelf.id),
            "name": shelf.name,
            "hx711_channel": shelf.hx711_channel,
            "product_id": str(shelf.product_id) if shelf.product_id else None,
            "max_capacity_grams": float(shelf.max_capacity_grams) if shelf.max_capacity_grams else None,
            "low_stock_threshold_kg": float(shelf.low_stock_threshold_kg) if shelf.low_stock_threshold_kg else None,
        }
        for shelf in shelves
    ]


@router.post("/gateway/{gateway_id}/update-status")
def update_gateway_status(
    gateway_id: str,
    body: dict,  # {ip_address, wifi_rssi, hostname}
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """
    Actualiza el estado de conectividad del gateway
    """
    token = extract_token(authorization)
    org_token = verify_organization_token(db, token)
    
    try:
        gw_id = uuid.UUID(gateway_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="gateway_id inválido")
    
    gateway = db.query(Gateway).filter(Gateway.id == gw_id).first()
    if not gateway:
        raise HTTPException(status_code=404, detail="Gateway no encontrado")
    
    # Actualizar estado
    gateway.ip_address = body.get("ip_address")
    gateway.wifi_rssi = body.get("wifi_rssi")
    gateway.hostname = body.get("hostname")
    gateway.is_online = True
    gateway.last_heartbeat_at = func.now()
    db.commit()
    
    return {"status": "updated", "gateway_id": str(gateway.id)}
