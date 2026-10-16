# SecureStack 🐋

A small REST API running across four Docker containers, built to practise locking down a
deployment rather than to be a big application. The app itself is a simple task list. The
interesting part is how the containers are isolated from each other.

## Stack

- **nginx** - reverse proxy, the only container the outside world can reach
- **Flask** - Python REST API
- **PostgreSQL** - database
- **Redis** - cache

## Security design

- **The database and cache are on a private network.** Docker lets you mark a network
  `internal: true`, which cuts off all routing in and out of it. `db` and `cache` sit on
  that network, so nothing outside the stack can reach them.
- **nginx cannot reach the database either.** nginx is only on the `frontend` network. The
  Flask app sits on both networks and acts as the bridge. So even if someone fully
  compromised nginx, which is the container facing the internet, there is still no path
  from there to Postgres or Redis.
- **Only one port is published.** nginx maps `80:80`. The other three publish nothing, so
  they are not reachable from the host at all.
- **The app does not run as root.** `app/Dockerfile` creates a system user called `appuser`
  and switches to it.
- **Filesystems are read-only.** nginx and the app both run with `read_only: true`. The only
  writable paths are small `tmpfs` mounts for the few directories each one actually needs
  (`/tmp` for the app, `/var/cache/nginx` and `/var/run` for nginx). Anything written there
  disappears on restart, so a dropped webshell does not survive.
- **Every container has CPU and memory limits**, so one of them cannot starve the others.
- **Passwords come from `.env`**, which is gitignored. Only `.env.example` with placeholder
  values is committed.
- **Healthchecks control startup order.** Postgres and Redis define healthchecks in Compose
  and the app defines one in its Dockerfile. `depends_on: condition: service_healthy` means
  the app never starts against a database that is not ready yet.

## What this protects against

The setup assumes an attacker who can reach nginx over the network and has no access to the
host machine.

| Threat | What stops it |
| ------ | ------------- |
| Attacking Postgres or Redis directly | They are on an internal network and publish no ports |
| Breaking into nginx, then moving to the database | nginx has no route to the backend network |
| Escaping the container to get root on the host | The app runs as a normal user, not root |
| Leaving a backdoor behind after a break-in | Read-only filesystems, and tmpfs is wiped on restart |
| One container eating all the CPU or memory | Per-container limits |
| Database password ending up on GitHub | `.env` is gitignored, only the example file is committed |
| Requests hitting a database that has not started | Healthchecks and startup ordering |

## What it does not cover

- **TLS.** The stack serves plain HTTP and expects something in front of it to handle HTTPS.
  Do not put this straight on the internet as it is.
- **Logins.** The API has no authentication. This project is about hardening the deployment,
  not the application.
- **The host machine.** Kernel updates, Docker daemon config, and OS patching are assumed to
  be handled elsewhere.
- **Where the images come from.** Base images are pulled and trusted as-is. No signature or
  SBOM checking.
- **Secrets on disk.** `.env` is a plain text file. A real deployment would use Docker
  secrets or something like Vault.

## Architecture

    Client → nginx (read-only, port 80)          [frontend network]
                  │
                  ▼
             Flask app (runs as appuser, read-only)   [frontend + backend]
             ┌────┴────┐
             ▼         ▼
         PostgreSQL   Redis                      [backend network, internal only]

## How to run it

```bash
git clone https://github.com/Adi-Czobel/securestack.git
cd securestack
cp .env.example .env     # change the password in it
docker compose up -d --build
curl http://localhost/tasks
```

Needs Docker Engine 20.10 or newer with Compose V2.

## Checking that it actually works

You can verify each control yourself instead of taking my word for it.

```bash
# nginx cannot reach the database
docker compose exec nginx sh -c "nc -z -w2 db 5432 || echo 'blocked, as expected'"

# the app is not running as root
docker compose exec app id                      # uid should not be 0

# the filesystem is read-only
docker compose exec app sh -c "touch /nope"     # should say: Read-only file system

# but the tmpfs mount still works
docker compose exec app sh -c "touch /tmp/ok && echo 'tmpfs is writable, as expected'"

# limits are applied
docker stats --no-stream

# only nginx is published
docker compose ps
```

## API

| Method | Endpoint | Description |
| ------ | -------- | ----------- |
| GET | /tasks | Get all tasks (cached in Redis for 60s) |
| POST | /tasks | Create a task (clears the cache) |
| GET | /health | Health check |
