"""
FastAPI Application - Main entry point following clean architecture
"""

import logging
import os
from datetime import datetime

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from application.rag_service import DocumentRAGService
from infrastructure.config_manager import ConfigManager
from api import router, initialize_rag_service

# Configure logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Get configuration
config = ConfigManager.from_env(os.getenv("ENV", "production"))

# Initialize FastAPI app
app = FastAPI(
    title="Document RAG Engine",
    description="Production-ready REST API for semantic search and document analysis",
    version="2.0.0",
    docs_url="/docs" if config.DEBUG else None,
    redoc_url="/redoc" if config.DEBUG else None,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
    max_age=config.CORS_CACHE_MAX_AGE,
)


@app.middleware("http")
async def require_api_token(request: Request, call_next):
    """Require Electron-generated bearer token when configured."""
    if not config.API_TOKEN:
        return await call_next(request)

    authorization = request.headers.get("Authorization", "")
    if authorization != f"Bearer {config.API_TOKEN}":
        return JSONResponse(status_code=401, content={"detail": "Unauthorized"})

    return await call_next(request)


# Initialize RAG service
try:
    rag_service = DocumentRAGService(
        ollama_url=config.OLLAMA_URL,
        embedding_model=config.EMBEDDING_MODEL,
        llm_model=config.LLM_MODEL,
        temperature=config.LLM_TEMPERATURE,
        chroma_path=config.CHROMA_PATH,
    )
    initialize_rag_service(rag_service)
    logger.info("✅ RAG service initialized successfully")
except Exception as e:
    logger.error(f"❌ Failed to initialize RAG service: {e}", exc_info=True)
    rag_service = None

# Include API routes
app.include_router(router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=config.HOST,
        port=config.PORT,
        log_level=config.LOG_LEVEL.lower(),
        workers=1,
    )
