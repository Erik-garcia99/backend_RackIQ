from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.v1.router import api_router
# Importar modelos para registrarlos en SQLAlchemy
from app.models import (
    Base,
    Organization,
    OrganizationToken,
    Branch,
    User,
    Product,
    InventoryMovement,
    Sale,
    SaleItem,
)

app = FastAPI(title=settings.PROJECT_NAME)

# Configuración segura de CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS if not settings.DEBUG else ["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.API_PREFIX)

@app.get("/health")
def health_check():
    return {
        "status": "ok", 
        "service": "RackIQ API",
        "environment": settings.ENVIRONMENT
    }