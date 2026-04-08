SHELL := /bin/bash

migrate:
	uv run alembic -c apps/api_service/alembic.ini upgrade head

bootstrap: migrate
	uv run python scripts/create_buckets.py
	uv run python scripts/seed_demo_data.py

test:
	uv run pytest -q

format:
	uv run python -m black apps services packages ml tests scripts

lint:
	uv run python -m ruff check apps services packages ml tests scripts

api: migrate
	uv run uvicorn apps.api_service.app.main:app --reload --port 8000

bot:
	uv run uvicorn apps.bot_service.app.main:app --reload --port 8001

worker:
	uv run celery -A apps.worker_service.app.celery_app.celery_app worker --loglevel=INFO

inference:
	uv run uvicorn services.inference_service.app.main:app --reload --port 8010
