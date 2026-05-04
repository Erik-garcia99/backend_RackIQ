import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.sql import func
from typing import List
from app.db.database import get_db
from app.models.branch import Branch
from app.models.organization_token import OrganizationToken
from app.schemas.branch import BranchRegisterRequest, BranchResponse

router = APIRouter(prefix="/branches", tags=["branches"])


@router.post("/register", response_model=BranchResponse, status_code=201)
def register_branch(body: BranchRegisterRequest, db: Session = Depends(get_db)):
    token_record = db.query(OrganizationToken).filter(
        OrganizationToken.token == body.token,
        OrganizationToken.is_active == True
    ).first()

    if not token_record:
        raise HTTPException(status_code=400, detail="Token inválido o inactivo")

    # ──── VALIDAR QUE NO HAYA SUCURSAL CON EL MISMO NOMBRE Y DIRECCIÓN ────
    existing_branch = db.query(Branch).filter(
        Branch.organization_id == token_record.organization_id,
        Branch.name.ilike(body.name.strip()),  # Case-insensitive
        Branch.address.ilike(body.address.strip() if body.address else ""),
        Branch.is_active == True
    ).first()

    if existing_branch:
        raise HTTPException(
            status_code=400, 
            detail=f"Ya existe una sucursal con el nombre '{body.name}' y dirección '{body.address}' en tu organización"
        )

    # ──── CREAR NUEVA SUCURSAL ────
    branch_code = f"BR-{uuid.uuid4().hex[:6].upper()}"

    branch = Branch(
        organization_id=token_record.organization_id,
        name=body.name,
        address=body.address,
        timezone=body.timezone,
        branch_code=branch_code,
    )
    db.add(branch)

    # Marcar cuándo se usó por última vez
    token_record.last_used_at = func.now()

    db.commit()
    db.refresh(branch)

    return branch


@router.get("/organization/{organization_id}", response_model=List[BranchResponse])
def get_organization_branches(organization_id: str, db: Session = Depends(get_db)):
    """
    Obtiene todas las sucursales de una organización.
    """
    try:
        org_uuid = uuid.UUID(organization_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="ID de organización inválido")
    
    branches = db.query(Branch).filter(
        Branch.organization_id == org_uuid,
        Branch.is_active == True
    ).all()
    return branches


@router.get("/{branch_id}", response_model=BranchResponse)
def get_branch(branch_id: str, db: Session = Depends(get_db)):
    branch = db.query(Branch).filter(Branch.id == branch_id).first()
    if not branch:
        raise HTTPException(status_code=404, detail="Sucursal no encontrada")
    return branch