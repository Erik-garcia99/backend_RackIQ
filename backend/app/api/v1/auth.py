from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.models.user import User
from app.services.auth_service import get_token_by_code
from app.models.organization_token import OrganizationToken
from app.schemas.auth import (
    LoginRequest, TokenResponse,
    RegisterRequest, RegisterResponse
)
from app.core.security import verify_password, create_access_token, hash_password

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(
        User.email == body.email,
    ).first()

    if not user or not user.password_hash:
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")

    if not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")

    # Guardar push_token si se proporciona
    if body.push_token:
        user.push_token = body.push_token
        db.commit()

    # Permitir login aunque esté pending, el front decide qué mostrar
    token = create_access_token({
        "sub": str(user.id),
        "role": user.role,
        "org": str(user.organization_id),
        "status": user.account_status,
    })

    return TokenResponse(
        access_token=token,
        user_id=user.id,
        name=user.name,
        role=user.role,
        account_status=user.account_status,
        organization_id=user.organization_id,
    )


@router.post("/register", response_model=RegisterResponse, status_code=201)
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    # 1. Verificar que el correo no exista ya
    existing = db.query(User).filter(User.email == body.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Este correo ya está registrado")

    # 2. Buscar el token de organización
    org_token = get_token_by_code(db, body.branch_code)
    if not org_token:
        raise HTTPException(status_code=404, detail="Token de organización no válido o inactivo")

    # 3. Buscar un supervisor (admin, owner o superadmin) en la misma organización
    supervisor = db.query(User).filter(
        User.organization_id == org_token.organization_id,
        User.role.in_(["admin", "owner", "superadmin"])
    ).first()

    # 4. Crear usuario con permisos mínimos y status pending
    new_user = User(
        organization_id=org_token.organization_id,
        branch_id=None,  # El token no está ligado a una sucursal específica
        supervisor_id=supervisor.id if supervisor else None,
        email=body.email.lower().strip(),
        name=body.full_name.strip(),
        role="staff",
        password_hash=hash_password(body.password),
        push_token=body.push_token,  # Guardar el token FCM
        account_status="pending",
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return RegisterResponse(
        user_id=new_user.id,
        name=new_user.name,
        email=new_user.email,
        account_status=new_user.account_status,
        message="Usuario registrado. Espera que un administrador active tu cuenta."
    )