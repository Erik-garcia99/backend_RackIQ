import uuid
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from sqlalchemy.sql import func
from typing import List, Optional
from datetime import datetime
from app.core.security import get_current_user
from app.models.user import User
from app.db.database import get_db
from app.models.rpi_models import (
    Gateway, Esp32Node, PendingCommand, Shelf, WeightReading, 
    StockEvent, AnomalyEvent, Alert
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


class HX711StatusResponse(BaseModel):
    pin: int  # Pin del ESP32 (4, 22, 23, 12, 14)
    position: int  # Posición (1-5)
    shelf_id: UUID
    is_connected: bool
    shelf_name: str


class Esp32RegisterRequest(BaseModel):
    mac_address: str
    gateway_id: UUID
    branch_id: UUID
    hx711_status: List[dict]  # Lista con {pin: int, is_connected: bool} para cada HX711


class Esp32RegisterResponse(BaseModel):
    esp32_node_id: UUID
    node_name: str
    message: str
    hx711_list: List[HX711StatusResponse]


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
    También actualiza el estado de conectividad del estante.
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
        shelf_id=shelf_id,
        raw_weight_grams=body.raw_weight_grams,
        net_weight_grams=body.net_weight_grams
    )
    db.add(reading)
    
    # Actualizar estado de conectividad del estante
    shelf.is_connected = True
    shelf.last_reading_at = func.now()
    
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
    Registra un ESP32 en el sistema con sus 5 HX711s asociados.
    
    Crea automáticamente:
    - Esp32Node (nodo ESP32)
    - 5 Shelf (uno para cada HX711 en pins 4, 22, 23, 12, 14)
    
    Flujo:
    1. Valida el token y permisos
    2. Busca o crea el Esp32Node
    3. Crea/actualiza 5 Shelf con los HX711s
    4. Retorna información de conectividad de cada HX711
    """
    token = extract_token(authorization)
    org_token = verify_organization_token(db, token)
    
    # Validar gateway y branch
    gateway = db.query(Gateway).filter(Gateway.id == body.gateway_id).first()
    if not gateway:
        raise HTTPException(status_code=404, detail="Gateway no encontrado")
    
    branch = db.query(Branch).filter(Branch.id == body.branch_id).first()
    if not branch:
        raise HTTPException(status_code=404, detail="Rama no encontrada")
    
    if branch.organization_id != org_token.organization_id:
        raise HTTPException(status_code=403, detail="No tienes acceso a esta rama")
    
    # Definir los 5 HX711s con sus pines
    hx711_pins = [
        {"pin": 4, "position": 1},
        {"pin": 22, "position": 2},
        {"pin": 23, "position": 3},
        {"pin": 12, "position": 4},
        {"pin": 14, "position": 5},
    ]
    
    # Crear o actualizar ESP32Node
    esp32_node = db.query(Esp32Node).filter(
        Esp32Node.mac_address == body.mac_address
    ).first()

    if not esp32_node:
        node_name = f"Nodo-{body.mac_address[-4:].upper()}"
        esp32_node = Esp32Node(
            gateway_id=body.gateway_id,
            mac_address=body.mac_address,
            name=node_name,
            firmware_version="3.0",
            is_online=False,
            last_heartbeat_at=func.now()
        )
        db.add(esp32_node)
        db.flush()
    else:
        # Actualizar datos existentes
        esp32_node.gateway_id = body.gateway_id
        esp32_node.firmware_version = "3.0"
        esp32_node.last_heartbeat_at = func.now()
        # Si no tiene nombre, asignar uno por defecto
        if not esp32_node.name:
            esp32_node.name = f"Nodo-{body.mac_address[-4:].upper()}"
            db.add(esp32_node)
        db.flush()
    
    # Procesar status de HX711s desde el ESP32
    hx711_status_map = {}
    if body.hx711_status:
        for status in body.hx711_status:
            hx711_status_map[status.get("pin")] = status.get("is_connected", False)
    
    # Crear o actualizar los 5 Shelf (estantes)
    created_shelves = []
    
    for hx_config in hx711_pins:
        pin = hx_config["pin"]
        position = hx_config["position"]
        is_connected = hx711_status_map.get(pin, False)
        
        # Buscar si ya existe un Shelf para este pin
        shelf = db.query(Shelf).filter(
            Shelf.esp32_node_id == esp32_node.id,
            Shelf.hx711_pin == pin
        ).first()
        
        if not shelf:
            # Crear nuevo Shelf
            shelf_name = f"Estante {position}"
            shelf = Shelf(
                esp32_node_id=esp32_node.id,
                branch_id=body.branch_id,
                hx711_channel=position - 1,  # Canal 0-4
                hx711_pin=pin,
                hx711_position=position,
                name=shelf_name,
                is_connected=is_connected,
                is_active=True
            )
            db.add(shelf)
            db.flush()
        else:
            # Actualizar estado de conectividad
            shelf.is_connected = is_connected
            shelf.hx711_pin = pin
            shelf.hx711_position = position
            shelf.is_active = True
        
        created_shelves.append({
            "shelf": shelf,
            "is_connected": is_connected,
            "pin": pin,
            "position": position
        })
    
    db.commit()
    db.refresh(esp32_node)
    
    # Construir respuesta con información de HX711s
    hx711_list = [
        HX711StatusResponse(
            pin=item["pin"],
            position=item["position"],
            shelf_id=item["shelf"].id,
            is_connected=item["is_connected"],
            shelf_name=item["shelf"].name
        )
        for item in created_shelves
    ]
    
    return Esp32RegisterResponse(
        esp32_node_id=esp32_node.id,
        node_name=esp32_node.name,
        message="ESP32 registrado con sus 5 HX711s",
        hx711_list=hx711_list
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
    
    # TODO: Consultar InfluxConfig cuando la tabla exista en la BD
    # influx_config = db.query(InfluxConfig).filter(InfluxConfig.gateway_id == gw_id).first()
    
    return {
        "gateway_id": str(gateway.id),
        "rpi_identifier": gateway.rpi_identifier,
        "branch_id": str(gateway.branch_id),
        "influx_config": None  # Por implementar en futuro
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
    
    # Obtener estantes a través de los nodos ESP32
    esp32_nodes = db.query(Esp32Node).filter(
        Esp32Node.gateway_id == gw_id
    ).all()
    
    shelves_list = []
    for node in esp32_nodes:
        shelves = db.query(Shelf).filter(
            Shelf.esp32_node_id == node.id,
            Shelf.is_active == True
        ).all()
        for shelf in shelves:
            shelves_list.append({
                "id": str(shelf.id),
                "name": shelf.name,
                "hx711_channel": shelf.hx711_channel,
                "hx711_pin": shelf.hx711_pin,
                "hx711_position": shelf.hx711_position,
                "product_id": str(shelf.product_id) if shelf.product_id else None,
                "max_capacity_grams": float(shelf.max_capacity_grams) if shelf.max_capacity_grams else None,
                "low_stock_threshold_kg": float(shelf.low_stock_threshold_kg) if shelf.low_stock_threshold_kg else None,
                "is_connected": shelf.is_connected,
                "status": "online" if shelf.is_connected else "offline"
            })
    
    return shelves_list



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


# ============ ENDPOINTS PARA NODOS Y ESTANTES ============

@router.get("/branch/{branch_id}/esp32-nodes")
def get_branch_esp32_nodes(
    branch_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)  # Cambiar a autenticación de usuario
):
    """
    Obtiene todos los nodos ESP32 de una rama con sus estantes.
    Usado para mostrar nodos disponibles para configuración en el frontend.
    """
    # Validar que el branch existe
    try:
        br_id = uuid.UUID(branch_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="branch_id inválido")
    
    branch = db.query(Branch).filter(Branch.id == br_id).first()
    if not branch:
        raise HTTPException(status_code=404, detail="Rama no encontrada")
    
    # Verificar que el usuario pertenece a la misma organización
    if branch.organization_id != current_user.organization_id:
        raise HTTPException(status_code=403, detail="No tienes acceso a esta rama")
    
    # Obtener el gateway de esta rama
    gateway = db.query(Gateway).filter(Gateway.branch_id == br_id).first()
    if not gateway:
        return []
    
    gateway_ip = gateway.ip_address if gateway else None

    esp32_nodes = db.query(Esp32Node).filter(
        Esp32Node.gateway_id == gateway.id
    ).all()
    
    nodes_response = []
    for node in esp32_nodes:
        shelves = db.query(Shelf).filter(
            Shelf.esp32_node_id == node.id
        ).order_by(Shelf.hx711_position).all()
        
        shelves_data = [
            {
                "id": str(shelf.id),
                "name": shelf.name,
                "pin": shelf.hx711_pin,
                "position": shelf.hx711_position,
                "is_connected": shelf.is_connected,
                "last_reading_at": shelf.last_reading_at.isoformat() if shelf.last_reading_at else None,
                "status": "online" if shelf.is_connected else "offline"
            }
            for shelf in shelves
        ]
        
        nodes_response.append({
            "id": str(node.id),
            "mac_address": node.mac_address,
            "name": node.name,
            "is_online": node.is_online,
            "firmware_version": node.firmware_version,
            "shelves": shelves_data,
            "gateway_ip": gateway_ip
        })
    
    return nodes_response

@router.patch("/esp32-node/{node_id}/name")
def update_esp32_node_name(
    node_id: str,
    body: dict,  # {"name": "Nuevo nombre"}
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """
    Actualiza el nombre de un nodo ESP32
    """
    token = extract_token(authorization)
    org_token = verify_organization_token(db, token)
    
    try:
        n_id = uuid.UUID(node_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="node_id inválido")
    
    # Obtener nodo
    esp32_node = db.query(Esp32Node).filter(Esp32Node.id == n_id).first()
    if not esp32_node:
        raise HTTPException(status_code=404, detail="Nodo ESP32 no encontrado")
    
    # Validar permisos
    gateway = db.query(Gateway).filter(Gateway.id == esp32_node.gateway_id).first()
    branch = db.query(Branch).filter(Branch.id == gateway.branch_id).first()
    if branch.organization_id != org_token.organization_id:
        raise HTTPException(status_code=403, detail="No tienes acceso a este nodo")
    
    # Actualizar nombre
    new_name = body.get("name", "").strip()
    if not new_name:
        raise HTTPException(status_code=400, detail="El nombre no puede estar vacío")
    
    esp32_node.name = new_name
    esp32_node.updated_at = func.now()
    db.commit()
    
    return {
        "status": "updated",
        "node_id": str(esp32_node.id),
        "new_name": esp32_node.name
    }


@router.patch("/shelf/{shelf_id}/name")
def update_shelf_name(
    shelf_id: str,
    body: dict,  # {"name": "Nuevo nombre del estante"}
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """
    Actualiza el nombre de un estante (shelf)
    """
    token = extract_token(authorization)
    org_token = verify_organization_token(db, token)
    
    try:
        sh_id = uuid.UUID(shelf_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="shelf_id inválido")
    
    # Obtener estante
    shelf = db.query(Shelf).filter(Shelf.id == sh_id).first()
    if not shelf:
        raise HTTPException(status_code=404, detail="Estante no encontrado")
    
    # Validar permisos
    branch = db.query(Branch).filter(Branch.id == shelf.branch_id).first()
    if branch.organization_id != org_token.organization_id:
        raise HTTPException(status_code=403, detail="No tienes acceso a este estante")
    
    # Actualizar nombre
    new_name = body.get("name", "").strip()
    if not new_name:
        raise HTTPException(status_code=400, detail="El nombre no puede estar vacío")
    
    shelf.name = new_name
    shelf.updated_at = func.now()
    db.commit()
    
    return {
        "status": "updated",
        "shelf_id": str(shelf.id),
        "new_name": shelf.name
    }


@router.patch("/shelf/{shelf_id}/status")
def update_shelf_connection_status(
    shelf_id: str,
    body: dict,  # {"is_connected": bool, "last_reading_at": datetime}
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """
    Actualiza el estado de conectividad de un HX711 (estante)
    Usado por el ESP32 para reportar si está recibiendo lectura
    """
    token = extract_token(authorization)
    org_token = verify_organization_token(db, token)
    
    try:
        sh_id = uuid.UUID(shelf_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="shelf_id inválido")
    
    # Obtener estante
    shelf = db.query(Shelf).filter(Shelf.id == sh_id).first()
    if not shelf:
        raise HTTPException(status_code=404, detail="Estante no encontrado")
    
    # Validar permisos
    branch = db.query(Branch).filter(Branch.id == shelf.branch_id).first()
    if branch.organization_id != org_token.organization_id:
        raise HTTPException(status_code=403, detail="No tienes acceso a este estante")
    
    # Actualizar estado de conectividad
    is_connected = body.get("is_connected", shelf.is_connected)
    shelf.is_connected = is_connected
    shelf.last_reading_at = func.now()
    shelf.updated_at = func.now()
    db.commit()
    
    return {
        "status": "updated",
        "shelf_id": str(shelf.id),
        "is_connected": shelf.is_connected
    }
# ============ CALIBRATION ENDPOINTS ============

class CalibrationUpdateRequest(BaseModel):
    last_calibrated_at: Optional[datetime] = None
    scale_factor: Optional[float] = None

@router.patch("/shelf/{shelf_id}/calibration")
def update_shelf_calibration(
    shelf_id: str,
    body: CalibrationUpdateRequest,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """
    Actualiza los parámetros de calibración de un estante (tara y factor de escala).
    Usado por la RPI cuando recibe confirmación del ESP32.
    """
    token = extract_token(authorization)
    org_token = verify_organization_token(db, token)
    
    try:
        sh_id = uuid.UUID(shelf_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="shelf_id inválido")
    
    shelf = db.query(Shelf).filter(Shelf.id == sh_id).first()
    if not shelf:
        raise HTTPException(status_code=404, detail="Estante no encontrado")
    
    # Verificar permisos
    branch = db.query(Branch).filter(Branch.id == shelf.branch_id).first()
    if branch.organization_id != org_token.organization_id:
        raise HTTPException(status_code=403, detail="No tienes acceso a este estante")
    
    if body.last_calibrated_at:
        shelf.last_calibrated_at = body.last_calibrated_at
    if body.scale_factor is not None:
        shelf.scale_factor = body.scale_factor
    
    shelf.updated_at = func.now()

    db.query(PendingCommand).filter(
        PendingCommand.shelf_id == shelf.id,
        PendingCommand.status == "pending"
    ).update({"status": "executed", "executed_at": func.now()})
    db.commit()
    
    return {"status": "updated", "shelf_id": str(shelf.id)}


@router.get("/shelf/{shelf_id}/full")
def get_shelf_full(
    shelf_id: str,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """
    Obtiene toda la información del estante, incluyendo el producto asociado y el nodo ESP32.
    """
    token = extract_token(authorization)
    org_token = verify_organization_token(db, token)
    
    try:
        sh_id = uuid.UUID(shelf_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="shelf_id inválido")
    
    shelf = db.query(Shelf).filter(Shelf.id == sh_id).first()
    if not shelf:
        raise HTTPException(status_code=404, detail="Estante no encontrado")
    
    branch = db.query(Branch).filter(Branch.id == shelf.branch_id).first()
    if branch.organization_id != org_token.organization_id:
        raise HTTPException(status_code=403, detail="No tienes acceso a este estante")
    
    # Información del nodo ESP32
    node_info = None
    if shelf.esp32_node_id:
        node = db.query(Esp32Node).filter(Esp32Node.id == shelf.esp32_node_id).first()
        if node:
            node_info = {
                "id": str(node.id),
                "name": node.name,
                "mac_address": node.mac_address,
                "is_online": node.is_online
            }
    
    # Información del producto
    product_info = None
    if shelf.product_id:
        from app.models.product import Product
        product = db.query(Product).filter(Product.id == shelf.product_id).first()
        if product:
            product_info = {
                "id": str(product.id),
                "name": product.name,
                "sku": product.sku,
                "unit_cost": float(product.unit_cost) if product.unit_cost else 0,
                "unit_price": float(product.unit_price) if product.unit_price else 0,
                "unit_weight_grams": float(product.unit_weight_grams) if product.unit_weight_grams else None,
                "category": product.category,
            }
    
    return {
        "id": str(shelf.id),
        "name": shelf.name,
        "branch_id": str(shelf.branch_id),
        "esp32_node": node_info,
        "hx711_pin": shelf.hx711_pin,
        "hx711_position": shelf.hx711_position,
        "is_connected": shelf.is_connected,
        "last_reading_at": shelf.last_reading_at.isoformat() if shelf.last_reading_at else None,
        "tare_weight_grams": float(shelf.tare_weight_grams) if shelf.tare_weight_grams else 0,
        "scale_factor": float(shelf.scale_factor) if shelf.scale_factor else 1,
        "max_capacity_grams": float(shelf.max_capacity_grams) if shelf.max_capacity_grams else None,
        "low_stock_threshold_kg": float(shelf.low_stock_threshold_kg) if shelf.low_stock_threshold_kg else None,
        "alert_mode": shelf.alert_mode,
        "last_calibrated_at": shelf.last_calibrated_at.isoformat() if shelf.last_calibrated_at else None,
        "product": product_info,
    }


# ============ COMMAND POLLING ============

class PendingCommandResponse(BaseModel):
    id: UUID
    shelf_id: UUID
    command_type: str
    reference_weight_kg: Optional[float] = None


@router.get("/gateway/{gateway_id}/commands")
def get_pending_commands(
    gateway_id: str,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """
    RPI consulta comandos pendientes no ejecutados para su gateway.
    """
    token = extract_token(authorization)
    org_token = verify_organization_token(db, token)

    gateway = db.query(Gateway).filter(Gateway.id == gateway_id).first()
    if not gateway:
        raise HTTPException(404, "Gateway no encontrado")

    # Comandos pendientes para estantes que pertenecen a ESP32s de este gateway
    commands = db.query(PendingCommand).join(
        Shelf, PendingCommand.shelf_id == Shelf.id
    ).filter(
        Shelf.esp32_node.has(gateway_id=gateway_id),
        PendingCommand.status == "pending"
    ).all()

    return [PendingCommandResponse.model_validate(cmd) for cmd in commands]


@router.patch("/commands/{command_id}/status")
def update_command_status(
    command_id: str,
    body: dict,  # {"status": "executed"}
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """
    RPI notifica que ejecutó (o falló) el comando.
    """
    token = extract_token(authorization)
    org_token = verify_organization_token(db, token)

    cmd = db.query(PendingCommand).filter(PendingCommand.id == command_id).first()
    if not cmd:
        raise HTTPException(404, "Comando no encontrado")

    new_status = body.get("status")
    if new_status not in ("executed", "failed"):
        raise HTTPException(400, "Status inválido")

    cmd.status = new_status
    cmd.executed_at = func.now()
    db.commit()
    return {"status": "ok"}


@router.post("/calibrate/{shelf_id}/tare")
def request_tare(
    shelf_id: str,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """
    Frontend → crea un comando de tara para un estante.
    """
    token = extract_token(authorization)
    org_token = verify_organization_token(db, token)

    shelf = db.query(Shelf).filter(Shelf.id == shelf_id).first()
    if not shelf:
        raise HTTPException(404, "Estante no encontrado")

    # Verificar permisos (usando branch)
    branch = db.query(Branch).filter(Branch.id == shelf.branch_id).first()
    if branch.organization_id != org_token.organization_id:
        raise HTTPException(403, "No tienes acceso a este estante")

    cmd = PendingCommand(
        shelf_id=shelf_id,
        command_type="tare"
    )
    db.add(cmd)
    db.commit()
    return {"message": "Comando de tara creado", "command_id": str(cmd.id)}


@router.post("/calibrate/{shelf_id}/scale")
def request_scale(
    shelf_id: str,
    body: dict,  # {"reference_weight_kg": 1.0}
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """
    Frontend → crea un comando de calibración con peso de referencia.
    """
    token = extract_token(authorization)
    org_token = verify_organization_token(db, token)

    shelf = db.query(Shelf).filter(Shelf.id == shelf_id).first()
    if not shelf:
        raise HTTPException(404, "Estante no encontrado")

    branch = db.query(Branch).filter(Branch.id == shelf.branch_id).first()
    if branch.organization_id != org_token.organization_id:
        raise HTTPException(403, "No tienes acceso a este estante")

    ref_weight = body.get("reference_weight_kg")
    if not ref_weight or ref_weight <= 0:
        raise HTTPException(400, "Peso de referencia inválido")

    cmd = PendingCommand(
        shelf_id=shelf_id,
        command_type="scale",
        reference_weight_kg=ref_weight
    )
    db.add(cmd)
    db.commit()
    return {"message": "Comando de calibración creado", "command_id": str(cmd.id)}
