FROM node:24.18.0-bookworm-slim@sha256:6f7b03f7c2c8e2e784dcf9295400527b9b1270fd37b7e9a7285cf83b6951452d AS frontend
WORKDIR /build/frontend
COPY App/frontend/package.json App/frontend/package-lock.json ./
RUN npm install --global npm@11.16.0 && npm ci
COPY App/frontend/ ./
ENV VITE_API_BASE_URL=/api
RUN npm run build

FROM python:3.12.3-slim-bookworm@sha256:afc139a0a640942491ec481ad8dda10f2c5b753f5c969393b12480155fe15a63
COPY --from=ghcr.io/astral-sh/uv:0.13.6@sha256:af22a52f5eafef3d78e551599d405c02df61919d18028f0cea8eda93bc9986d0 /uv /usr/local/bin/uv
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PATH="/app/.venv/bin:$PATH" \
    DEPLOYMENT_ACCESS=private
WORKDIR /app
COPY App/pyproject.toml App/uv.lock App/.python-version ./
COPY App/backend/ ./backend/
RUN uv sync --locked --no-dev --no-editable && uv cache clean
COPY App/alembic.ini ./
COPY App/migrations/ ./migrations/
COPY --from=frontend /build/frontend/dist ./frontend/dist/
RUN useradd --create-home --uid 10001 tourney
USER tourney
EXPOSE 10000
CMD ["sh", "-c", "exec uvicorn backend.deployment:create_deployment_app --factory --host 0.0.0.0 --port \"${PORT:-10000}\" --workers 1 --no-proxy-headers"]
