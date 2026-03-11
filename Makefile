SHELL := /bin/bash

bootstrap:
	python scripts/create_buckets.py
	python scripts/seed_demo_data.py

test:
	pytest -q

format:
	python -m black apps services packages ml tests scripts

lint:
	python -m ruff check apps services packages ml tests scripts

api:
	uvicorn apps.api_service.app.main:app --reload --port 8000

bot:
	uvicorn apps.bot_service.app.main:app --reload --port 8001

worker:
	celery -A apps.worker_service.app.celery_app.celery_app worker --loglevel=INFO

inference:
	uvicorn services.inference_service.app.main:app --reload --port 8010
