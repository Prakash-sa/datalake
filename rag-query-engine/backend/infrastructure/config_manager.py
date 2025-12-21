"""
Configuration Manager - Infrastructure for settings management
"""

import os
from typing import Optional


class ConfigManager:
    """Centralized configuration management."""
    
    ENV: str = os.getenv("ENV", "production")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    
    # API Settings
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    WORKERS: int = int(os.getenv("WORKERS", "4"))
    
    # CORS Settings
    ALLOWED_ORIGINS: list = [
        o.strip() for o in os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")
    ]
    
    # RAG Engine Settings
    OLLAMA_URL: str = os.getenv("OLLAMA_URL", "http://localhost:11434")
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "mistral")
    LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0.3"))
    
    # Resource Limits
    MAX_DOCUMENTS: int = int(os.getenv("MAX_DOCUMENTS", "10000"))
    MAX_QUERY_LENGTH: int = int(os.getenv("MAX_QUERY_LENGTH", "1000"))
    MAX_RESULTS: int = int(os.getenv("MAX_RESULTS", "100"))
    QUERY_TIMEOUT: int = int(os.getenv("QUERY_TIMEOUT", "30"))
    
    @classmethod
    def from_env(cls, env: str = "production"):
        """Create config from environment."""
        if env == "development":
            return cls._development_config()
        elif env == "testing":
            return cls._testing_config()
        else:
            return cls._production_config()
    
    @classmethod
    def _development_config(cls):
        """Development settings."""
        cls.DEBUG = True
        cls.LOG_LEVEL = "DEBUG"
        cls.WORKERS = 1
        cls.ALLOWED_ORIGINS = ["*"]
        return cls
    
    @classmethod
    def _production_config(cls):
        """Production settings."""
        cls.DEBUG = False
        cls.LOG_LEVEL = "INFO"
        cls.WORKERS = 4
        return cls
    
    @classmethod
    def _testing_config(cls):
        """Testing settings."""
        cls.DEBUG = True
        cls.LOG_LEVEL = "DEBUG"
        cls.QUERY_TIMEOUT = 5
        return cls
