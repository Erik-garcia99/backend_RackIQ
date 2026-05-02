from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://postgres:best4ever@basededatos:5432/rackiq_db"
    API_PREFIX: str = "/api/v1"
    PROJECT_NAME: str = "RackIQ API"

    class Config:
        env_file = ".env"

settings = Settings()