# Prompt Gap Audit (MVP Reality Check)

Дата: 2026-03-20

Этот документ фиксирует текущее соответствие проекта исходному промту и оставшиеся разрывы.
Он отражает текущую реализацию и не откатывает пользовательские UX-изменения.

## 1) Product flow

Статус: `PARTIAL / WORKING`

- Telegram bot как основной интерфейс: `DONE`
- Guided capture обязательных ракурсов в Mini App: `DONE`
- PRE -> POST -> comparison -> admin case: `DONE`
- Human-in-the-loop review:
  - Исторические API confirm/reject/uncertain: `DONE`
  - Текущий UX по требованию демо упрощён до авто-решений + ручные добавления: `ADJUSTED`
- Дополнительные close-up фото: `DONE`

## 2) API / Backend

Статус: `DONE (core), PARTIAL (advanced hardening)`

- Inspection lifecycle endpoints: `DONE`
- Mini App endpoints: `DONE`
- Comparison endpoints: `DONE`
- Admin endpoints (+assign): `DONE`
- Mobile orchestration endpoints: `DONE`
- Telegram webhook endpoint: `DONE`

Свежие доработки:
- Исправлена устойчивость admin-cases к "orphan assignee"
- Унифицированы UUID в ответах (строки для фронта)
- Исправлена логика выбора новой машины в боте при активной/return-поездке

## 3) ML inference

Статус: `DONE (demo-grade)`

- Quality + viewpoint gate: `DONE`
- Damage segmentation + overlay: `DONE`
- Diff engine (rule-based): `DONE`
- Авто-решения по confidence-порогам: `DONE`

Примечание:
- В проекте используется практичный демо-режим: часть решений авто-принимается/фильтруется для снижения UI-трения.

## 4) MLOps

Статус: `PARTIAL -> STRONG MVP`

- W&B hooks в training: `DONE (optional runtime)`
- MLflow registration hooks: `DONE (optional runtime)`
- Airflow offline DAGs:
  - dataset_ingestion: `DONE`
  - dataset_validation: `DONE`
  - train_quality_view_model: `DONE`
  - train_damage_seg_model: `DONE`
  - evaluate_models: `DONE`
  - register_best_model: `DONE`
  - generate_eval_report: `DONE`

## 5) Infra / deployment

Статус: `DONE (local), PARTIAL (portfolio K8s)`

- Docker Compose stack: `DONE`
- Local edge proxy for `/api`, `/admin`, `/telegram/webhook`: `DONE`
- Исправлена прокси-маршрутизация `/admin` (без обрезки префикса): `DONE`
- K8s manifests: `DONE (portfolio baseline)`

## 6) Current known gaps

- Не все решения соответствуют "strict production" (это осознанно для учебного MVP).
- Viewpoint model class-space и product-slot semantics упрощены под текущий UX (front / side / rear acceptance logic).
- Часть отчетов может содержать internal artifact paths (в чат-выводе скрыто).

## 7) Recommended next iteration (without architecture overgrowth)

1. Добавить e2e-smoke сценарий `bot -> miniapp -> finalize -> comparison -> admin`.
2. Добавить миграционный smoke-check в CI (alembic upgrade + rollback dry run).
3. Зафиксировать "demo mode" флаг в docs (auto decision policy + thresholds).
4. Добавить легкий seed script для reproducible demo state (1 PRE, 1 POST, 1 admin case).

