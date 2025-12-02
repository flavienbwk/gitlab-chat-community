# GitLab Chat Community

<div align="center">

![GitLab Chat](https://img.shields.io/badge/GitLab-Chat-orange?style=for-the-badge&logo=gitlab)
![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)
![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?style=for-the-badge&logo=docker)

**A RAG-powered AI assistant for querying your GitLab projects**

*Ask questions about issues, merge requests, and code in natural language*

</div>

---

## Features

- **Semantic Search** - Find relevant issues, MRs, and code using natural language
- **Conversational AI** - Chat interface with streaming responses
- **Full Project Indexing** - Index README, issues, merge requests, and code
- **Real-time Sync** - Keep your knowledge base up to date
- **Self-hosted** - Run entirely on your own infrastructure
- **Privacy-first** - Your code never leaves your servers

## Quick Start

### Prerequisites

- Docker & Docker Compose
- GitLab Personal Access Token (PAT) with `read_api` scope
- OpenAI API key (for chat inference)

### 1. Clone & Configure

```bash
git clone <repository-url>
cd gitlab-chat-community

# Copy environment template
cp .env.example .env
```

### 2. Edit `.env` with your credentials

```env
# Required
GITLAB_URL=https://gitlab.example.com
GITLAB_PAT=glpat-xxxxxxxxxxxx
OPENAI_API_KEY=sk-xxxxxxxxxxxx

# Optional: Use local embeddings instead of OpenAI
EMBEDDING_PROVIDER=local  # or "openai"
```

### 3. Start the application

```bash
# Start all services
make dev

# Or with rebuild
make dev-build
```

### 4. Access the UI

Open [http://localhost:3000](http://localhost:3000) in your browser.

---

## Usage

### Indexing Projects

1. Navigate to **Manage Projects** in the sidebar
2. Click **Refresh** to fetch your GitLab projects
3. Select projects you want to query
4. Click **Index** to start indexing

### Chatting

Once indexed, you can ask questions like:

- *"What are the recent issues in project X?"*
- *"Summarize merge request !42"*
- *"How does the authentication system work?"*
- *"Find issues labeled 'bug' that are still open"*

---

## Configuration

### Embedding Providers

| Provider | Pros | Cons |
|----------|------|------|
| `openai` | High quality, fast | Requires API key, costs money |
| `local` | Free, private | Requires more resources |

To use local embeddings:

```env
EMBEDDING_PROVIDER=local
ENABLE_CUDA=1  # If you have a GPU
```

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `GITLAB_URL` | Your GitLab instance URL | - |
| `GITLAB_PAT` | Personal Access Token | - |
| `OPENAI_API_KEY` | OpenAI API key | - |
| `OPENAI_MODEL` | LLM model for chat | `gpt-4o` |
| `EMBEDDING_PROVIDER` | `openai` or `local` | `openai` |
| `CHUNK_SIZE` | Token chunk size | `512` |
| `TOP_K_RESULTS` | Search results count | `10` |

---

## Development

### Available Commands

```bash
make dev              # Start all services
make dev-build        # Start with rebuild
make logs             # View logs
make down             # Stop services
make clean            # Stop and remove volumes

make migrate          # Run database migrations
make test             # Run tests

make shell-backend    # Shell into backend container
make shell-frontend   # Shell into frontend container
```

---

## Troubleshooting

### Common Issues

**"Connection refused" errors**

```bash
# Ensure all services are running
docker compose ps
```

**Indexing stuck**

```bash
# Check celery worker logs
docker compose logs celery_worker
```

**Empty search results**

- Ensure projects are indexed (check status in UI)
- Try re-indexing the project

---

## License

MIT License - see [LICENSE](LICENSE) for details.

---

<div align="center">

Made with care for the GitLab community

</div>
