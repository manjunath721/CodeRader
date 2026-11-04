# CodeRadar — DevOps & Production Deployment Guide

This guide details containerization, Docker Compose configuration, healthcheck orchestration, and continuous integration workflows for CodeRadar.

---

## 1. Docker Compose Production Architecture

CodeRadar defines three services orchestrated via Docker Compose:

1. **`postgres`**: PostgreSQL 16 Alpine
   - Storage: Persistent Docker named volume `postgres_data`
   - Healthcheck: `pg_isready -U coderesilience -d coderesilience` (interval: 5s, retries: 10)
2. **`backend`**: FastAPI application (Python 3.11)
   - Entrypoint: `docker-entrypoint.sh` executes `alembic upgrade head` on startup before launching Uvicorn
   - Healthcheck: Python probe invoking `http://localhost:8000/api/health/ready`
   - Workers: Multi-worker process model when `ENVIRONMENT=production`
3. **`frontend`**: React 18 / Vite SPA
   - Reverse proxy targeting `http://backend:8000`
   - Healthcheck dependency waiting for backend health

```yaml
name: coderadar

services:
  postgres:
    image: postgres:16-alpine
    restart: unless-stopped
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-coderesilience}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-coderesilience}
      POSTGRES_DB: ${POSTGRES_DB:-coderesilience}
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-coderesilience} -d ${POSTGRES_DB:-coderesilience}"]
      interval: 5s
      timeout: 5s
      retries: 10

  backend:
    image: coderadar-backend
    build:
      context: ./backend
      dockerfile: Dockerfile
    restart: unless-stopped
    env_file:
      - .env
    environment:
      DATABASE_URL: postgresql+psycopg2://${POSTGRES_USER:-coderesilience}:${POSTGRES_PASSWORD:-coderesilience}@postgres:5432/${POSTGRES_DB:-coderesilience}
    ports:
      - "8000:8000"
    depends_on:
      postgres:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health/ready')"]
      interval: 10s
      timeout: 5s
      retries: 5

  frontend:
    image: coderadar-frontend
    build:
      context: ./frontend
      dockerfile: Dockerfile
    restart: unless-stopped
    environment:
      - VITE_PROXY_TARGET=http://backend:8000
    ports:
      - "5173:5173"
    depends_on:
      backend:
        condition: service_healthy

volumes:
  postgres_data:
```

---

## 2. CI/CD Pipeline (GitHub Actions)

The workflow `.github/workflows/ci.yml` triggers on all pushes and pull requests to `main` and `master`:

- **Job 1: Backend Checks**:
  - Python 3.11 environment setup
  - Offline Alembic DDL validation (`alembic upgrade head --sql`)
  - Full pytest execution with strict assertion checking (`pytest tests -v`)
- **Job 2: Frontend Checks**:
  - Node.js 20 environment setup
  - ESLint static analysis (`npm run lint`)
  - Vitest unit tests (`npm test -- --run`)
  - Production build bundle generation (`npm run build`)
- **Job 3: Compose Validation**:
  - Docker Compose syntax and schema validation (`docker compose config`)

---

## 3. Operational Health Checks

The backend provides three dedicated endpoints for orchestrators:

- `GET /api/health`: Basic service status
- `GET /api/health/live`: Liveness probe indicating process responsive
- `GET /api/health/ready`: Readiness probe executing `SELECT 1` on PostgreSQL to confirm active database connection pool availability
