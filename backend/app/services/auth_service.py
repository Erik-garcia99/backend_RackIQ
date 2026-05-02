from sqlalchemy.orm import Session
from app.models.organization_token import OrganizationToken

def get_token_by_code(db: Session, token_code: str) -> OrganizationToken | None:
    """
    Busca un token de organización por su código.

    Args:
        db: La sesión de base de datos.
        token_code: El código del token a buscar.

    Returns:
        El objeto OrganizationToken si se encuentra, de lo contrario None.
    """
    return db.query(OrganizationToken).filter(
        OrganizationToken.token == token_code,
        OrganizationToken.is_active == True
    ).first()
