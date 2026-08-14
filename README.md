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
