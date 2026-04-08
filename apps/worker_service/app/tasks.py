"""Celery tasks for async inference and comparison processing.

These tasks run in a worker process separate from the API,
allowing the API to return immediately (202 Accepted) while
heavy ML inference happens in the background.
"""

import logging
import os

from apps.worker_service.app.celery_app import celery_app

logger = logging.getLogger(__name__)
API_BASE_URL = os.getenv("API_BASE_URL") or os.getenv("API_SERVICE_URL", "http://api-service:8000")
INTERNAL_SERVICE_TOKEN = os.getenv("INTERNAL_SERVICE_TOKEN", "change-me-internal")


@celery_app.task(bind=True, max_retries=2, default_retry_delay=10)
def run_damage_inference_task(self, inspection_id: str):
    """Run damage segmentation on all accepted images for an inspection.

    Strategy: calls back to the API's run-damage-inference endpoint.
    This keeps the DB logic in the API process, while the heavy ML
    inference (called by the API → inference-service) is off-loaded
    from the user-facing request.
    """
    import httpx
    try:
        logger.info("Starting damage inference for inspection %s", inspection_id)
        resp = httpx.post(
            f"{API_BASE_URL}/inspections/{inspection_id}/run-damage-inference?force_sync=true",
            headers={"X-Internal-Service-Token": INTERNAL_SERVICE_TOKEN},
            timeout=180.0,
        )
        resp.raise_for_status()
        logger.info("Damage inference complete for %s: %s", inspection_id, resp.json())
        return resp.json()
    except httpx.HTTPStatusError as e:
        logger.error("HTTP error for inference %s: %s %s", inspection_id, e.response.status_code, e.response.text)
        raise self.retry(exc=e)
    except httpx.ConnectError as e:
        logger.error("Connection error for inference %s: %s", inspection_id, e)
        raise self.retry(exc=e)
    except Exception as e:
        logger.error("Unexpected error for inference %s: %s", inspection_id, e, exc_info=True)
        # Mark inspection as failed via API
        try:
            httpx.post(
                f"{API_BASE_URL}/inspections/{inspection_id}/mark-failed",
                json={"reason": str(e)},
                headers={"X-Internal-Service-Token": INTERNAL_SERVICE_TOKEN},
                timeout=10.0,
            )
        except Exception:
            pass
        raise


@celery_app.task(bind=True, max_retries=2, default_retry_delay=10)
def run_comparison_task(self, post_session_id: str):
    """Run PRE vs POST trip comparison for a finalized POST inspection.

    Called after finalize if async_comparison is enabled.
    """
    import httpx
    try:
        logger.info("Starting comparison for post_session %s", post_session_id)
        resp = httpx.post(
            f"{API_BASE_URL}/comparisons/run",
            json={"post_session_id": post_session_id},
            headers={"X-Internal-Service-Token": INTERNAL_SERVICE_TOKEN},
            timeout=120.0,
        )
        resp.raise_for_status()
        logger.info("Comparison complete for %s: %s", post_session_id, resp.json())
        return resp.json()
    except httpx.HTTPStatusError as e:
        logger.error("HTTP error for comparison %s: %s", post_session_id, e.response.text)
        raise self.retry(exc=e)
    except httpx.ConnectError as e:
        logger.error("Connection error for comparison %s: %s", post_session_id, e)
        raise self.retry(exc=e)
    except Exception as e:
        logger.error("Unexpected error for comparison %s: %s", post_session_id, e, exc_info=True)
        raise
