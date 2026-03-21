# Car Inspection Assistant

<p align="center">
  Portfolio-grade Telegram car inspection workflow: Bot + Mini App + FastAPI backend + inference service + lightweight MLOps stack.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white" alt="Python 3.11" />
  <img src="https://img.shields.io/badge/FastAPI-0.115+-009688?logo=fastapi&logoColor=white" alt="FastAPI" />
  <img src="https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=black" alt="React 18" />
  <img src="https://img.shields.io/badge/Vite-5-646CFF?logo=vite&logoColor=white" alt="Vite 5" />
  <img src="https://img.shields.io/badge/Telegram-Bot%20%2B%20Mini%20App-26A5E4?logo=telegram&logoColor=white" alt="Telegram" />
  <img src="https://img.shields.io/badge/PostgreSQL-16-316192?logo=postgresql&logoColor=white" alt="PostgreSQL 16" />
  <img src="https://img.shields.io/badge/Redis-7-DC382D?logo=redis&logoColor=white" alt="Redis 7" />
  <img src="https://img.shields.io/badge/MLflow-2.14-0194E2?logo=mlflow&logoColor=white" alt="MLflow" />
  <img src="https://img.shields.io/badge/Airflow-2.9-017CEE?logo=apacheairflow&logoColor=white" alt="Airflow 2.9" />
  <img src="https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white" alt="Docker Compose" />
</p>

An end-to-end demo of a rental-driven car inspection product. The project combines a Telegram entrypoint, a Mini App for guided photo capture, a FastAPI backend for inspections and comparisons, an admin review panel, an online inference boundary, and an offline ML / MLOps layer.

---

## Highlights

- **Telegram-first flow**: the bot starts the rental, opens the inspection, and keeps the user inside a simple guided journey.
- **Guided capture**: the Mini App enforces 4 required views and sends images through quality / viewpoint validation and damage detection.
- **Damage review loop**: users can confirm detections, reject them, add manual damages, attach close-ups, and finalize the inspection.
- **Pre/post comparison**: pickup and return inspections are compared to surface likely new damages.
- **Admin case handling**: a separate admin panel shows evidence, review status, and resolution controls.
- **Realistic ML packaging**: inference runs as an isolated service with `mock`, `weights`, and MLflow-oriented loading paths.
- **MLOps signals included**: Airflow DAGs, MLflow registry wiring, MinIO buckets, training code, evaluation scripts, and Docker Compose.

---

## Prediction examples

<table>
  <tr>
    <td align="center">
      <img src="docs/screenshots/prediction-accepted.png" width="320" alt="Accepted capture" /><br/>
      <sub>Accepted capture: correct slot and acceptable quality</sub>
    </td>
    <td align="center">
      <img src="docs/screenshots/prediction-quality-reject.png" width="320" alt="Rejected quality" /><br/>
      <sub>Rejected capture: unsuitable photo quality</sub>
    </td>
  </tr>
  <tr>
    <td align="center">
      <img src="docs/screenshots/prediction-view-mismatch.png" width="320" alt="Wrong viewpoint" /><br/>
      <sub>Rejected capture: wrong viewpoint for the expected slot</sub>
    </td>
    <td align="center">
      <img src="docs/screenshots/prediction-segmentation.png" width="320" alt="Damage segmentation" /><br/>
      <sub>Damage segmentation: polygons, classes and confidence scores</sub>
    </td>
  </tr>
  <tr>
    <td align="center" colspan="2">
      <img src="docs/screenshots/prediction-classification.png" width="620" alt="Finding classification and review states" /><br/>
      <sub>Finding classification and review states: autoconfirmed, uncertain and filtered results</sub>
    </td>
  </tr>
</table>

Typical outcomes shown by the current pipeline:

- **accepted capture**: `quality_label=good`, predicted view matches the expected slot, the frame goes to damage inference;
- **unsuitable photo**: the quality gate can reject `too_blurry`, `too_dark`, or `overexposed` frames;
- **wrong viewpoint**: the frame can be rejected even with acceptable quality if `predicted_view` does not match `expected_slot`;
- **damage segmentation**: the service returns polygons, boxes, confidence, overlay image, and damage classes such as `scratch`, `dent`, `crack`, `broken_part`;
- **review classification**: predicted damages can be auto-confirmed, sent to admin review, or filtered out depending on confidence and review rules.

---

## Interface walkthrough

<table>
  <tr>
    <td align="center">
      <img src="docs/screenshots/bot-entry.png" width="220" alt="Telegram bot entry" /><br/>
      <sub>Telegram entry</sub>
    </td>
    <td align="center">
      <img src="docs/screenshots/miniapp-capture.png" width="220" alt="Mini App guided capture" /><br/>
      <sub>Guided capture</sub>
    </td>
  </tr>
  <tr>
    <td align="center">
      <img src="docs/screenshots/miniapp-grid.png" width="220" alt="Required views ready" /><br/>
      <sub>Required views ready</sub>
    </td>
    <td align="center">
      <img src="docs/screenshots/miniapp-review.png" width="220" alt="Damage review" /><br/>
      <sub>Damage review</sub>
    </td>
  </tr>
  <tr>
    <td align="center">
      <img src="docs/screenshots/miniapp-closeups.png" width="220" alt="Manual review and closeups" /><br/>
      <sub>Manual review and close-ups</sub>
    </td>
    <td align="center">
      <img src="docs/screenshots/admin-queue.png" width="320" alt="Admin queue" /><br/>
      <sub>Admin queue</sub>
    </td>
  </tr>
  <tr>
    <td align="center" colspan="2">
      <img src="docs/screenshots/admin-case-detail.png" width="560" alt="Admin case detail" /><br/>
      <sub>Case detail with evidence and resolution actions</sub>
    </td>
  </tr>
</table>

---

## Models used

| Component | Model | Role | Where it is defined |
|---|---|---|---|
| Quality gate | **EfficientNet-B0** | binary accept / reject quality classification | `ml/quality_view/configs/quality_gate_config.json` |
| View validation | **EfficientNet-B0** | 5-class viewpoint / validity classification | `ml/quality_view/configs/view_validation_config.json` |
| Legacy QV experiment | **EfficientNet-B0 multitask** | joint quality + viewpoint prediction experiment | `ml/quality_view/configs/efficientnet_b0_multitask.yaml` |
| Damage segmentation baseline | **YOLOv8s-seg** | segmentation of scratches / dents / cracks / broken parts | `ml/damage_seg/configs/yolo_seg_v1.yaml`, `ml/damage_seg/configs/yolo_seg_v2.json` |
| Latest evaluated external artifact | **YOLO11n-seg checkpoint** | external checkpoint referenced by the latest quality report | `ml/evaluation/reports/model_quality_latest.json` |

### Model notes

- The current runtime loader supports **split EfficientNet-B0 classifiers** for quality gate and view validation, and also keeps compatibility with an older multitask EfficientNet-B0 checkpoint.
- The damage-seg training configs inside the repo are built around **Ultralytics YOLO segmentation** baselines, primarily `yolov8s-seg.pt`.
- The latest aggregated evaluation report references an **external YOLO11n segmentation checkpoint** as the active evaluated artifact, which is why the repo currently shows both YOLOv8-seg training configs and a YOLO11n-based result in reports.

---

## What is implemented

- **Product backend** in `apps/api_service/`:
  rentals, inspections, uploads, comparisons, admin cases, auth helpers, object storage integration.
- **Telegram bot service** in `apps/bot_service/`:
  rental selection, trip status, inspection launch, return flow, menu sync, and status panels.
- **Mini App frontend** in `apps/miniapp-frontend/`:
  guided image capture, review state, and inspection completion flow.
- **Admin panel** in `apps/admin-panel/`:
  review queue for probable new damage cases.
- **Inference service** in `services/inference_service/`:
  quality / viewpoint validation and damage segmentation behind stable API contracts.
- **Worker service** in `apps/worker_service/`:
  background-task boundary for async processing.
- **Offline ML layer** in `ml/`:
  training, evaluation, dataset preparation, reports, and model configs.
- **Infra / orchestration** in `infra/` and `airflow/`:
  Docker Compose, service Dockerfiles, Airflow DAGs, and deployment-oriented structure.

---

## Product flow

```text
Telegram Bot
    -> user selects a car
    -> backend creates pickup inspection

Mini App
    -> collects 4 required views
    -> uploads images
    -> receives quality/view + damage predictions
    -> user confirms / edits final damages

Backend
    -> stores inspection state
    -> finalizes rental start
    -> later creates return inspection
    -> compares pre-trip and post-trip final states

Admin Panel
    -> receives probable new-damage cases
    -> reviewer resolves the case
```

Required capture slots:

- `front`
- `left_side`
- `right_side`
- `rear`

---

## Architecture

```text
┌──────────────────────┐
│    Telegram User     │
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│  bot-service         │
│  FastAPI + Telegram  │
└──────────┬───────────┘
           ▼
┌──────────────────────────────────────────────┐
│ api-service                                  │
│ rentals / inspections / comparison / admin   │
└──────┬───────────────┬───────────────┬───────┘
       │               │               │
       ▼               ▼               ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│ PostgreSQL   │ │ MinIO        │ │ Redis        │
│ app state    │ │ images/files │ │ async/cache  │
└──────────────┘ └──────────────┘ └──────────────┘
       │
       ├──────────────────────────────┐
       ▼                              ▼
┌──────────────┐              ┌──────────────────┐
│ worker       │              │ inference-service│
│ Celery tasks │              │ QV + damage seg  │
└──────────────┘              └──────────────────┘

Frontend surfaces:
- `apps/miniapp-frontend`  -> Telegram Mini App
- `apps/admin-panel`       -> reviewer UI

Offline ML / MLOps:
- `ml/`                    -> training, evaluation, dataset prep
- `airflow/dags/`          -> offline pipelines
- `mlflow`                 -> model registry / experiment tracking
```

---

## How the project was built

The project was designed as a portfolio system rather than a single-model demo. The goal was to make the product flow tangible: not only detect damage, but also model the surrounding product behavior that a real inspection process needs.

The implementation was split into clear runtime boundaries:

- **product logic** in the API service
- **conversation and UX orchestration** in the bot service
- **capture / review UI** in the Mini App
- **online ML inference** in a dedicated inference service
- **offline training and evaluation** in `ml/`
- **ops packaging** via Docker Compose, Airflow, MLflow, Redis, Postgres, and MinIO

That split keeps the demo understandable while still showing backend ownership, ML integration, and infra awareness.

---

## ML and inference layer

### Inference modes

The inference boundary supports multiple modes:

- `mock`:
  quickest local demo mode with stable response contracts
- `weights`:
  loads local quality / viewpoint and damage segmentation checkpoints
- `mlflow`:
  MLflow-oriented loading path for registered models

### Quality / viewpoint validation

- implemented in `services/inference_service/app/routers/quality_view.py`
- supports heuristic fallback and real EfficientNet-based model loading
- returns acceptance decision, predicted view, quality label, confidence, and rejection reason

### Damage segmentation

- implemented in `services/inference_service/app/routers/damage_seg.py`
- supports deterministic mock inference and real YOLO segmentation inference
- returns polygons, normalized boxes, centroids, confidence, area, and overlay PNG

### Offline ML / MLOps

- quality-view training: `ml/quality_view/`
- damage segmentation training: `ml/damage_seg/`
- paired evaluation: `ml/evaluation/`
- Airflow DAGs:
  `dataset_ingestion`, `dataset_validation`, `train_quality_view_model`,
  `train_damage_seg_model`, `evaluate_models`, `register_best_model`, `generate_eval_report`

---

## Results

Latest aggregated metrics from `ml/evaluation/reports/model_quality_latest.json`:

| Component | Metric | Value |
|---|---|---:|
| Quality gate | Accuracy | **0.9213** |
| Quality gate | Macro F1 | **0.9212** |
| Quality gate | Reject precision | **0.9318** |
| Quality gate | Reject recall | **0.9091** |
| View validation | Accuracy | **0.9448** |
| View validation | Macro F1 | **0.9444** |
| Damage segmentation | Mask mAP@50 | **0.6718** |
| Damage segmentation | Mask mAP@50-95 | **0.4889** |
| Damage segmentation | Precision | **0.7142** |
| Damage segmentation | Recall | **0.6818** |

Per-class F1 for view validation:

| Class | F1 |
|---|---:|
| `front_valid` | **0.9436** |
| `rear_valid` | **0.9610** |
| `side_valid` | **0.9460** |
| `angled_invalid` | **0.8983** |
| `other_invalid` | **0.9732** |

Interpretation:

- the **quality gate** is already strong enough for a demo workflow and keeps false rejects under reasonable control;
- the **view validator** is the most stable classifier in the current stack;
- the **damage segmentation** result is the most experimental part and depends strongly on which checkpoint is active.

Detailed reports:

- `ml/quality_view/reports/quality_gate_test_report.json`
- `ml/quality_view/reports/view_validation_test_report.json`
- `ml/evaluation/reports/model_quality_latest.json`

---

## Quickstart

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

### 4. Open interfaces

- API docs: `http://localhost:8000/docs`
- Bot service: `http://localhost:8001`
- Inference service: `http://localhost:8010/docs`
- Mini App: `http://localhost:5173`
- Admin panel: `http://localhost:5174`
- MinIO: `http://localhost:9001`
- MLflow: `http://localhost:5000`
- Airflow: `http://localhost:8080`

---

## Local development

### Backend / services

```bash
make api
make bot
make worker
make inference
make test
```

### Formatting and lint

```bash
make format
make lint
```

### Frontend

```bash
cd apps/miniapp-frontend
npm install
npm run dev

cd apps/admin-panel
npm install
npm run dev
```

---

## Telegram setup

1. Create the bot via BotFather.
2. Put `TELEGRAM_BOT_TOKEN` into `.env`.
3. Expose the bot with `ngrok` or `cloudflared`.
4. Set the webhook:

```bash
curl -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/setWebhook" \
  -d "url=${PUBLIC_WEBHOOK_URL}/telegram/webhook" \
  -d "secret_token=${TELEGRAM_WEBHOOK_SECRET}"
```

The bot supports contextual menu behavior:

- default state -> regular commands
- active inspection -> Mini App button for the current inspection

---

## Repository structure

```text
apps/
  api_service/         FastAPI product backend
  bot_service/         Telegram bot service
  miniapp-frontend/    React + Vite Telegram Mini App
  admin-panel/         React + Vite admin UI
  worker_service/      Celery worker

services/
  inference_service/   online ML inference boundary

packages/
  shared_py/           shared backend enums and contracts
  shared-ts/           generated frontend types

ml/
  quality_view/        quality / viewpoint model training
  damage_seg/          damage segmentation training
  evaluation/          paired evaluation and reports
  data/                local datasets and prepared manifests

airflow/
  dags/                offline ML pipelines

infra/
  compose/             local stack
  docker/              service Dockerfiles

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
  backend / bot / inference / smoke tests
```

Detailed layout notes: `docs/architecture/repo-layout.md`

---

## Data and model artifacts

This repository is structured so that **code and configs live in Git**, while heavy local assets stay outside of version control.

Not stored in Git:

- local datasets in `ml/data/`
- local training runs
- model weights and large artifacts
- `.env` and private credentials
- generated frontend build output and local virtual environments

Public bootstrap datasets referenced by the project:

- **CarDD**
- **TQVCD**
- **CrashCar101** as augmentation source only

Important caveat: these are research bootstrap datasets and do not fully reproduce real rental-inspection conditions. The intended long-term setup is a custom paired protocol with repeated inspections of the same vehicles.

---

## Demo walkthrough

If the goal is to show engineering breadth, the cleanest walkthrough is:

1. Start the local stack.
2. Open the repository structure and explain the service boundaries.
3. Start a rental in Telegram.
4. Complete the pickup inspection in the Mini App.
5. Confirm or edit predicted damages.
6. Start a return inspection.
7. Show the comparison result and created admin case.
8. Resolve the case in the admin panel.
9. Show Airflow DAGs, MLflow, and the `ml/` folder as the offline layer.

---

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
- `docs/runbooks/e2e-smoke.md`
- `docs/runbooks/prompt-gap-audit.md`

---

## Limitations

- This is a **demo-first** system, not a production-hardened carsharing platform.
- Public research datasets do not perfectly match real inspection photos and paired pre/post evidence.
- Some flows are simplified to keep the stack runnable locally and easier to demo.
- Inference can fall back to mock behavior depending on selected backend and available weights.
- Security, auth hardening, and large-scale ops concerns are intentionally out of scope for this repository.
