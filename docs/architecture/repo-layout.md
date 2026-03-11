# Repo Layout

This repository is organized as a practical monorepo with four clear boundaries:

1. product runtime
2. online ML serving
3. offline ML / training
4. infrastructure / deployment

## Top-level ownership

### `apps/`

User-facing and product-facing runtime applications.

- `apps/api_service/`
  - main FastAPI backend
  - owns inspections, rentals, review decisions, comparisons, admin cases
- `apps/bot_service/`
  - Telegram integration layer
  - owns chat UX, bot state, menu behavior, and bot-to-API orchestration
- `apps/miniapp-frontend/`
  - Telegram Mini App
  - owns capture/review UX
- `apps/admin-panel/`
  - admin reviewer UI
  - owns case queue and evidence review surface
- `apps/worker_service/`
  - background jobs
  - owns async product tasks

Rule:
If the code is part of the user or operator runtime, it belongs in `apps/`.

### `services/`

Runtime services that are not direct user-facing apps.

- `services/inference_service/`
  - online ML inference boundary
  - model loading
  - quality/view prediction
  - damage segmentation prediction

Rule:
If the code serves ML predictions online and can be deployed independently, it belongs in `services/`.

### `ml/`

Offline ML code and artifacts.

- `ml/quality_view/`
- `ml/damage_seg/`
- `ml/evaluation/`
- `ml/data/`
- `ml/utils/`

Rule:
If the code is used for training, evaluation, dataset prep, reporting, or model experimentation, it belongs in `ml/`, not in runtime apps.

### `packages/`

Shared contracts.

- `packages/shared_py/`
  - enums and shared backend/domain contracts
- `packages/shared-ts/`
  - shared frontend contracts

Rule:
If multiple services need the same contract and it is not business logic by itself, it belongs in `packages/`.

### `airflow/`

Offline orchestration only.

- `airflow/dags/`
  - ingestion
  - training
  - evaluation
  - registration flows

Rule:
Airflow should orchestrate offline ML/data work, not online request-time product behavior.

### `infra/`

Deployment and environment definitions.

- `infra/compose/`
- `infra/docker/`
- `infra/k8s/`

Rule:
If it defines how the system runs, not what the system does, it belongs in `infra/`.

### `scripts/`

Repo-level operational helpers.

Examples:
- bucket bootstrap
- demo data seed
- local edge proxy

Rule:
If the file is a convenience entrypoint or environment helper and not part of core runtime behavior, it belongs in `scripts/`.

### `docs/`

Documentation by topic, not by service.

- `docs/architecture/`
- `docs/api/`
- `docs/data/`
- `docs/deployment/`
- `docs/ml/`
- `docs/runbooks/`

Rule:
Docs should explain boundaries, workflows, and operating instructions. They should not become hidden source-of-truth replacements for the code.

## Internal service layout

### `apps/api_service/app/`

- `main.py`
  - FastAPI entrypoint, startup wiring, database init hook, CORS, and router registration
- `api/routes/`
  - HTTP surfaces grouped by product area
- `services/`
  - orchestration and side-effect-heavy use cases
- `domain/`
  - pure-ish business/domain logic
- `db/`
  - persistence layer
- `schemas/`
  - request/response contracts

Recommended rule:
- route files stay thin
- domain files stay logic-focused
- service files coordinate IO and orchestration

### `apps/bot_service/app/`

- `main.py`
  - Telegram update handling and service orchestration
- `ui.py`
  - keyboards, message text, welcome card rendering, editable status panel, and Telegram menu-button behavior
- `api_client.py`
  - API transport
- `state.py`
  - demo bot state

Recommended rule:
- `main.py` should not own rendering details
- anything purely presentational belongs in `ui.py`
- Telegram surface helpers should stay grouped in `ui.py` unless that file becomes too large

## Practical placement rules for future changes

- New product endpoint:
  add route in `apps/api_service/app/api/routes/` and orchestration in `services/`
- New pure comparison/matching logic:
  place in `apps/api_service/app/domain/`
- New Telegram text/button/layout behavior:
  place in `apps/bot_service/app/ui.py`
- New Telegram chat-edit/menu behavior:
  keep it in `apps/bot_service/app/ui.py` until there is a clear reason to split it out
- New training experiment:
  place in `ml/...`
- New model-serving endpoint:
  place in `services/inference_service/...`

## What this layout optimizes for

- easier demo navigation
- clear separation between product and ML concerns
- easier explanation in interviews / portfolio walkthroughs
- less accidental mixing of runtime code and experimentation code

It intentionally does not optimize for:

- deep microservice decomposition
- production-grade platform complexity
- extreme modularization at the cost of demo readability
