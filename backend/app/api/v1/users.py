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
    Obtiene el perfil del usuario actual.
    """
    # Obtener nombre del supervisor si existe
    supervisor_name = None
    if current_user.supervisor_id:
        supervisor = db.query(User).filter(User.id == current_user.supervisor_id).first()
        if supervisor:
            supervisor_name = supervisor.name
    
    # Crear respuesta con datos del usuario actual
    user_data = {
        "id": current_user.id,
        "name": current_user.name,
        "email": current_user.email,
        "role": current_user.role,
        "account_status": current_user.account_status,
        "supervisor_id": current_user.supervisor_id,
        "supervisor_name": supervisor_name,
    }
    
    return user_data


@router.get("/my-team", response_model=list[UserResponse])
def get_my_team(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Obtiene todos los empleados de la organización.
    Solo accesible para usuarios con rol 'admin', 'owner', 'superuser' o 'rrhh'.
    """
    # Verificar permisos: solo roles específicos
    if current_user.role not in ["admin", "owner", "superuser", "rrhh"]:
        raise HTTPException(status_code=403, detail="No tienes permiso para ver el equipo")
    
    # Obtener todos los empleados de la misma organización
    employees = db.query(User).filter(
        User.organization_id == current_user.organization_id
    ).all()
    
    # Enriquecer datos con nombre del supervisor
    for employee in employees:
        if employee.supervisor_id:
            supervisor = db.query(User).filter(User.id == employee.supervisor_id).first()
            if supervisor:
                employee.supervisor_name = supervisor.name
    
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
    
    # Validar que el supervisor y el empleado están en la misma organización
    if supervisor.organization_id != target_user.organization_id:
        raise HTTPException(status_code=400, detail="El supervisor debe estar en la misma organización")
    
    # Asignar supervisor
    target_user.supervisor_id = body.supervisor_id
    db.commit()
    db.refresh(target_user)
    
    # Obtener nombre del supervisor para la respuesta
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
    
    return {
        "id": target_user.id,
        "name": target_user.name,
        "email": target_user.email,
        "role": target_user.role,
        "account_status": target_user.account_status,
        "supervisor_id": target_user.supervisor_id,
        "supervisor_name": supervisor_name,
    }
