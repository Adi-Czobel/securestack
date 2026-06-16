# SecureStack 🐋

A multi-container REST API built with Docker Compose.

## Stack

- **nginx** — Reverse proxy
- **Flask** — Python REST API
- **PostgreSQL** — Database
- **Redis** — Cache

## Architecture
## How to Run

1. Clone the repo
2. Copy the example env file: `cp .env.example .env`
3. Start the stack: `docker compose up -d --build`
4. Test it: `curl http://localhost/tasks`

## API

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /tasks | Get all tasks |
| POST | /tasks | Create a task |
| GET | /health | Health check |