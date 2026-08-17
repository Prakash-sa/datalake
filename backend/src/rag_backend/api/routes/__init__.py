"""Route modules, aggregated into a single API router."""

from fastapi import APIRouter

from rag_backend.api.routes import documents, evals, health, models, search, settings

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(models.router)
api_router.include_router(settings.router)
api_router.include_router(documents.router)
api_router.include_router(search.router)
api_router.include_router(evals.router)

__all__ = ["api_router"]
