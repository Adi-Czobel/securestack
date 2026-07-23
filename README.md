# SecureStack 🐋

A multi-container REST API built with Docker Compose, designed around network isolation, least-privilege containers, and resource-bounded services.

## Stack

- **nginx** — Reverse proxy, entry point for all traffic
- **Flask** — Python REST API
- **PostgreSQL** — Database
- **Redis** — Cache

## Security Design

- **Network segmentation** — `db` and `cache` sit on an internal-only Docker network (`internal: true`) with no route to the outside world. Only `nginx` and `app` are reachable from the host.
- **Non-root application container** — the Flask app runs as a dedicated unprivileged system user (`appuser`), not root.
- **Read-only filesystems** — `nginx` and `app` run with `read_only: true`; the only writable paths are explicit `tmpfs` mounts scoped to what each service actually needs at runtime (`/tmp` for the app, `/var/cache/nginx` and `/var/run` for nginx).
- **Resource limits** — every service has CPU and memory ceilings set via `deploy.resources.limits`, so no single container can exhaust host resources.
- **Secrets kept out of the image** — credentials are injected via `.env` (gitignored) rather than hardcoded in `docker-compose.yml`; only `.env.example` is committed.
- **Healthchecks on every service** that supports one, so `depends_on: condition: service_healthy` ensures the app doesn't start against a database that isn't ready yet.

## Architecture

    Client → nginx (reverse proxy, read-only, port 80)
                  │
                  ▼
             Flask app (non-root, read-only)
             ┌────┴────┐
             ▼         ▼
         PostgreSQL   Redis
       (internal-only network, unreachable from host or internet)

## How to Run

1. Clone the repo
2. Copy the example env file: `cp .env.example .env`
3. Start the stack: `docker compose up -d --build`
4. Test it: `curl http://localhost/tasks`

## API

| Method | Endpoint | Description   |
| ------ | -------- | ------------- |
| GET    | /tasks   | Get all tasks |
| POST   | /tasks   | Create a task |
| GET    | /health  | Health check  |
