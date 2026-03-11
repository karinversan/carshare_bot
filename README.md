# Telegram-Based Car Inspection Assistant

Portfolio-grade demo of a Telegram rental flow with guided car inspection, damage review, comparison, and lightweight MLOps packaging.

The goal of this repository is not to imitate a production carsharing platform one-to-one. The goal is to show that the product flow, ML integration, backend logic, and platform tooling are assembled into one coherent system:

- Telegram bot as the user entrypoint
- Telegram Mini App for capture and review
- FastAPI backend for inspections, rentals, comparison, and admin cases
- inference-service for quality/view validation and damage detection
- Airflow, MLflow, Docker Compose, and Kubernetes manifests as portfolio MLOps/infra signals

## What works today

The current demo flow is rental-driven:

1. User opens the bot and chooses a car
2. Bot creates a pickup inspection
3. Mini App collects 4 required views:
   - `front`
   - `left_side`
   - `right_side`
   - `rear`
4. Backend validates uploads, runs inference, and opens review
5. User confirms/rejects detections, adds manual damages, attaches close-ups, and finalizes
6. Rental becomes active
7. User later starts return inspection
8. Backend compares pre-trip and post-trip final states
9. If likely new damage exists, an admin case is created
10. Admin panel shows evidence and lets the reviewer resolve the case

## Runtime boundaries

```text
Telegram Bot
  -> apps/bot_service
  -> apps/api_service/mobile + inspections APIs

Mini App / Admin Panel
  -> apps/miniapp-frontend
  -> apps/admin-panel
  -> apps/api_service

Online inference
  -> services/inference_service

Offline ML / MLOps
  -> ml/
  -> airflow/
  -> MLflow / W&B integration points
```

## Repository map

```text
apps/
  api_service/         FastAPI product backend
  bot_service/         Telegram bot service
  miniapp-frontend/    Telegram Mini App (React + Vite)
  admin-panel/         Admin review UI (React + Vite)
  worker_service/      Celery worker

services/
  inference_service/   Online ML inference boundary

packages/
  shared_py/           Shared backend enums/contracts
  shared-ts/           Shared frontend contracts

ml/
  quality_view/        Quality/view model code and weights
  damage_seg/          Segmentation model code and weights
  evaluation/          Paired comparison evaluation
  data/                Dataset manifests and prepared data

airflow/
  dags/                Offline training / data pipelines

infra/
  compose/             Local Docker Compose stack
  docker/              Service Dockerfiles
  k8s/                 Kubernetes manifests

scripts/
  create_buckets.py
  seed_demo_data.py
  local_edge_proxy.py

docs/
  architecture/
  api/
  data/
  deployment/
  ml/
  runbooks/

tests/
  Backend / inference / logic tests
```

Detailed folder ownership lives in `docs/architecture/repo-layout.md`.

## Service architecture notes

### Bot service

`apps/bot_service/app` is now split by responsibility:

- `main.py`: FastAPI entrypoint and Telegram update orchestration
- `ui.py`: keyboards, welcome card image, Telegram menu behavior, editable status-panel behavior, and user-facing text formatting
- `api_client.py`: product API client
- `state.py`: lightweight in-memory bot state for the demo

### API service

`apps/api_service/app` keeps product logic centralized:

- `main.py`: entrypoint, startup wiring, CORS, and router registration
- `api/routes/`: HTTP contracts grouped by product surface
- `services/`: orchestration logic
- `domain/`: comparison/domain logic
- `db/`: SQLAlchemy models and session
- `schemas/`: Pydantic contracts

### Inference service

`services/inference_service` stays as the online ML boundary:

- model loading / registry resolution
- quality + viewpoint inference
- damage segmentation inference
- health/status endpoints

Training code stays in `ml/` and is intentionally separate from online serving.

## Demo-first design choices

This repository is intentionally optimized for:

- showing end-to-end backend ownership
- showing ML integration in a product
- showing MLOps packaging and infrastructure awareness
- keeping the code runnable locally

It is intentionally not optimized for:

- full production auth/security hardening
- multi-region reliability
- large-scale queueing/event architecture
- perfect dataset quality or perfect model calibration

## Quick start

### 1. Prepare env

```bash
cp .env.example .env
```

### 2. Start the local stack

```bash
docker compose -f infra/compose/docker-compose.yml up --build
```

### 3. Bootstrap buckets and demo data

```bash
make bootstrap
```

### 4. Open services

- API docs: `http://localhost:8000/docs`
- Mini App dev server: `http://localhost:5173`
- Admin panel dev server: `http://localhost:5174`
- MLflow: `http://localhost:5000`
- Airflow: `http://localhost:8080`

## Local dev commands

```bash
make api
make bot
make worker
make inference
make test
```

## Telegram setup

1. Create the bot via BotFather
2. Put the token into `.env`
3. Expose the bot with `ngrok` or `cloudflared`
4. Set webhook:

```bash
curl -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/setWebhook" \
  -d "url=${PUBLIC_WEBHOOK_URL}/telegram/webhook" \
  -d "secret_token=${TELEGRAM_WEBHOOK_SECRET}"
```

The bot now uses contextual Telegram menu buttons:

- default state: regular commands
- active inspection: Mini App button for the current inspection only

## ML modes

The project supports two realistic demo modes:

- `mock`: easiest product-flow demo without real weights
- `weights`: local real-model loading from repo weights/artifacts

The online inference boundary remains the same either way, so the rest of the backend flow does not change.

## Using custom segmentation weights

The inference service can load a local YOLO segmentation checkpoint directly from `.env`:

```bash
DAMAGE_SEG_WEIGHTS_PATH=/absolute/path/to/model.pt
DAMAGE_SEG_METADATA_PATH=
```

Recommended usage for future distribution:

1. Publish the checkpoint to Hugging Face
2. Download it locally
3. Point `DAMAGE_SEG_WEIGHTS_PATH` to the downloaded `.pt`
4. Restart `inference-service`

Example:

```bash
huggingface-cli download <repo-id> best_yolo11n_cardd_seg_from_coco_kaggle.pt --local-dir ./artifacts
```

Then set:

```bash
DAMAGE_SEG_WEIGHTS_PATH=/absolute/path/to/artifacts/best_yolo11n_cardd_seg_from_coco_kaggle.pt
```

Notes:

- existing weights inside the repository can remain in place as archive/fallback
- you do not need to delete old repo weights to use a new checkpoint
- if your custom checkpoint already contains class names, `DAMAGE_SEG_METADATA_PATH` can stay empty

## What to show in a demo

If your goal is to demonstrate engineering breadth, the cleanest walkthrough is:

1. Start the stack
2. Show repo layout and architecture
3. Start a rental in Telegram
4. Complete pickup inspection in Mini App
5. Show comparison/admin case after return inspection
6. Open admin panel and resolve the case
7. Show Airflow DAGs, MLflow, and the `ml/` structure as the offline ML/MLOps layer

## Key docs

- `docs/architecture/architecture.md`
- `docs/architecture/repo-layout.md`
- `docs/api/api.md`
- `docs/data/data.md`
- `docs/ml/training.md`
- `docs/ml/inference.md`
- `docs/ml/mlops.md`
- `docs/deployment/deployment.md`
- `docs/known-limitations.md`
- `docs/runbooks/prompt-gap-audit.md`
- `docs/runbooks/e2e-smoke.md`

## Known limitations

This is still a demo system. The main constraints are:

- public research datasets do not fully match rental-style inspection images
- quality/view validation still depends on the current training label space
- some demo conveniences remain in place for local launch and showcase speed

Those tradeoffs are documented explicitly rather than hidden.
