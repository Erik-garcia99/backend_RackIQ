import os
from typing import Any
from pydantic import field_validator
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Base de datos
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        ""
    )
    
    # API
    API_PREFIX: str = os.getenv("API_PREFIX", "/api/v1")
    PROJECT_NAME: str = os.getenv("PROJECT_NAME", "RackIQ API")
    
    # Supabase
    SUPABASE_URL_RQ: str = os.getenv(
        "SUPABASE_URL_RQ",
        ""
    )
    SUPABASE_KEY: str = os.getenv(
        "SUPABASE_KEY",
        ""
    )
    SUPABASE_SERVICE_ROLE_KEY: str = os.getenv(
        "SUPABASE_SERVICE_ROLE_KEY",
        ""
    )
    
    # Firebase
    FIREBASE_CREDENTIALS_PATH: str = os.getenv(
        "FIREBASE_CREDENTIALS_PATH",
        "./firebase-credentials.json"
    )
    FIREBASE_CREDENTIALS_JSON: str = os.getenv(
        "FIREBASE_CREDENTIALS_JSON",
        ""
    )
    
    # JWT
    SECRET_KEY: str = os.getenv(
        "SECRET_KEY",
        ""
    )
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    
    # InfluxDB - Para datos en tiempo real
    INFLUX_URL: str = os.getenv(
        "INFLUX_URL",
        "https://us-east-1-1.aws.cloud2.influxdata.com"
    )
    INFLUX_TOKEN: str = os.getenv("INFLUX_TOKEN", "")
    INFLUX_ORG: str = os.getenv("INFLUX_ORG", "rackiq")
    INFLUX_BUCKET: str = os.getenv("INFLUX_BUCKET", "inventario_estantes")
    
    # Celery - Para tareas asincrónicas
    CELERY_BROKER_URL: str = os.getenv(
        "CELERY_BROKER_URL",
        "redis://localhost:6379/0"
    )
    CELERY_RESULT_BACKEND: str = os.getenv(
        "CELERY_RESULT_BACKEND",
        "redis://localhost:6379/0"
    )
    
    # Entorno
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
    
    # CORS - Configuración segura
    ALLOWED_ORIGINS: Any = [
        "http://localhost:3000",
        "http://localhost:8000",
    ]
    
    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def parse_allowed_origins(cls, v):
        if isinstance(v, str):
            return [item.strip() for item in v.split(",") if item.strip()]
        return v

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()