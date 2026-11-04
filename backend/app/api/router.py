"""
Top-level API router. Aggregates all route modules — see Documentation/API_DOCUMENTATION.md for
the full endpoint list.
"""
from fastapi import APIRouter

from app.api import analytics, auth, demo, entity_detail, health, projects, simulations

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(auth.projects_auth_router)
api_router.include_router(projects.router)
api_router.include_router(analytics.router)
api_router.include_router(entity_detail.router)
api_router.include_router(simulations.router)
api_router.include_router(demo.router)
