import os
from pathlib import Path
from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(_ROOT / ".env")

class Settings:
    PROJECT_NAME: str = "PlantMyPlanet"
    API_V1_PREFIX: str = "/api/v1"
    
    # Postgres
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "plant")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "plant")
    POSTGRES_HOST: str = os.getenv("POSTGRES_HOST", "localhost")
    POSTGRES_PORT: str = os.getenv("POSTGRES_PORT", "5432")
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "planttheplanet")
    
    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql+psycopg2://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    # JWT Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", "garden-planner-secret-key-35b5c0ee-minimal")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    # OpenRouter LLM
    OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")

settings = Settings()
