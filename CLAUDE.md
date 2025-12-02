# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

GitLab Chat Community is a RAG-powered AI assistant for querying GitLab projects. It indexes issues, merge requests, code, and comments into a vector database (Qdrant) and provides a conversational chat interface with streaming responses.

## Development Commands

```bash
# Development (all services with hot reload)
make dev              # Start all services
make dev-build        # Start with rebuild

# Production
make prod             # Start production stack with nginx
make prod-build       # Build and start production stack

# Database
make migrate          # Run Alembic migrations
make migrate-new name='description'  # Create new migration

# Testing
make test             # Run backend (pytest) and frontend (npm test) tests

# Utilities
make shell-backend    # Shell into backend container
make shell-frontend   # Shell into frontend container
make celery-monitor   # Monitor Celery workers

# Cleanup
make down             # Stop services
make clean            # Stop and remove volumes
```

## Architecture

### Backend (Python/FastAPI)

- **Entry point**: `backend/main.py` - FastAPI app with routers for chat, conversations, projects, and providers
- **API routes**: `backend/api/routes/` - REST endpoints
- **Core logic**:
  - `core/agent.py` - ChatAgent with RAG, supports OpenAI and Anthropic providers with streaming
  - `core/retrieval.py` - HybridRetriever combines vector search with GitLab API queries
  - `core/embedding.py` - EmbeddingService for OpenAI or local embeddings
  - `core/chunking.py` - ChunkingStrategy for splitting content
  - `core/code_analysis.py` - CodeAnalysisAgent for code-specific queries
  - `core/gitlab_client.py` - GitLab API client
- **Tasks**: `backend/tasks/` - Celery tasks for async indexing
  - `indexing.py` - Project indexing pipeline (README, issues, MRs, code)
  - `sync.py` - Incremental sync tasks
- **Database**: `backend/db/` - SQLAlchemy models and repositories
- **Config**: `backend/config.py` - Pydantic settings from environment variables

### Frontend (Next.js 14)

- **Pages**: `frontend/app/` - Next.js app router pages (chat, projects, settings)
- **Components**: `frontend/components/` - React components for chat interface, project management
- **API client**: `frontend/lib/api.ts` - Typed API client for backend communication
- **Hooks**: `frontend/hooks/` - Custom hooks for chat, projects, providers

### Infrastructure (Docker Compose)

Services: nginx, frontend, backend, celery_worker, postgres, qdrant, redis

Optional: `embedding-server` (local embeddings via Weaviate transformers, enabled with `EMBEDDING_PROVIDER=local`)

## Key Patterns

- **Embedding provider toggle**: Set `EMBEDDING_PROVIDER=openai` or `EMBEDDING_PROVIDER=local` in `.env`. Local embeddings use `--profile local-embeddings` compose profile.
- **LLM providers**: Configured via UI (Settings page), stored in database. Supports OpenAI, Anthropic, and custom OpenAI-compatible APIs.
- **Celery task chaining**: Indexing uses `chain()` to sequence README -> issues -> MRs -> code indexing.
- **SSE streaming**: Chat responses stream via Server-Sent Events with event types: message, title, done, error.

## Database Migrations

Migrations are in `backend/alembic/versions/`. Run `make migrate` after pulling changes that include new migrations. Create new migrations with `make migrate-new name='description'`.

## Env variables updates

Both `docker-compose.yml` and `prod.docker-compose.yml` must be updated for env variables if new ones are introduced or some are modified.
