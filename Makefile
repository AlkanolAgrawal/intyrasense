# ============================================================
# INTYRASENSE — Developer Makefile
# ============================================================

.PHONY: help install run run-backend run-frontend backend frontend docker-up docker-down docker-build clean

help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

# ---- Setup ----

install: ## Install all Python dependencies
	pip install --upgrade pip
	pip install -r requirements.txt
	pip install -r backend/requirements.txt
	pip install -r frontend/requirements.txt

# ---- Run ----

run: ## Start backend and frontend (requires two terminals)
	@echo "Starting backend on http://127.0.0.1:8000 ..."
	@echo "Starting frontend on http://localhost:8501 ..."
	@echo ""
	@echo "Run in separate terminals:"
	@echo "  make backend"
	@echo "  make frontend"

backend: ## Start the FastAPI backend server
	uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000

run-backend: backend ## Alias for backend

frontend: ## Start the Streamlit frontend
	streamlit run frontend/app.py

run-frontend: frontend ## Alias for frontend

# ---- Docker ----

docker-up: ## Build and start all services with Docker Compose
	docker compose -f Docker/docker-compose.yml up --build

docker-down: ## Stop all Docker services
	docker compose -f Docker/docker-compose.yml down

docker-build: ## Build Docker images without starting
	docker compose -f Docker/docker-compose.yml build

# ---- Cleanup ----

clean: ## Remove __pycache__ and compiled Python files
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@echo "Cleaned Python cache files."
