import uuid
import secrets
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.sql import func
from typing import List

from app.db.database import get_db
from app.models.organization import Organization
from app.models.organization_token import OrganizationToken
from app.schemas.organization import (
    OrganizationCreateRequest,
    OrganizationResponse,
    OrganizationTokenCreateRequest,
    OrganizationTokenResponse,
)
from app.core.security import get_current_user

router = APIRouter(prefix="/organizations", tags=["organizations"])


@router.post("/", response_model=OrganizationResponse, status_code=201)
def create_organization(
    body: OrganizationCreateRequest,
    db: Session = Depends(get_db),
):
    """
    Crea una nueva organización.
    
    **Nota**: Este endpoint es público. En producción, deberías protegerlo con autenticación.
    """
    
    # Validar que el slug sea único
    existing = db.query(Organization).filter(
        Organization.slug == body.slug.lower().strip()
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Ya existe una organización con el slug '{body.slug}'"
        )
    
    # Crear nueva organización
    organization = Organization(
        name=body.name.strip(),
        slug=body.slug.lower().strip(),
        plan_type=body.plan_type,
    )
    
    db.add(organization)
    db.commit()
    db.refresh(organization)
    
    return organization


@router.get("/{organization_id}", response_model=OrganizationResponse)
def get_organization(
    organization_id: str,
    db: Session = Depends(get_db),
):
    """
    Obtiene los detalles de una organización por ID.
    """
    try:
        org_uuid = uuid.UUID(organization_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="ID de organización inválido")
    
    organization = db.query(Organization).filter(
        Organization.id == org_uuid
    ).first()
    
    if not organization:
        raise HTTPException(status_code=404, detail="Organización no encontrada")
    
    return organization


@router.post("/{organization_id}/tokens", response_model=OrganizationTokenResponse, status_code=201)
def create_organization_token(
    organization_id: str,
    body: OrganizationTokenCreateRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Crea un nuevo token de organización.
    
    **Requiere**: Usuario autenticado que pertenezca a la organización.
    """
    try:
        org_uuid = uuid.UUID(organization_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="ID de organización inválido")
    
    # Verificar que el usuario pertenezca a la organización
    if str(current_user.get("org")) != organization_id:
        raise HTTPException(
            status_code=403,
            detail="No tienes permiso para crear tokens en esta organización"
        )
    
    # Generar token único
    token = secrets.token_urlsafe(32)
    
    # Verificar que el token sea único (muy poco probable pero sí es posible)
    while db.query(OrganizationToken).filter(
        OrganizationToken.token == token
    ).first():
        token = secrets.token_urlsafe(32)
    
    # Crear el token
    org_token = OrganizationToken(
        organization_id=org_uuid,
        token=token,
        label=body.label.strip(),
        created_by=current_user.get("sub"),
    )
    
    db.add(org_token)
    db.commit()
    db.refresh(org_token)
    
    return org_token


@router.get("/{organization_id}/tokens", response_model=List[OrganizationTokenResponse])
def list_organization_tokens(
    organization_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Lista todos los tokens activos de una organización.
    
    **Requiere**: Usuario autenticado que pertenezca a la organización.
    """
    try:
        org_uuid = uuid.UUID(organization_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="ID de organización inválido")
    
    # Verificar que el usuario pertenezca a la organización
    if str(current_user.get("org")) != organization_id:
        raise HTTPException(
            status_code=403,
            detail="No tienes permiso para ver tokens de esta organización"
        )
    
    tokens = db.query(OrganizationToken).filter(
        OrganizationToken.organization_id == org_uuid,
        OrganizationToken.is_active == True,
    ).all()
    
    return tokens


@router.delete("/{organization_id}/tokens/{token_id}", status_code=204)
def deactivate_organization_token(
    organization_id: str,
    token_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Desactiva un token de organización.
    
    **Requiere**: Usuario autenticado que pertenezca a la organización.
    """
    try:
        org_uuid = uuid.UUID(organization_id)
        token_uuid = uuid.UUID(token_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="IDs inválidos")
    
    # Verificar que el usuario pertenezca a la organización
    if str(current_user.get("org")) != organization_id:
        raise HTTPException(
            status_code=403,
            detail="No tienes permiso para desactivar tokens en esta organización"
        )
    
    token = db.query(OrganizationToken).filter(
        OrganizationToken.id == token_uuid,
        OrganizationToken.organization_id == org_uuid,
    ).first()
    
    if not token:
        raise HTTPException(status_code=404, detail="Token no encontrado")
    
    token.is_active = False
    db.commit()
    
    return None
