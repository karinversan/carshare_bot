# E2E Smoke (API + Core Product Flow)

Дата: 2026-03-21

## Результат

PASS

- `uv run pytest -q tests/test_e2e_smoke_flow.py`
- `uv run pytest -q tests/test_bot_message_flow.py tests/test_bot_trip_flow.py tests/test_bot_state.py tests/test_admin_cases_route.py tests/test_e2e_smoke_flow.py`
- `uv run pytest -q`
- `npm run build` in `apps/miniapp-frontend`
- `npm run build` in `apps/admin-panel`

## Что проверяется

Минимальный сквозной сценарий:

1. Старт аренды (`/mobile/trips/start`) -> создаётся PRE inspection.
2. Загрузка 4 обязательных фото + initial checks.
3. Подтверждение набора фото (`/inspections/{id}/confirm-photo-set`).
4. Damage inference + finalize PRE.
5. Переход в активную поездку.
6. Старт возврата (`/mobile/trips/{id}/return`) -> создаётся POST inspection.
7. Загрузка 4 обязательных фото + initial checks.
8. Подтверждение набора фото (`/inspections/{id}/confirm-photo-set`).
9. Damage inference + finalize POST.
10. Сравнение PRE/POST создаёт `admin_case`.
11. Кейсы доступны через `/admin-cases`, `/admin-cases/{id}` и выдерживают смену статуса.
12. После завершения возврата активной аренды нет.
13. Bot flow после завершения PRE переключается на активную поездку, после POST не оставляет конфликтующих кнопок.

## Где реализовано

- Тест: `tests/test_e2e_smoke_flow.py`
- Доп. проверки: `tests/test_bot_message_flow.py`, `tests/test_bot_trip_flow.py`, `tests/test_admin_cases_route.py`
- Тип: in-memory SQLite + mock storage/inference + реальные API роуты FastAPI.

## Запуск

```bash
uv run pytest -q tests/test_e2e_smoke_flow.py
```

Полный регресс:

```bash
uv run pytest -q
```
