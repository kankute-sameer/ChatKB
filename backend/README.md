# ChatKB backend

FastAPI app with env-based auth and resumable conversation streaming.

## Conda env

```bash
conda env create -f environment.yml   # or: conda create -n chatkb python=3.12 -y
conda activate chatkb
```

## Setup

```bash
conda activate chatkb
cd backend
uv pip install -e ".[dev]" --python "$CONDA_PREFIX/bin/python"
cp .env.example .env
```

`--python "$CONDA_PREFIX/bin/python"` installs into the conda env instead of a nested `.venv`.

Generate a JWT secret and password hashes, then edit `.env`:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
python -c "from passlib.context import CryptContext; print(CryptContext(schemes=['bcrypt']).hash('yourpassword'))"
python -c "import json; print(json.dumps({'alice': '<hash>', 'bob': '<hash>'}))"
```

Put the JSON object in `AUTH_USERS` and the secret in `JWT_SECRET`. Set `LLM_API_KEY` for generation.

## Database

Start Postgres from the repo root:

```bash
docker compose up -d
```

`DATABASE_URL` should match the compose service (already the app default):

```bash
DATABASE_URL=postgresql+asyncpg://chatkb:chatkb@127.0.0.1:5433/chatkb
```

Apply migrations (from `backend/`):

```bash
alembic upgrade head
```

## Run

From `backend/`:

```bash
uvicorn app.main:create_app --factory --reload
```

- `GET /health` — public
- `POST /auth/login` — `{"username": "...", "password": "..."}` → bearer token
- `GET /auth/me` — `Authorization: Bearer <token>`
- `POST /v1/conversations` — create a conversation
- `POST /v1/responses` — stream an assistant reply (UI message protocol)
- `GET /v1/conversations/{id}/stream` — resume an in-flight stream

## Test / lint

```bash
pytest
ruff check .
mypy
```
