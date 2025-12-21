"""
Production-ready configuration for Document RAG Engine
Centralized settings for all environments
"""

import os
from typing import Optional

class Config:
    """Base configuration."""
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
    CHROMA_PATH: str = os.getenv("CHROMA_PATH", "./chroma_db")
    
    # Resource Limits
    MAX_DOCUMENTS: int = int(os.getenv("MAX_DOCUMENTS", "10000"))
    MAX_QUERY_LENGTH: int = int(os.getenv("MAX_QUERY_LENGTH", "1000"))
    MAX_RESULTS: int = int(os.getenv("MAX_RESULTS", "100"))
    QUERY_TIMEOUT: int = int(os.getenv("QUERY_TIMEOUT", "30"))
    
    # Performance Settings
    EMBEDDING_CACHE_SIZE: int = int(os.getenv("EMBEDDING_CACHE_SIZE", "128"))
    CORS_CACHE_MAX_AGE: int = int(os.getenv("CORS_CACHE_MAX_AGE", "600"))
    
    # Monitoring
    ENABLE_METRICS: bool = os.getenv("ENABLE_METRICS", "true").lower() == "true"
    METRICS_PORT: int = int(os.getenv("METRICS_PORT", "9090"))


class DevelopmentConfig(Config):
    """Development environment configuration."""
    ENV = "development"
    DEBUG = True
    LOG_LEVEL = "DEBUG"
    WORKERS = 1
    ALLOWED_ORIGINS = ["*"]  # Allow all origins in development


class ProductionConfig(Config):
    """Production environment configuration."""
    ENV = "production"
    DEBUG = False
    LOG_LEVEL = "INFO"
    WORKERS = int(os.getenv("WORKERS", "4"))
    ALLOWED_ORIGINS = [
        o.strip() for o in os.getenv("ALLOWED_ORIGINS", "https://example.com").split(",")
    ]


class TestingConfig(Config):
    """Testing environment configuration."""
    ENV = "testing"
    DEBUG = True
    LOG_LEVEL = "DEBUG"
    OLLAMA_URL = "http://localhost:11434"
    QUERY_TIMEOUT = 5


def get_config() -> Config:
    """Get configuration based on environment."""
    env = os.getenv("ENV", "production").lower()
    
    if env == "development":
        return DevelopmentConfig()
    elif env == "testing":
        return TestingConfig()
    else:
        return ProductionConfig()


# Export current config
config = get_config()
