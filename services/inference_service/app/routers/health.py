from fastapi import APIRouter

from services.inference_service.app.core.config import settings
from services.inference_service.app.model_registry import get_qv_model, get_seg_model

router = APIRouter()

@router.get("/health")
def health():
    qv_model, _ = get_qv_model()
    seg_model, _ = get_seg_model()
    return {
        "ok": True,
        "service": "inference-service",
        "backend": settings.inference_backend,
        "quality_view_loaded": qv_model is not None,
        "damage_seg_loaded": seg_model is not None,
    }
