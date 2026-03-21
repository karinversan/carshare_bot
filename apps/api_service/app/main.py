from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text

from apps.api_service.app.db.base import Base
from apps.api_service.app.db import models as db_models  # noqa: F401
from apps.api_service.app.db.session import engine
from apps.api_service.app.api.routes.health import router as health_router
from apps.api_service.app.api.routes.assets import router as assets_router
from apps.api_service.app.api.routes.inspections import router as inspections_router
from apps.api_service.app.api.routes.miniapp import router as miniapp_router
from apps.api_service.app.api.routes.comparisons import router as comparisons_router
from apps.api_service.app.api.routes.admin_cases import router as admin_cases_router
from apps.api_service.app.api.routes.auth import router as auth_router
from apps.api_service.app.api.routes.mobile import router as mobile_router

logger = logging.getLogger(__name__)


def _ensure_runtime_columns() -> None:
    try:
        inspector = inspect(engine)
        with engine.begin() as conn:
            manual_columns = {column["name"] for column in inspector.get_columns("manual_damages")}
            if "note" not in manual_columns:
                conn.execute(text("ALTER TABLE manual_damages ADD COLUMN note TEXT"))

            final_columns = {column["name"] for column in inspector.get_columns("inspection_damages_final")}
            if "note" not in final_columns:
                conn.execute(text("ALTER TABLE inspection_damages_final ADD COLUMN note TEXT"))

            image_columns = {column["name"] for column in inspector.get_columns("inspection_images")}
            if "note" not in image_columns:
                conn.execute(text("ALTER TABLE inspection_images ADD COLUMN note TEXT"))
    except Exception as exc:
        logger.warning("Skipping optional runtime schema update: %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        Base.metadata.create_all(bind=engine)
        _ensure_runtime_columns()
    except Exception as exc:
        logger.warning("Skipping database initialization at startup: %s", exc)
    yield


app = FastAPI(title="Car Inspection API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
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
