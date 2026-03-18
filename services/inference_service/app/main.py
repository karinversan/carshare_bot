import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from services.inference_service.app.routers.health import router as health_router
from services.inference_service.app.routers.quality_view import router as quality_view_router
from services.inference_service.app.routers.damage_seg import router as damage_seg_router
from services.inference_service.app.model_registry import startup_load_models

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load ML models at startup."""
    logger.info("Inference service starting — loading models...")
    startup_load_models()
    logger.info("Inference service ready.")
    yield
    logger.info("Inference service shutting down.")


app = FastAPI(
    title="Car Inspection Inference Service",
    version="0.2.0",
    lifespan=lifespan,
)
app.include_router(health_router)
app.include_router(quality_view_router)
app.include_router(damage_seg_router)
