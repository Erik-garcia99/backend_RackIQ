import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Base de datos
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:best4ever@localhost:5432/rackiq_db"
    )
    
    # API
    API_PREFIX: str = os.getenv("API_PREFIX", "/api/v1")
    PROJECT_NAME: str = os.getenv("PROJECT_NAME", "RackIQ API")
    
    # Firebase
    FIREBASE_CREDENTIALS_PATH: str = os.getenv(
        "FIREBASE_CREDENTIALS_PATH",
        "./firebase-credentials.json"
    )
    
    # JWT
    SECRET_KEY: str = os.getenv(
        "SECRET_KEY",
        "your-secret-key-change-in-production"
    )
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    
    # Entorno
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
    
    # CORS - Configuración segura
    ALLOWED_ORIGINS: list = [
        "http://localhost:3000",
        "http://localhost:8000",
    ]
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Agregar orígenes adicionales desde variable de entorno si existen
        if environment_origins := os.getenv("ALLOWED_ORIGINS"):
            self.ALLOWED_ORIGINS.extend(environment_origins.split(","))

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()