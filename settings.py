import os
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv("DATABASE_URL", "postgresql://localhost/encryptochat")
    redis_url: str = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
    api_url: str = os.getenv("API_URL", "http://127.0.0.1:8000")
    token_ttl_seconds: int = int(os.getenv("TOKEN_TTL_SECONDS", "604800"))
    challenge_ttl_seconds: int = int(os.getenv("CHALLENGE_TTL_SECONDS", "300"))
    cors_origins: str = os.getenv("CORS_ORIGINS", "")


settings = Settings()
