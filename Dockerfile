# Multi-stage: build React UI, then serve it from FastAPI + SQLite.
FROM node:22-bookworm-slim AS frontend-build
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
# Same-origin API when the UI is served by the backend.
ENV VITE_API_BASE=
RUN npm run build

FROM python:3.12-slim-bookworm AS runtime
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    SERVE_FRONTEND=1 \
    STATIC_DIR=/app/static \
    PORT=8000

COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

COPY backend/ /app/backend/
COPY --from=frontend-build /frontend/dist /app/static

WORKDIR /app/backend
EXPOSE 8000

# Render and similar hosts inject $PORT; local default is 8000.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
