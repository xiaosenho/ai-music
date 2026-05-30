# AI Music Control Plane

This repository contains the control-plane backend and web console for the AI music workflow platform.

## Current scope

- Spring Boot backend
- Flyway database migrations
- PostgreSQL + Redis via Docker Compose
- AutoDL worker control APIs
- AutoDL execution worker
- React + Vite web console

## Quick start

### Backend with Docker Compose

1. Copy `.env.docker.example` to `.env.docker`
2. Fill in the real secrets
3. Run:

```bash
DOCKER_BUILDKIT=1 docker compose --env-file .env.docker up --build
```

The backend listens on `SERVER_PORT`.

If you are deploying in mainland China, keep `MAVEN_MIRROR_URL=https://maven.aliyun.com/repository/public` in `.env.docker` so the backend image builds faster.

### Backend without Docker

Requirements:

- Java 21
- Maven 3.9+
- PostgreSQL
- Redis

Run:

```bash
source scripts/use-local-toolchain.sh
cd apps/api
mvn spring-boot:run
```

The backend reads configuration from environment variables in `application.yml`.

### Web console

1. Copy `apps/web/.env.example` to `apps/web/.env`
2. Adjust `VITE_API_BASE_URL`
3. Run:

```bash
source scripts/use-local-toolchain.sh
cd apps/web
npm install
npm run dev
```

## Current APIs

- `POST /api/v1/workers/register`
- `POST /api/v1/workers/heartbeat`
- `GET /api/v1/workers`
- `POST /api/v1/workers/{nodeId}/drain`
- `POST /api/v1/workers/{nodeId}/activate`
- `POST /api/v1/jobs`
- `POST /api/v1/jobs/pull`
- `POST /api/v1/jobs/{jobId}/report`
- `GET /api/v1/jobs`
- `GET /api/v1/jobs/{jobId}`
- `GET /api/v1/jobs/{jobId}/events`
- `GET /api/v1/dashboard/summary`

## AutoDL worker

The execution-plane worker lives in `apps/autodl-worker/worker.py`.

Quick start:

```bash
cd apps/autodl-worker
cp .env.example .env
set -a
source .env
set +a
python3 worker.py
```

See `apps/autodl-worker/README.md` for the command contract and real pipeline integration.

## Notes

- Database schema is managed by `Flyway`
- `process` and `train` jobs are cloud-only
- `infer` jobs support `CLOUD`, `LOCAL`, and `AUTO` execution modes
- Frontend CORS origins are controlled by `AIMUSIC_CORS_ALLOWED_ORIGINS`

## Suggested next steps

- Add authentication and JWT issuance
- Add character / dataset / model domain tables
- Add worker lease recovery and offline detection scheduler
- Add AutoDL worker deployment and watchdog scripts

## Deployment docs

- [Aliyun simple deployment](./docs/aliyun-simple-deployment.md)
- [Local and Aliyun runbook](./docs/local-and-aliyun-runbook.md)
- [AutoDL worker deployment](./docs/autodl-worker-deployment.md)
