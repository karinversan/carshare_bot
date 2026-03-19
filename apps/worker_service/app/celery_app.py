from celery import Celery
import os

celery_app = Celery(
    "car_inspection_worker",
    broker=os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/1"),
    backend=os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/2"),
)

celery_app.conf.task_routes = {
    "apps.worker_service.app.tasks.run_damage_inference_task": {"queue": "inference"},
    "apps.worker_service.app.tasks.run_comparison_task": {"queue": "comparison"},
}
