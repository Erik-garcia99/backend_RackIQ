import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from uuid import uuid4

# Agregar el path al backend
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from app.models.user import User
from app.models.organization_token import OrganizationToken
from app.core.security import hash_password

# Configuración de conexión
DATABASE_URL = "postgresql://postgres:best4ever@localhost:5432/rackiq_db"
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)

VALID_ROLES = ["staff", "manager", "admin", "owner", "superadmin"]

def create_test_user(token_code: str, email: str, name: str, role: str = "staff", password: str = None):
    """
    Crea un usuario de prueba usando un token de organización.
    
    Args:
        token_code: Código del token (ej: "TOKEN-PRUEBA-001")
        email: Email del usuario
        name: Nombre completo
        role: Rol del usuario (staff, manager, admin, owner, superadmin)
        password: Contraseña (si no se proporciona, genera una por defecto)
    """
    
    # Validar rol
    if role not in VALID_ROLES:
        print(f"❌ Rol inválido '{role}'. Roles válidos: {', '.join(VALID_ROLES)}")
        return
    
    if password is None:
        password = "Test123!@#"
    
    session = Session()
    
    try:
        # 1. Buscar el token de organización
        org_token = session.query(OrganizationToken).filter(
            OrganizationToken.token == token_code
        ).first()
        
        if not org_token:
            print(f"❌ Token '{token_code}' no encontrado")
            return
        
        print(f"✅ Token encontrado: {org_token.label}")
        print(f"   Organización ID: {org_token.organization_id}")
        
        # 2. Buscar un supervisor (admin, owner o superadmin) en la misma organización
        supervisor = session.query(User).filter(
            User.organization_id == org_token.organization_id,
            User.role.in_(["admin", "owner", "superadmin"])
        ).first()
        
        if supervisor:
            print(f"✅ Supervisor encontrado: {supervisor.name} ({supervisor.role})")
        else:
            print(f"⚠️  No hay supervisor en esta organización (se asignará None)")
        
        # 3. Crear el usuario
        new_user = User(
            id=uuid4(),
            organization_id=org_token.organization_id,
            branch_id=None,
            supervisor_id=supervisor.id if supervisor else None,
            email=email.lower().strip(),
            name=name.strip(),
            role=role,
            password_hash=hash_password(password),
            account_status="active" if role != "staff" else "pending",  # Admin/Owner inicia activo
            push_token=None
        )
        
        session.add(new_user)
        session.commit()
        session.refresh(new_user)
        
        print(f"\n✅ Usuario creado exitosamente!")
        print(f"   ID: {new_user.id}")
        print(f"   Email: {new_user.email}")
        print(f"   Nombre: {new_user.name}")
        print(f"   Rol: {new_user.role}")
        print(f"   Estado: {new_user.account_status}")
        print(f"   Supervisor: {supervisor.name if supervisor else 'Ninguno'}")
        print(f"\n   Credenciales:")
        print(f"   Email: {new_user.email}")
        print(f"   Contraseña: {password}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        session.rollback()
    finally:
        session.close()

def list_valid_roles():
    """Muestra los roles válidos"""
    print("\n📋 Roles válidos:")
    for role in VALID_ROLES:
        descriptions = {
            "staff": "Empleado regular (requiere aprobación)",
            "manager": "Gerente (puede ver empleados a cargo)",
            "admin": "Administrador (puede gestionar usuarios)",
            "owner": "Propietario (acceso total)",
            "superadmin": "Súper administrador (acceso total)"
        }
        print(f"   - {role}: {descriptions.get(role, 'Sin descripción')}")

if __name__ == "__main__":
    print("\n" + "="*70)
    print("CREAR UN USUARIO DE PRUEBA")
    print("="*70)
    
    # Mostrar roles disponibles
    list_valid_roles()
    
    print("\n" + "="*70)
    
    # Pedir rol al usuario
    while True:
        try:
            print("\nSelecciona un rol (ingresa el número):")
            for i, role in enumerate(VALID_ROLES, 1):
                print(f"  {i}. {role}")
            
            role_input = input("\n👉 Número: ").strip()
            role_index = int(role_input) - 1
            
            if 0 <= role_index < len(VALID_ROLES):
                selected_role = VALID_ROLES[role_index]
                break
            else:
                print("❌ Número inválido. Intenta de nuevo.")
        except ValueError:
            print("❌ Debes ingresar un número. Intenta de nuevo.")
    
    # Pedir email
    while True:
        email = input("\n📧 Email del usuario: ").strip()
        if email and "@" in email:
            break
        print("❌ Email inválido. Intenta de nuevo.")
    
    # Pedir nombre
    name = input("👤 Nombre del usuario: ").strip()
    
    # Pedir contraseña (opcional)
    password_input = input("🔑 Contraseña (presiona Enter para usar 'Test123!@#'): ").strip()
    password = password_input if password_input else None
    
    # Crear usuario
    print("\n" + "="*70)
    print(f"Creando usuario con rol: {selected_role}")
    print("="*70)
    
    create_test_user(
        token_code="TOKEN-PRUEBA-001",
        email=email,
        name=name,
        role=selected_role,
        password=password
    )
    
    print("\n" + "="*70)
    print("✅ ¡Listo!")
    print("="*70 + "\n")
