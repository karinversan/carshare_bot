# E2E Smoke (API + Core Product Flow)

Дата: 2026-03-20

## Что проверяется

Минимальный сквозной сценарий:

1. Старт аренды (`/mobile/trips/start`) -> создаётся PRE inspection.
2. Загрузка 4 обязательных фото + initial checks.
3. Damage inference + finalize PRE.
4. Переход в активную поездку.
5. Старт возврата (`/mobile/trips/{id}/return`) -> создаётся POST inspection.
6. Загрузка 4 обязательных фото + initial checks.
7. Damage inference + finalize POST.
8. Сравнение PRE/POST создаёт `admin_case`.
9. Кейсы доступны через `/admin-cases` и `/admin-cases/{id}`.
10. После завершения возврата активной аренды нет.

## Где реализовано

- Тест: `tests/test_e2e_smoke_flow.py`
- Тип: in-memory SQLite + mock storage/inference + реальные API роуты FastAPI.

## Запуск

```bash
uv run pytest -q tests/test_e2e_smoke_flow.py
```

Полный регресс:

```bash
uv run pytest -q
```

