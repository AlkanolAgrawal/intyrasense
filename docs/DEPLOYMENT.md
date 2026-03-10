# 🚀 Deployment Guide

> Instructions for deploying INTYRASENSE with Docker and in production environments.

---

## Docker Deployment

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) installed
- [Docker Compose](https://docs.docker.com/compose/install/) (v2+)
- A valid Groq API key

### Quick Start

```bash
# 1. Configure environment
cp .env.example .env
# Edit .env and add your GROQ_API_KEY

# 2. Build and start services
docker compose -f Docker/docker-compose.yml up --build
```

This starts two containers:

| Service | Port | Description |
|---------|------|-------------|
| `backend` | 8000 | FastAPI API server |
| `frontend` | 8501 | Streamlit web UI |

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
├── backend (Dockerfile.backend)
│   ├── Python 3.11 slim
│   ├── Tesseract OCR + Poppler (system deps)
│   ├── Backend Python packages
│   └── Exposed on port 8000
└── frontend (Dockerfile.frontend)
    ├── Python 3.11 slim
    ├── Streamlit + requests
    ├── BACKEND_URL=http://backend:8000
    └── Exposed on port 8501
```

**Shared volumes:**

- `../data:/app/data` — Document storage and FAISS index persists across container restarts

**Environment:**

- Backend reads `.env` from the project root via `env_file`
- Frontend receives `BACKEND_URL` as an environment variable pointing to the backend container

---

## Production Considerations

### Security

- **Never commit `.env` files** — Use Docker secrets or environment variable injection
- **Restrict CORS** — Add CORS middleware to FastAPI if exposing the API externally:

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

- **Embedding model**: Loaded once at startup, shared across all requests
- **FAISS index**: Kept in memory for fast retrieval
- **Groq API**: No local GPU needed — inference happens on Groq's infrastructure
- For high traffic, consider running multiple backend workers:

```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### Data Persistence

Ensure the `data/` directory is persisted:

- **Docker**: Already mounted as a volume in `docker-compose.yml`
- **Cloud**: Mount a persistent volume (e.g., AWS EBS, GCP Persistent Disk)

### Monitoring

Add health check endpoint (optional enhancement):

```python
@app.get("/health")
async def health_check():
    return {"status": "healthy"}
```

---

## Cloud Deployment Options

| Platform | Method | Notes |
|----------|--------|-------|
| **Railway** | Connect GitHub repo, set env vars | Simplest deployment |
| **Render** | Docker or native Python | Free tier available |
| **AWS ECS** | Push Docker images to ECR | Production-grade, scalable |
| **GCP Cloud Run** | Container-based | Auto-scaling, pay-per-use |
| **DigitalOcean App Platform** | Docker support | Simple and affordable |
| **VPS (any provider)** | Docker Compose directly | Full control |

### Generic Cloud Steps

1. Push Docker images to a container registry
2. Set `GROQ_API_KEY` as an environment variable / secret
3. Ensure `data/` volume is persisted
4. Expose ports 8000 (backend) and 8501 (frontend)
5. Configure DNS and TLS termination
