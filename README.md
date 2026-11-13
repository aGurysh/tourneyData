# Kayak Tournament Analytics

This application gives anglers access to deeper insights from kayak fishing tournament results. All tournament data is collected from public TourneyX result pages. This software is not a replacement for TourneyX, or meant to compete with it in any way. The goal is to provide data visualizations and summaries based on the data that is already publicly available.

<img width="1400" height="470" alt="summaryAndBite" src="https://github.com/user-attachments/assets/f9371eb6-cdeb-478d-8518-a0e934af7920" />
<img width="1402" height="543" alt="Screenshot 2026-11-12 191950" src="https://github.com/user-attachments/assets/ca17002d-a52f-4b46-9a43-f89698e15014" />


The app is currently deployed via Render, but is a private preview at this time.

The tech stack includes a React/Vite frontend, a FastAPI/PostgreSQL backend.

See the [engineering guide](docs/engineering.md) for the architecture and key implementation decisions.

## Start locally

Run each block from the repository root. Keep the API and client running in separate terminals.

**Database**

```bash
cd App
docker compose up -d --wait db
```

**API** — http://localhost:8000/docs

```bash
cd App
.venv/bin/uvicorn backend.api.main:app --reload
```

**Client** — http://localhost:5173

```bash
cd App/frontend
npm run dev
```

Vite forwards `/api` to the API on port 8000. Stop the API/client with Ctrl+C;
stop the database with `cd App && docker compose down` (data is retained).

## First-time setup

Requires Docker Compose, Python **3.12.3**, uv **0.13.6**, Node **24.18.0**,
and npm **11.16.0**. Runtime versions are pinned in the app configuration.

```bash
cd App
cp -n .env.example .env
uv sync --locked --extra dev
docker compose up -d --wait db
.venv/bin/alembic upgrade head
```

In another terminal, from the repository root (using nvm):

```bash
cd App/frontend
nvm install
nvm use
npm ci
```

The database starts empty. [Import tournaments](App/backend/ingestion/README.md)
to populate the client. Local configuration lives in `App/.env`; keep it out of Git.

## Reference

- [Backend tests, migrations, and API checks](App/backend/README.md)
- [Frontend checks and configuration](App/frontend/README.md)
- [Ingestion commands](App/backend/ingestion/README.md)
- [Deployment and backups](App/deploy/README.md)
- [Database tables](DB_SCHEMA.md)
