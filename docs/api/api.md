# API

Main routes:
- POST /inspections
- GET /inspections/{id}
- POST /inspections/{id}/images
- POST /inspections/{id}/run-initial-checks
- POST /inspections/{id}/run-damage-inference
- POST /inspections/{id}/finalize

- GET /miniapp/inspections/{id}
- POST /miniapp/damages/{id}/confirm
- POST /miniapp/damages/{id}/reject
- POST /miniapp/damages/{id}/uncertain
- POST /miniapp/damages/manual
- POST /miniapp/images/{id}/attach-closeup

- POST /comparisons/run
- GET /comparisons/{id}

- GET /admin-cases
- GET /admin-cases/{id}
- POST /admin-cases/{id}/status
- POST /admin-cases/{id}/assign

Mobile/runtime orchestration:
- GET /mobile/dashboard
- POST /mobile/trips/start
- POST /mobile/trips/{id}/return
- POST /mobile/trips/{id}/cancel
- GET /mobile/inspections/{id}/context

Bot webhook:
- POST /telegram/webhook
