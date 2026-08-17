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
python -c "import json; print(json.dumps({'test': '<hash>'}))"
```

Put the JSON object in `AUTH_USERS` and the secret in `JWT_SECRET`. Set `LLM_API_KEY` for generation.

PDF originals are stored in S3. Configure `AWS_ACCESS_KEY_ID`,
`AWS_SECRET_ACCESS_KEY`, `AWS_REGION`, and `S3_BUCKET` in `.env`.

## S3 CORS for the PDF viewer

The document viewer follows an authenticated API redirect to a short-lived
presigned S3 URL. Apply this CORS configuration to the bucket:

```json
[
  {
    "AllowedOrigins": ["http://localhost:5173"],
    "AllowedMethods": ["GET"],
    "AllowedHeaders": ["Range"],
    "ExposeHeaders": ["Content-Range", "Content-Length", "Accept-Ranges"]
  }
]
```

Without this configuration, pdf.js range requests can fail silently in the
browser. Add production frontend origins to `AllowedOrigins` when deploying.

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

## Railway deployment

Create a Railway service from this repository, set its root directory to
`/backend`, and deploy with the backend `Dockerfile`. Attach a managed PostgreSQL
service and reference its internal `DATABASE_URL`. Railway supplies a plain
`postgresql://` URL; the app converts it to asyncpg while Alembic converts the
same value to psycopg for synchronous migrations.

The container runs `alembic upgrade head` before starting uvicorn, listens on
Railway's `PORT` at `0.0.0.0`, and starts exactly one process. Keep the Railway
service at one replica because active response streams are stored in process
memory.

Configure these Railway variables:

```dotenv
DATABASE_URL=${{Postgres.DATABASE_URL}}
JWT_SECRET=<random token-safe secret>
AUTH_USERS={"admin":"<bcrypt password hash>"}
OPENAI_API_KEY=<OpenAI API key>
GEMINI_API_KEY=<Gemini API key>
EXA_API_KEY=<Exa API key>
AWS_ACCESS_KEY_ID=<AWS access key>
AWS_SECRET_ACCESS_KEY=<AWS secret key>
AWS_REGION=<S3 bucket region>
S3_BUCKET=<S3 bucket name>
CORS_ORIGINS=["https://your-app.vercel.app"]
LOG_LEVEL=INFO
```

`LLM_API_KEY` remains supported as an alternative to `OPENAI_API_KEY`. Optional
observability variables are `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, and
`LANGFUSE_HOST`.

Set Railway's health-check path to `/health`. It returns
`{"status":"ok"}` without querying PostgreSQL, S3, or model providers. Add the
same Vercel origin to the S3 CORS policy above so browser PDF range requests are
allowed.

## Test / lint

```bash
pytest
ruff check .
mypy
```
