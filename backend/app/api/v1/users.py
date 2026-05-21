from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import or_
from uuid import UUID
from datetime import datetime
from app.db.database import get_db
from app.models.user import User
from app.models.branch import Branch
from app.schemas.user import (
    UserResponse, UpdateUserStatusRequest, UpdateUserStatusResponse, AssignSupervisorRequest,
    AssignBranchRequest, UpdateProfileRequest, UpdateProfileResponse
)
from app.core.security import get_current_user, hash_password, verify_password
from app.services.firebase_service import send_push_notification

router = APIRouter(prefix="/users", tags=["users"])


SUPERVISOR_ROLES = ["admin", "owner", "superadmin", "superuser", "rrhh", "director", "gerente", "manager"]


def serialize_user(db: Session, user: User) -> dict:
    supervisor_name = None
    if user.supervisor_id:
        supervisor = db.query(User).filter(User.id == user.supervisor_id).first()
        if supervisor:
            supervisor_name = supervisor.name

    branch_name = None
    if user.branch_id:
        branch = db.query(Branch).filter(Branch.id == user.branch_id).first()
        if branch:
            branch_name = branch.name

    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "branch_id": user.branch_id,
        "branch_name": branch_name,
        "phone_number": user.phone_number,
        "account_status": user.account_status,
        "supervisor_id": user.supervisor_id,
        "supervisor_name": supervisor_name,
    }


@router.get("/me", response_model=UserResponse)
def get_current_user_profile(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Obtiene el perfil del usuario actual.
    """
    return serialize_user(db, current_user)


@router.get("/my-team", response_model=list[UserResponse])
def get_my_team(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Obtiene los empleados directos a cargo del usuario actual.
    Solo accesible para usuarios con rol de mando o RRHH.
    """
    # Verificar permisos: solo roles que pueden tener gente a cargo
    if current_user.role not in SUPERVISOR_ROLES:
        raise HTTPException(status_code=403, detail="No tienes permiso para ver el equipo")
    
    # Obtener solo los empleados que reportan directamente al usuario actual
    employees = db.query(User).filter(
        User.organization_id == current_user.organization_id,
        User.supervisor_id == current_user.id
    ).all()
    
    return [serialize_user(db, employee) for employee in employees]


@router.get("/supervisors", response_model=list[UserResponse])
def get_branch_supervisors(
    branch_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Devuelve posibles supervisores para una sucursal.
    """
    if current_user.role not in ["admin", "owner", "superuser", "rrhh"]:
        raise HTTPException(status_code=403, detail="No tienes permiso para ver supervisores")

    branch = db.query(Branch).filter(
        Branch.id == branch_id,
        Branch.organization_id == current_user.organization_id,
        Branch.is_active == True
    ).first()
    if not branch:
        raise HTTPException(status_code=404, detail="Sucursal no encontrada")

    supervisors = db.query(User).filter(
        User.organization_id == current_user.organization_id,
        User.role.in_(SUPERVISOR_ROLES),
        or_(User.branch_id == branch_id, User.branch_id.is_(None))
    ).order_by(User.name.asc()).all()

    return [serialize_user(db, supervisor) for supervisor in supervisors]


@router.put("/{user_id}/status", response_model=UpdateUserStatusResponse)
def update_user_status(
    user_id: UUID,
    body: UpdateUserStatusRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Actualiza el estado de un empleado.
    Solo un admin, owner o superadmin pueden hacer esto.
    Envía notificación push al dispositivo del empleado.
    """
    # Obtener el usuario a actualizar
    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    # Verificar permisos: solo admin, owner o superadmin
    is_admin = current_user.role in ["admin", "owner", "superadmin"]
    
    if not is_admin:
        raise HTTPException(status_code=403, detail="No tienes permiso para actualizar este usuario")
    
    # Validar estado
    valid_statuses = ["active", "pending", "suspended", "deleted"]
    if body.status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Estado no válido. Debe ser uno de: {valid_statuses}")
    
    # Actualizar estado
    target_user.account_status = body.status
    db.commit()
    db.refresh(target_user)
    
    status_messages = {
        "active": "Tu cuenta ha sido activada",
        "pending": "Tu cuenta está pendiente de revisión",
        "suspended": "Tu cuenta ha sido suspendida",
        "deleted": "Tu cuenta ha sido eliminada"
    }
    
    notification_titles = {
        "active": "Cuenta Activada",
        "pending": "Cuenta Pendiente",
        "suspended": "Cuenta Suspendida",
        "deleted": "Cuenta Eliminada"
    }
    
    # Enviar notificación push si el usuario tiene token
    if target_user.push_token:
        from datetime import datetime
        send_push_notification(
            push_token=target_user.push_token,
            title=notification_titles.get(body.status, "Actualización de Estado"),
            body=status_messages.get(body.status, "Tu estado ha sido actualizado"),
            data={
                "action": "status_changed",
                "status": body.status,
                "timestamp": datetime.utcnow().isoformat()
            }
        )
    
    return UpdateUserStatusResponse(
        id=target_user.id,
        name=target_user.name,
        account_status=target_user.account_status,
        message=status_messages.get(body.status, "Estado actualizado")
    )


@router.put("/{user_id}/assign-supervisor", response_model=UserResponse)
def assign_supervisor(
    user_id: UUID,
    body: AssignSupervisorRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Asigna un supervisor a un empleado.
    Solo usuarios con rol 'rrhh', 'owner' o 'superuser' pueden hacer esto.
    """
    # Verificar permisos: solo rrhh, owner, superuser
    if current_user.role not in ["rrhh", "owner", "superuser"]:
        raise HTTPException(status_code=403, detail="No tienes permiso para asignar supervisores")
    
    # Obtener el empleado a asignar
    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    # Validar que el supervisor existe
    supervisor = db.query(User).filter(User.id == body.supervisor_id).first()
    if not supervisor:
        raise HTTPException(status_code=404, detail="Supervisor no encontrado")

    if supervisor.role not in SUPERVISOR_ROLES:
        raise HTTPException(status_code=400, detail="El usuario seleccionado no tiene un rol válido para supervisar")
    
    # Validar que el supervisor y el empleado están en la misma organización
    if supervisor.organization_id != target_user.organization_id:
        raise HTTPException(status_code=400, detail="El supervisor debe estar en la misma organización")
    
    # Asignar supervisor
    target_user.supervisor_id = body.supervisor_id
    db.commit()
    db.refresh(target_user)

    supervisor_name = supervisor.name if supervisor else None
    
    # Enviar notificación push si el usuario tiene token
    if target_user.push_token:
        send_push_notification(
            push_token=target_user.push_token,
            title="Nuevo Supervisor Asignado",
            body=f"Tu supervisor es ahora {supervisor_name}",
            data={
                "action": "supervisor_assigned",
                "supervisor_id": str(body.supervisor_id),
                "supervisor_name": supervisor_name
            }
        )
    
    return serialize_user(db, target_user)


@router.put("/{user_id}/assign-branch", response_model=UserResponse)
def assign_branch(
    user_id: UUID,
    body: AssignBranchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Asigna una sucursal a un empleado.
    Solo usuarios con rol 'rrhh', 'owner' o 'superuser' pueden hacer esto.
    """
    # Verificar permisos: solo rrhh, owner, superuser
    if current_user.role not in ["rrhh", "owner", "superuser"]:
        raise HTTPException(status_code=403, detail="No tienes permiso para asignar sucursales")
    
    # Obtener el empleado a asignar
    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    # Validar que la rama/sucursal existe
    branch = db.query(Branch).filter(Branch.id == body.branch_id).first()
    if not branch:
        raise HTTPException(status_code=404, detail="Sucursal no encontrada")
    
    # Validar que la rama y el empleado están en la misma organización
    if branch.organization_id != target_user.organization_id:
        raise HTTPException(status_code=400, detail="La sucursal debe estar en la misma organización")
    
    # Asignar rama/sucursal
    target_user.branch_id = body.branch_id

    if body.supervisor_id:
        supervisor = db.query(User).filter(User.id == body.supervisor_id).first()
        if not supervisor:
            raise HTTPException(status_code=404, detail="Supervisor no encontrado")
        if supervisor.organization_id != target_user.organization_id:
            raise HTTPException(status_code=400, detail="El supervisor debe estar en la misma organización")
        if supervisor.branch_id not in [body.branch_id, None]:
            raise HTTPException(status_code=400, detail="El supervisor debe pertenecer a la sucursal o ser un supervisor global")
        if supervisor.role not in SUPERVISOR_ROLES:
            raise HTTPException(status_code=400, detail="El usuario seleccionado no tiene un rol válido para supervisar")
        target_user.supervisor_id = body.supervisor_id

    if body.status:
        valid_statuses = ["active", "pending", "suspended", "deleted"]
        if body.status not in valid_statuses:
            raise HTTPException(status_code=400, detail=f"Estado no válido. Debe ser uno de: {valid_statuses}")
        target_user.account_status = body.status

    db.commit()
    db.refresh(target_user)
    
    # Enviar notificación push si el usuario tiene token
    if target_user.push_token:
        send_push_notification(
            push_token=target_user.push_token,
            title="Sucursal Asignada",
            body=f"Ahora estás asignado a {branch.name}",
            data={
                "action": "branch_assigned",
                "branch_id": str(body.branch_id),
                "branch_name": branch.name
            }
        )
    
    return serialize_user(db, target_user)


@router.put("/me/profile", response_model=UpdateProfileResponse)
def update_user_profile(
    body: UpdateProfileRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Actualiza el perfil del usuario actual (correo, teléfono, contraseña).
    Requiere la contraseña actual para cambios de contraseña.
    """
    # Verificar contraseña actual
    if not verify_password(body.current_password, current_user.password_hash):
        raise HTTPException(status_code=401, detail="Contraseña actual incorrecta")
    
    # Actualizar email si se proporciona
    if body.email:
        # Verificar que el email no esté en uso
        existing_user = db.query(User).filter(
            User.email == body.email, 
            User.id != current_user.id
        ).first()
        if existing_user:
            raise HTTPException(status_code=400, detail="El correo ya está en uso")
        current_user.email = body.email
    
    # Actualizar teléfono si se proporciona
    if body.phone_number:
        current_user.phone_number = body.phone_number
    
    # Actualizar contraseña si se proporciona
    if body.new_password:
        current_user.password_hash = hash_password(body.new_password)
    
    db.commit()
    db.refresh(current_user)
    
    return UpdateProfileResponse(
        id=current_user.id,
        name=current_user.name,
        email=current_user.email,
        phone_number=current_user.phone_number,
        message="Perfil actualizado exitosamente"
    )
