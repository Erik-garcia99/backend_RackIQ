import secrets
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.models.organization_token import OrganizationToken
from app.models.organization import Organization
from app.schemas.token import (
    TokenValidateRequest, TokenValidateResponse,
    TokenGenerateRequest, TokenGenerateResponse
)

router = APIRouter(prefix="/tokens", tags=["tokens"])


@router.post("/validate", response_model=TokenValidateResponse)
def validate_token(body: TokenValidateRequest, db: Session = Depends(get_db)):
    # Buscar por label (más amigable) o por token (UUID)
    record = db.query(OrganizationToken).filter(
        (
            (OrganizationToken.label == body.token) |
            (OrganizationToken.token == body.token)
        ),
        OrganizationToken.is_active == True
    ).first()

    if not record:
        return TokenValidateResponse(is_valid=False, message="Token inválido o inactivo")

    org = db.query(Organization).filter(Organization.id == record.organization_id).first()

    return TokenValidateResponse(
        is_valid=True,
        organization_id=org.id,
        organization_name=org.name,
        message="Token válido"
    )


@router.post("/generate", response_model=TokenGenerateResponse)
def generate_token(body: TokenGenerateRequest, db: Session = Depends(get_db)):
    org = db.query(Organization).filter(Organization.id == body.organization_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organización no encontrada")

    new_token = secrets.token_urlsafe(16)

    record = OrganizationToken(
        organization_id=body.organization_id,
        token=new_token,
        label=body.label,
        is_active=True,
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    return TokenGenerateResponse(
        token=new_token,
        label=body.label,
        organization_id=body.organization_id,
    )