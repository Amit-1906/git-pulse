from fastapi import APIRouter
from app.api.v1.endpoints import (
    health,
    repositories,
    pipeline,
    analytics,
    github,
    extraction,
    database,
    transformation,
)

api_v1_router = APIRouter()

api_v1_router.include_router(health.router)
api_v1_router.include_router(repositories.router)
api_v1_router.include_router(pipeline.router)
api_v1_router.include_router(analytics.router)
api_v1_router.include_router(github.router)
api_v1_router.include_router(extraction.router)
api_v1_router.include_router(database.router)
api_v1_router.include_router(transformation.router)
