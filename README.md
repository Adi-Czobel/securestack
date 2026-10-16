# SecureStack 🐋

A multi-container REST API built with Docker Compose, designed around network isolation, least-privilege containers, and resource-bounded services.

## Stack

- **nginx** — Reverse proxy, entry point for all traffic
- **Flask** — Python REST API
- **PostgreSQL** — Database
- **Redis** — Cache

## Security Design

- **Network segmentation** — `db` and `cache` sit on an internal-only Docker network (`internal: true`) with no route to the outside world. `nginx` is on the `frontend` network only; `app` bridges `frontend` and `backend`. nginx therefore cannot reach the database at all, even though it is the internet-facing service.
- **Only one published port** — `nginx` maps `80:80`. `app`, `db`, and `cache` publish nothing and are unreachable from the host.
- **Non-root application container** — the Flask app runs as a dedicated unprivileged system user (`appuser`), not root.
- **Read-only filesystems** — `nginx` and `app` run with `read_only: true`; the only writable paths are explicit `tmpfs` mounts scoped to what each service actually needs at runtime (`/tmp` for the app, `/var/cache/nginx` and `/var/run` for nginx).
- **Resource limits** — every service has CPU and memory ceilings set via `deploy.resources.limits`, so no single container can exhaust host resources.
- **Secrets kept out of the image** — credentials are injected via `.env` (gitignored) rather than hardcoded in `docker-compose.yml`; only `.env.example` is committed.
- **Healthchecks gate startup order** — `db` and `cache` define healthchecks in Compose, `app` defines one in its Dockerfile. `depends_on: condition: service_healthy` means the app never starts against a database that isn't ready, and nginx never starts against a dead app.

## Threat model

Scoped to a single-host Docker Compose deployment serving an HTTP API to untrusted clients.
The assumed attacker reaches nginx over the network with no prior foothold on the host.

| # | Threat | Control |
|---|---|---|
| 1 | Direct attack on the database | `backend` is `internal: true` and publishes no ports. Unreachable from host or internet. |
| 2 | Pivot from the internet-facing service to the data tier | nginx is not attached to `backend`. A full nginx compromise still yields no route to Postgres or Redis. |
| 3 | Container escape to host root | Application containers run as a non-root user (`appuser`). |
| 4 | Persistence after compromise | Read-only root filesystems; writable paths are explicit `tmpfs` and vanish on restart, so a dropped webshell does not survive. |
| 5 | Resource exhaustion by one service | Per-service CPU and memory limits on all four containers. |
| 6 | Credentials committed to source | `.env` is gitignored; only placeholder values ship in `.env.example`. |
| 7 | Traffic served by an unready backend | Healthchecks plus `depends_on: service_healthy` ordering. |

### Out of scope

- **TLS termination.** This stack serves plain HTTP and assumes TLS terminates upstream at a
  load balancer. Exposing it directly to the internet as-is would be wrong.
- **Authentication and authorisation.** The API is deliberately unauthenticated; this repo
  demonstrates deployment hardening, not application-layer access control.
- **Host hardening.** Kernel, Docker daemon config, and OS patching are assumed handled.
- **Image provenance.** Base images are trusted as pulled; no signing or SBOM verification.
- **Secrets at rest.** `.env` is plaintext on disk. A real deployment would use Docker
  secrets, Vault, or a cloud secrets manager.

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

```bash
git clone https://github.com/Adi-Czobel/securestack.git
cd securestack
cp .env.example .env     # then change the password
docker compose up -d --build
curl http://localhost/tasks
```

Requires Docker Engine 20.10+ with Compose V2.

## Verifying the controls

Don't take this README's word for it. Each command proves one control is actually on.

```bash
# 1. nginx cannot reach the database — no route from frontend to backend
docker compose exec nginx sh -c "nc -z -w2 db 5432 || echo 'BLOCKED (expected)'"

# 2. The app container is not running as root
docker compose exec app id                      # expect uid != 0, user appuser

# 3. The app root filesystem is read-only
docker compose exec app sh -c "touch /nope"     # expect: Read-only file system

# 4. ...but the tmpfs mount is writable
docker compose exec app sh -c "touch /tmp/ok && echo 'tmpfs writable (expected)'"

# 5. Resource ceilings are applied
docker stats --no-stream

# 6. Only nginx is published to the host
docker compose ps
```

## API

| Method | Endpoint | Description   |
| ------ | -------- | ------------- |
| GET    | /tasks   | Get all tasks |
| POST   | /tasks   | Create a task |
| GET    | /health  | Health check  |
