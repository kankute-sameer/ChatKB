# ChatKB

```
frontend/   Vite + React UI
backend/    FastAPI
```

## Backend

```bash
conda activate chatkb
cd backend
uvicorn app.main:create_app --factory --reload
```

Run this from `backend/` so `.env` loads. See `backend/README.md`.

## Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 — unauthenticated visits redirect to `/login`.
Default local users: `alice` / `bob`, password `changeme`.

## Docker deployment

The Compose stack runs four services:

- `frontend`: production Vite assets served by Nginx on `APP_PORT`
- `backend`: FastAPI, available to the browser through `/api`
- `migrate`: a one-shot Alembic migration before the API starts
- `postgres`: PostgreSQL 16 with pgvector and persistent storage

Create the deployment environment file:

```bash
cp .env.docker.example .env.docker
openssl rand -hex 32
```

Put the generated value in `POSTGRES_PASSWORD`, generate another value for
`JWT_SECRET`, and replace every `replace-me` value. Generate each login password
hash from the backend environment:

```bash
cd backend
python -c "from passlib.context import CryptContext; print(CryptContext(schemes=['bcrypt']).hash('your-password'))"
```

Keep `AUTH_USERS` single-quoted in `.env.docker`, for example:

```dotenv
AUTH_USERS='{"admin":"$2b$12$replace_with_the_generated_hash"}'
```

If the `chatkb_chatkb_postgres` volume already exists from the previous
Postgres-only Compose setup, changing `POSTGRES_PASSWORD` does not update the
password stored in that database. Rotate it before starting the full stack:

```bash
docker compose --env-file .env.docker up -d postgres
docker compose --env-file .env.docker exec postgres psql -U chatkb -d chatkb
# At the psql prompt, run \password chatkb and enter POSTGRES_PASSWORD.
```

Build and start the application from the repository root:

```bash
docker compose --env-file .env.docker up --build -d
docker compose --env-file .env.docker ps
set -a; . ./.env.docker; set +a
curl --fail http://localhost:${APP_PORT:-80}/healthz
curl --fail http://localhost:${APP_PORT:-80}/api/health
```

Open `http://localhost:${APP_PORT:-80}`. API documentation is available at
`/api/docs`.

For a public deployment, put a TLS-terminating reverse proxy or load balancer in
front of `APP_PORT`. The API and UI share one origin, so PostgreSQL and the API
are not exposed directly. Also add the public HTTPS origin to the S3 bucket CORS
configuration described in `backend/README.md`.

Run one backend replica. Active response streams are buffered in process memory,
so multiple replicas require sticky sessions or a shared stream store. The
`/api/health` check confirms that the API process is running, but does not probe
S3 or external model providers.

Useful operations:

```bash
# Follow application logs
docker compose --env-file .env.docker logs -f frontend backend migrate

# Rebuild after pulling a new release
docker compose --env-file .env.docker up --build -d

# Stop containers without deleting database or model-cache volumes
docker compose --env-file .env.docker down
```

Back up the `chatkb_chatkb_postgres` volume before upgrades. Do not use
`docker compose down -v` in production unless you intend to delete the database.
