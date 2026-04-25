# Repository Guidelines

## Project Structure & Module Organization
This repository is split into `backend/`, `frontend/`, and `ml/`. Backend code lives in `backend/app/`: `api/` for FastAPI routes, `models/` for SQLAlchemy models, `schemas/` for Pydantic schemas, `services/` for forecasting/report/chat logic, and `data_loader/` for CSV seeding. Datasets live in `backend/data/csv` and `backend/data/geo`. Frontend code is in `frontend/src/` with `components/`, `pages/`, `api/`, `store/`, `utils/`, and `styles/`.

## Build, Test, and Development Commands
Use Docker for the full stack:

- `cp .env.example .env && docker compose up --build`: start Postgres, FastAPI, and the built frontend.
- `docker compose down`: stop containers.
- `docker compose down -v`: reset Postgres data and reload the CSV dataset on next start.

Run services locally when debugging:

- `cd backend && pip install -e ".[dev]"`: install backend and test dependencies.
- `cd backend && DATABASE_URL=sqlite+aiosqlite:///./dev.db DATA_DIR=data uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`: run the API locally.
- `cd frontend && npm install && VITE_API_URL=http://localhost:8000 npm run dev`: run the Vite app against the local backend.
- `cd frontend && npm run build`: compile TypeScript and produce a production build.

## Coding Style & Naming Conventions
Follow the existing code style rather than introducing new conventions. Python uses 4-space indentation, snake_case module names, and type hints where practical. Keep API routers thin and move query/business logic into `services/` or `data_loader/`. Frontend TypeScript uses 2-space indentation, single quotes, and no semicolons. Use PascalCase for React components/pages, camelCase for utilities, and `useXStore.ts` for Zustand stores.

## Testing Guidelines
Backend tests use `pytest` and `pytest-asyncio`; place new tests in `backend/tests/` as `test_*.py`. The repository currently has very few committed tests, so new API, loader, and service changes should add coverage. Run `cd backend && python -m pytest tests` before opening a PR. The frontend has no dedicated test runner yet, so at minimum verify `npm run build` and smoke-test affected screens.

## Commit & Pull Request Guidelines
Recent commits use short, simple subjects such as `add fix docker` and `add full project code`. Keep commit messages brief, imperative, and lowercase where possible, for example `fix forecast query` or `add map filter`. PRs should include a short summary, affected areas, linked issues if any, and screenshots for UI changes.

## Security & Configuration Tips
Do not commit secrets. Keep real values in `.env`, commit only `.env.example`, and treat `LLM_API_KEY`, database credentials, and local SQLite/Postgres files as local-only artifacts.
