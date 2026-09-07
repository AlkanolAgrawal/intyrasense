# 🚀 Deployment Guide

> Instructions for deploying INTYRASENSE with Docker and in production environments.

---

## Docker Deployment

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) installed
- [Docker Compose](https://docs.docker.com/compose/install/) (v2+)
- A valid Groq API key
- A Supabase project with `documents` and `chunks` tables configured

### Quick Start

```bash
# 1. Configure environment
cp .env.example .env
# Edit .env and add your GROQ_API_KEY, SUPABASE_URL, and SUPABASE_KEY

# 2. Build and start services
docker compose -f Docker/docker-compose.yml up --build
```

This starts four containers:

| Service | Container Name | Port | Description |
|---------|----------------|------|-------------|
| `redis` | `intyrasense-redis` | 6379 | Redis 7 Alpine — Celery broker, result backend, status store |
| `celery_worker` | `intyrasense-celery-worker` | — | Background task processor (document ingestion) |
| `backend` | `intyrasense-backend` | 8000 | FastAPI API server |
| `frontend` | `intyrasense-frontend` | 8501 | Streamlit web UI |

### Stop Services

```bash
docker compose -f Docker/docker-compose.yml down
```

### Rebuild After Code Changes

```bash
docker compose -f Docker/docker-compose.yml up --build
```

---

## Docker Architecture

```text
docker-compose.yml
├── redis (redis:7-alpine)
│   ├── Healthcheck: redis-cli ping
│   └── Port 6379
├── celery_worker (Dockerfile.backend)
│   ├── command: celery -A backend.celery_app.celery worker --loglevel=info
│   ├── Redis URL overridden to redis://redis:6379/0
│   └── Depends on: redis (healthy)
├── backend (Dockerfile.backend)
│   ├── Python 3.11 + Tesseract OCR + Poppler
│   ├── Redis URL overridden to redis://redis:6379/0
│   ├── Depends on: redis (healthy)
│   └── Port 8000
└── frontend (Dockerfile.frontend)
    ├── Python 3.11 slim + Streamlit
    ├── BACKEND_URL=http://backend:8000
    ├── Depends on: backend
    └── Port 8501
```

**Networking:**

- All services share the `intyrasense-network` bridge network
- Backend and frontend share `.env` file via `env_file: ../.env`
- Redis URLs are overridden in `environment:` to use container-internal DNS (`redis://redis:6379/0`)
- Frontend `BACKEND_URL` defaults to `http://backend:8000` for container networking

---

## Production Considerations

### Security

- **Never commit `.env` files** — Use Docker secrets or environment variable injection
- **Restrict CORS** — The current configuration uses `allow_origins=["*"]`. For production, restrict to your domain:

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://yourdomain.com"],
    allow_methods=["*"],
    allow_headers=["*"],
)
```

- **Rate limit the API** — Consider adding rate limiting middleware
- **Use HTTPS** — Place behind a reverse proxy (Nginx, Caddy, Traefik)
- **Add authentication** — Current API has no authentication; all endpoints are publicly accessible

### Reverse Proxy (Nginx Example)

```nginx
server {
    listen 443 ssl;
    server_name intyrasense.example.com;

    ssl_certificate     /etc/ssl/certs/cert.pem;
    ssl_certificate_key /etc/ssl/private/key.pem;

    # Backend API
    location /api/ {
        proxy_pass http://localhost:8000/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # Frontend
    location / {
        proxy_pass http://localhost:8501/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

### Performance

- **Embedding model**: Loaded once at startup, shared across all requests (singleton pattern via `@lru_cache`)
- **Query embedding cache**: `@lru_cache(maxsize=256)` on query embeddings avoids re-computation
- **Vector search**: Supabase pgvector cosine similarity search with indexed embeddings
- **Groq API**: No local GPU needed — inference happens on Groq's infrastructure
- **Celery workers**: Scale ingestion by running multiple workers:

```bash
# Docker: scale worker instances
docker compose -f Docker/docker-compose.yml up --scale celery_worker=3

# Local: multiple worker processes (Linux/macOS)
celery -A backend.celery_app.celery worker --loglevel=info --concurrency=4
```

- **Backend workers**: For high traffic, run multiple uvicorn workers:

```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### Data Persistence

- **Supabase**: All documents, chunks, and embeddings are persisted in managed PostgreSQL
- **Supabase Storage**: Uploaded files are stored in the `documents` bucket
- **Redis**: Used only for ephemeral data (task state, ingestion status) — all keys expire after 24 hours
- **Backups**: Enable automatic backups via Supabase dashboard
- No local data directories need to be manually persisted

### Monitoring

The backend includes a health check endpoint:

```
GET /      → { "status": "running" }
HEAD /     → 200 OK
```

For deeper health checks, consider adding Supabase and Redis connectivity verification.

---

## Cloud Deployment Options

| Platform | Method | Notes |
|----------|--------|-------|
| **Render** | Docker or native Python | Current production backend host |
| **Railway** | Connect GitHub repo, set env vars | Simplest deployment |
| **AWS ECS** | Push Docker images to ECR | Production-grade, scalable |
| **GCP Cloud Run** | Container-based | Auto-scaling, pay-per-use |
| **DigitalOcean App Platform** | Docker support | Simple and affordable |
| **VPS (any provider)** | Docker Compose directly | Full control |

### Generic Cloud Steps

1. Push Docker images to a container registry
2. Set environment variables: `GROQ_API_KEY`, `SUPABASE_URL`, `SUPABASE_KEY`
3. Configure Redis URL (Upstash recommended for cloud — `rediss://` URLs auto-configure TLS)
4. Expose ports 8000 (backend) and 8501 (frontend)
5. Configure DNS and TLS termination

### Using Upstash Redis (Cloud)

For production, use [Upstash](https://upstash.com) as a managed Redis service:

1. Create an Upstash Redis database
2. Copy the `rediss://` connection URL
3. Set in `.env`:

```env
REDIS_URL=rediss://default:YOUR_PASSWORD@YOUR_ENDPOINT.upstash.io:6379
```

TLS is automatically configured in `celery_app.py` when the URL starts with `rediss://`.
