# Population Analytics

Веб-приложение для анализа демографической динамики муниципалитетов России. Проект показывает население, рождаемость, смертность, миграцию, рейтинги изменений, карту регионов, простые прогнозы и отчеты.

## Стек

- Backend: FastAPI, SQLAlchemy Async, PostgreSQL или SQLite, Pydantic.
- Frontend: React, Vite, TypeScript, Ant Design, ECharts, Leaflet.
- Data: CSV с муниципальной демографией и GeoJSON для карты.
- Optional AI: LLM-интеграция для чата и отчетов через OpenAI/OpenRouter-совместимый API.

## Структура

```text
backend/
  app/
    api/          # REST API
    data_loader/  # загрузка CSV и демо-данных
    models/       # SQLAlchemy модели
    schemas/      # Pydantic схемы
    services/     # прогнозы, отчеты, LLM
  data/
    csv/          # исходный CSV с демографией
    geo/          # GeoJSON для карты
frontend/
  src/            # React-приложение
ml/               # заготовка под ML-модель
docker-compose.yml
```

## Данные

При старте backend создает таблицы и автоматически загружает файл из `backend/data/csv/*demography*.csv`.

Текущий датасет содержит:

- 80 регионов;
- 2 286 муниципалитетов;
- данные по годам 2000-2023;
- население, рождения, смерти, миграцию и рассчитанные коэффициенты.

Если база уже содержит старые демо-данные или частичную загрузку, backend заменит их реальным CSV. Если CSV не найден, включится fallback на демо-данные.

## Быстрый Запуск Через Docker

Нужны Docker и Docker Compose.

```bash
cp .env.example .env
docker compose up --build
```

После запуска:

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- Swagger: http://localhost:8000/docs

Остановить:

```bash
docker compose down
```

Полностью сбросить PostgreSQL-данные и загрузить CSV заново:

```bash
docker compose down -v
docker compose up --build
```

## Локальный Запуск Без Docker

### Backend На SQLite

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

DATABASE_URL=sqlite+aiosqlite:///./dev.db DATA_DIR=data uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Swagger будет доступен на http://localhost:8000/docs.

### Frontend

В отдельном терминале:

```bash
cd frontend
npm install
VITE_API_URL=http://localhost:8000 npm run dev
```

Frontend будет доступен на http://localhost:5173.

## Настройки Окружения

Скопируйте `.env.example` в `.env` и поменяйте значения под себя.

Основные переменные:

- `DB_PASSWORD` - пароль PostgreSQL в Docker.
- `DATABASE_URL` - строка подключения backend к базе.
- `DATA_DIR` - путь к папке с `csv/` и `geo/`.
- `LLM_PROVIDER` - провайдер LLM, например `openai` или `openrouter`.
- `LLM_API_KEY` - ключ LLM API. Не коммитить.
- `LLM_MODEL` - модель для чата и отчетов.
- `LLM_BASE_URL` - base URL для OpenAI-compatible API.
- `VITE_API_URL` - адрес backend при локальном запуске frontend через Vite.

Файл `.env` игнорируется git. В репозиторий должен попадать только `.env.example`.

## Проверки

Backend:

```bash
cd backend
source .venv/bin/activate
python -m pytest tests
```

Frontend:

```bash
cd frontend
npm run build
```

## Git Hygiene

В `.gitignore` добавлены локальные и генерируемые файлы:

- `.env`, `.env.*`, кроме `.env.example`;
- Python virtualenv, кеши, `*.egg-info`;
- `node_modules`, `dist`, `*.tsbuildinfo`;
- локальные SQLite-БД: `*.db`, `*.sqlite`, `*.sqlite3`;
- IDE/OS-файлы и локальные настройки инструментов.

Данные в `backend/data` не игнорируются, потому что без них проект не загрузит реальный датасет при первом запуске.
