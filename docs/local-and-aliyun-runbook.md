# Local And Aliyun Runbook

## Local development

### Backend

Required services:

- PostgreSQL
- Redis

Required runtime:

- Java 21
- Maven 3.9+

Environment variables can be exported directly or loaded from a shell file.

Start backend:

```bash
source scripts/use-local-toolchain.sh
cd apps/api
mvn spring-boot:run
```

### Frontend

```bash
source scripts/use-local-toolchain.sh
cd apps/web
cp .env.example .env
npm install
npm run dev
```

Default frontend port:

- `5173`

Default backend port:

- `8092`

## Aliyun deployment suggestion

### Backend

Recommended target:

- `Alibaba Cloud ECS`
- Java 21 runtime
- External PostgreSQL and Redis, or self-hosted instances

Recommended process:

1. Provision Java 21 and Maven, or build jar in CI
2. Prepare environment variables from `.env.docker.example`
3. Run Flyway automatically at startup
4. Start the jar behind `systemd` or `supervisor`
5. Put Nginx in front for TLS and reverse proxy

Example:

```bash
source scripts/use-local-toolchain.sh
cd apps/api
mvn -DskipTests package
$JAVA_HOME/bin/java -jar target/control-plane-0.0.1-SNAPSHOT.jar
```

### Frontend

Recommended target:

- Static deployment via `Nginx`

Build:

```bash
source scripts/use-local-toolchain.sh
cd apps/web
npm install
npm run build
```

Deploy the generated `dist/` directory to Nginx.

## Environment notes

- `AIMUSIC_CORS_ALLOWED_ORIGINS` should include the frontend domain
- `SPRING_PROFILES_ACTIVE=postgres` is the default production profile
- `AIMUSIC_DB_MIGRATION_ENABLED=true` should stay enabled in controlled environments
