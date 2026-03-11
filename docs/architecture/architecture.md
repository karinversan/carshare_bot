# Architecture

See the root README for the full system overview.
See `docs/architecture/repo-layout.md` for the ownership map of the monorepo.

## Runtime services
- api-service
- bot-service
- worker-service
- inference-service
- miniapp-frontend
- admin-panel
- postgres
- redis
- minio
- mlflow
- airflow

## Product logic boundary
Product logic lives primarily in:

- `apps/api_service/app/domain`
- `apps/api_service/app/services`
- `apps/bot_service/app`
- `apps/miniapp-frontend/src`
- `apps/admin-panel/src`

## ML logic boundary
Online ML boundary lives in:

- `services/inference_service`

Offline training and evaluation live in:

- `ml/`

## MLOps boundary
- W&B logging: `ml/*`
- MLflow integration points: `ml/*` and runtime config
- Airflow DAGs: `airflow/dags/`
- deployment definitions: `infra/compose`, `infra/docker`, `infra/k8s`
