import os
from pathlib import Path
from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    ENV: Literal["development", "production", "testing"] = "development"
    LOG_LEVEL: str = "INFO"
    
    # Telegram Bot Settings
    TELEGRAM_BOT_TOKEN: str = ""
    
    # FastAPI Backend Settings
    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8000
    API_URL: str = "http://backend:8000"
    
    # AI Settings
    GEMINI_API_KEY: str = ""
    GEMINI_API_KEY_FALLBACK: str = ""
    GEMINI_MODEL: str = "gemini-3.5-flash"
    EMBEDDING_MODEL: str = "text-embedding-004"
    
    # File Processing & Storage Settings
    UPLOAD_DIR: str = "uploads"
    MAX_FILE_SIZE_MB: int = 100
    
    # Database Settings
    DATABASE_URL: str = "sqlite+aiosqlite:///./testyourself.db"
    
    @property
    def max_file_size_bytes(self) -> int:
        return self.MAX_FILE_SIZE_MB * 1024 * 1024
        
    @property
    def upload_path(self) -> Path:
        path = Path(self.UPLOAD_DIR)
        path.mkdir(parents=True, exist_ok=True)
        return path

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

# Instantiate settings
settings = Settings()
