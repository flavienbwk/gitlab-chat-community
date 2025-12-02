.PHONY: dev dev-build logs down clean migrate migrate-new test shell-backend shell-frontend celery-monitor rebuild-backend rebuild-frontend prod prod-build prod-down prod-logs help

# Load .env file if it exists
-include .env
export

# Determine compose profiles based on EMBEDDING_PROVIDER
ifeq ($(EMBEDDING_PROVIDER),local)
COMPOSE_PROFILES := --profile local-embeddings
else
COMPOSE_PROFILES :=
endif

# Default target
help:
	@echo "GitLab Chat Community - Commands"
	@echo ""
	@echo "Usage: make [target]"
	@echo ""
	@echo "Development:"
	@echo "  dev            Start all services for development (with hot reload)"
	@echo "  dev-build      Start all services with rebuild"
	@echo "  logs           Follow logs from all services"
	@echo "  down           Stop all services"
	@echo ""
	@echo "Production:"
	@echo "  prod           Start production stack (with nginx, basic auth)"
	@echo "  prod-build     Build and start production stack"
	@echo "  prod-down      Stop production stack"
	@echo "  prod-logs      Follow logs from production stack"
	@echo ""
	@echo "Database:"
	@echo "  migrate        Run database migrations"
	@echo "  migrate-new    Create new migration (use: make migrate-new name='description')"
	@echo ""
	@echo "Testing:"
	@echo "  test           Run all tests"
	@echo ""
	@echo "Utilities:"
	@echo "  shell-backend  Open shell in backend container"
	@echo "  shell-frontend Open shell in frontend container"
	@echo "  celery-monitor Monitor Celery workers"
	@echo ""
	@echo "Cleanup:"
	@echo "  clean          Stop services and remove volumes"
	@echo ""
	@echo "Rebuild:"
	@echo "  rebuild-backend  Rebuild backend service"
	@echo "  rebuild-frontend Rebuild frontend service"
	@echo ""
	@echo "Current config:"
	@echo "  EMBEDDING_PROVIDER=$(EMBEDDING_PROVIDER)"
ifeq ($(EMBEDDING_PROVIDER),local)
	@echo "  Local embeddings enabled (embedding-server will start)"
	@echo "  LOCAL_EMBEDDING_ENABLE_CUDA=$(LOCAL_EMBEDDING_ENABLE_CUDA)"
endif

# Development
dev:
	docker compose $(COMPOSE_PROFILES) up

dev-build:
	docker compose $(COMPOSE_PROFILES) up --build

logs:
	docker compose $(COMPOSE_PROFILES) logs -f

down:
	docker compose $(COMPOSE_PROFILES) down

# Database
migrate:
	docker compose $(COMPOSE_PROFILES) exec backend alembic upgrade head

migrate-new:
	@if [ -z "$(name)" ]; then \
		echo "Error: Please provide a migration name. Usage: make migrate-new name='description'"; \
		exit 1; \
	fi
	docker compose $(COMPOSE_PROFILES) exec backend alembic revision --autogenerate -m "$(name)"

# Cleanup
clean:
	docker compose $(COMPOSE_PROFILES) down -v
	rm -rf backend/__pycache__ backend/.pytest_cache
	rm -rf frontend/.next frontend/node_modules

# Testing
test:
	docker compose $(COMPOSE_PROFILES) exec backend pytest
	docker compose $(COMPOSE_PROFILES) exec frontend npm test

# Utility shells
shell-backend:
	docker compose $(COMPOSE_PROFILES) exec backend /bin/bash

shell-frontend:
	docker compose $(COMPOSE_PROFILES) exec frontend /bin/sh

# Celery monitoring
celery-monitor:
	docker compose $(COMPOSE_PROFILES) exec celery_worker celery -A tasks.celery_app inspect active

# Rebuild specific services
rebuild-backend:
	docker compose $(COMPOSE_PROFILES) up --build -d backend celery_worker

rebuild-frontend:
	docker compose $(COMPOSE_PROFILES) up --build -d frontend

# Production
prod:
	docker compose -f prod.docker-compose.yml $(COMPOSE_PROFILES) up -d

prod-build:
	docker compose -f prod.docker-compose.yml $(COMPOSE_PROFILES) up -d --build

prod-down:
	docker compose -f prod.docker-compose.yml $(COMPOSE_PROFILES) down

prod-logs:
	docker compose -f prod.docker-compose.yml $(COMPOSE_PROFILES) logs -f

prod-migrate:
	docker compose -f prod.docker-compose.yml exec backend alembic upgrade head
