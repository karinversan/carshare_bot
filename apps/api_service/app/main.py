from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apps.api_service.app.core.config import settings
from apps.api_service.app.api.routes.health import router as health_router
from apps.api_service.app.api.routes.assets import router as assets_router
from apps.api_service.app.api.routes.inspections import router as inspections_router
from apps.api_service.app.api.routes.miniapp import router as miniapp_router
from apps.api_service.app.api.routes.comparisons import router as comparisons_router
from apps.api_service.app.api.routes.admin_cases import router as admin_cases_router
from apps.api_service.app.api.routes.auth import router as auth_router
from apps.api_service.app.api.routes.mobile import router as mobile_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(title="Car Inspection API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.effective_cors_allowed_origins or ["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(assets_router)
app.include_router(inspections_router)
app.include_router(miniapp_router)
app.include_router(comparisons_router)
app.include_router(admin_cases_router)
app.include_router(auth_router)
app.include_router(mobile_router)
