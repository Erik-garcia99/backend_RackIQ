from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from uuid import UUID
from app.db.database import get_db
from app.models.user import User
from app.schemas.user import (
    UserResponse, UpdateUserStatusRequest, UpdateUserStatusResponse, AssignSupervisorRequest
)
from app.core.security import get_current_user
from app.services.firebase_service import send_push_notification

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserResponse)
def get_current_user_profile(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Obtiene el perfil del usuario actual con información del supervisor.
    """
    # Obtener el nombre del supervisor si existe
    supervisor_name = None
    if current_user.supervisor_id:
        supervisor = db.query(User).filter(User.id == current_user.supervisor_id).first()
        if supervisor:
            supervisor_name = supervisor.name
    
    # Crear respuesta manualmente para incluir supervisor_name
    user_data = {
        "id": current_user.id,
        "name": current_user.name,
        "email": current_user.email,
        "role": current_user.role,
        "account_status": current_user.account_status,
        "supervisor_id": current_user.supervisor_id,
        "supervisor_name": supervisor_name
    }
    
    return user_data


@router.get("/my-team", response_model=list[UserResponse])
def get_my_team(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Obtiene todos los empleados bajo la supervisión del usuario actual.
    Solo accesible para usuarios con rol 'manager', 'admin', 'owner' o 'superadmin'.
    """
    # Verificar permisos
    if current_user.role not in ["manager", "admin", "owner", "superadmin"]:
        raise HTTPException(status_code=403, detail="No tienes permiso para ver el equipo")
    
    # Obtener todos los empleados con este supervisor
    employees = db.query(User).filter(
        User.supervisor_id == current_user.id,
        User.organization_id == current_user.organization_id
    ).all()
    
    return employees


@router.put("/{user_id}/status", response_model=UpdateUserStatusResponse)
def update_user_status(
    user_id: UUID,
    body: UpdateUserStatusRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Actualiza el estado de un empleado.
    Solo el supervisor o un admin pueden hacer esto.
    Envía notificación push al dispositivo del empleado.
    """
    # Obtener el usuario a actualizar
    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    # Verificar permisos: solo supervisor, admin, owner o superadmin
    is_supervisor = target_user.supervisor_id == current_user.id
    is_admin = current_user.role in ["admin", "owner", "superadmin"]
    
    if not (is_supervisor or is_admin):
        raise HTTPException(status_code=403, detail="No tienes permiso para actualizar este usuario")
    
    # Validar estado
    valid_statuses = ["active", "pending", "suspended", "deleted"]
    if body.status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Estado no válido. Debe ser uno de: {valid_statuses}")
    
    # Actualizar estado
    old_status = target_user.account_status
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
        send_push_notification(
            push_token=target_user.push_token,
            title=notification_titles.get(body.status, "Actualización de Estado"),
            body=status_messages.get(body.status, "Tu estado ha sido actualizado"),
            data={
                "action": "status_changed",
                "status": body.status,
                "timestamp": str(db.query(User).filter(User.id == current_user.id).first().created_at)
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
    Solo admin u owner pueden hacer esto.
    """
    # Verificar permisos
    if current_user.role not in ["admin", "owner", "superadmin"]:
        raise HTTPException(status_code=403, detail="No tienes permiso para asignar supervisores")
    
    # Obtener el usuario a actualizar
    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    # Verificar que el supervisor existe
    supervisor = db.query(User).filter(User.id == body.supervisor_id).first()
    if not supervisor:
        raise HTTPException(status_code=404, detail="Supervisor no encontrado")
    
    # Verificar que el supervisor y el empleado están en la misma organización
    if supervisor.organization_id != target_user.organization_id:
        raise HTTPException(status_code=400, detail="El supervisor debe estar en la misma organización")
    
    # Asignar supervisor
    target_user.supervisor_id = body.supervisor_id
    db.commit()
    db.refresh(target_user)
    
    return target_user
