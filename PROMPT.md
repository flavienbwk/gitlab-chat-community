# GitLab Chat Community - Development Specification

## Project Overview

Build **GitLab Chat Community**: a NextJS web UI agentic chatbot with RAG (Retrieval-Augmented Generation) capabilities for querying issues, merge requests (PRs), and code from a self-hosted or cloud GitLab instance.

---

## Target Use Cases

The chatbot must be capable of answering queries such as:

1. **Counting/Filtering Issues**: "How many issues created in the last 3 months have 'Holograph' in their title?"
2. **Semantic Search**: "What is the issue talking about feedbacks for Arvo?" (return multiple if applicable)
3. **Recency Queries**: "What are the latest issues talking about Arvo?"
4. **Label Filtering**: "What are issues tagged 'Freelance:To bill' and 'Done'?"
5. **Summarization**: "Summarize issue 1995"
6. **Comment Search**: "In which issue did I talk about my finances?" (pointing to specific comments)
7. **Code Search**: "Which part of the code lists settings in its API?"

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              DOCKER COMPOSE                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────┐     ┌──────────────────────────────────────────────────┐  │
│  │   NextJS     │     │              Python Backend                       │  │
│  │   Frontend   │────▶│  ┌─────────────┐  ┌─────────────────────────┐    │  │
│  │   (Port 3000)│     │  │  FastAPI    │  │     Celery Workers      │    │  │
│  └──────────────┘     │  │  REST API   │  │  - Indexing Tasks       │    │  │
│                       │  └─────────────┘  │  - Code Analysis Tasks  │    │  │
│                       │         │         │  - GitLab Sync Tasks    │    │  │
│                       │         ▼         └─────────────────────────┘    │  │
│                       │  ┌─────────────┐          │                      │  │
│                       │  │   Agent     │          │                      │  │
│                       │  │   (LLM)     │◀─────────┘                      │  │
│                       │  └─────────────┘                                 │  │
│                       └──────────────────────────────────────────────────┘  │
│                                    │                                         │
│           ┌────────────────────────┼────────────────────────┐               │
│           ▼                        ▼                        ▼               │
│  ┌──────────────┐       ┌──────────────┐         ┌──────────────────┐      │
│  │  PostgreSQL  │       │   Qdrant     │         │   Redis          │      │
│  │  (Metadata)  │       │  (Vectors)   │         │  (Celery Broker) │      │
│  └──────────────┘       └──────────────┘         └──────────────────┘      │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                     Cloned Repositories Volume                        │   │
│  │                        /app/repos/{project_id}/                       │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
                        ┌──────────────────────┐
                        │   GitLab Instance    │
                        │   (External API)     │
                        └──────────────────────┘
```

---

## Technology Stack

### Frontend
- **Framework**: Next.js 14+ (App Router)
- **UI Library**: React 18+
- **Styling**: Tailwind CSS
- **State Management**: React Context / Zustand
- **HTTP Client**: Axios or Fetch API

### Backend
- **Language**: Python 3.11+
- **Web Framework**: FastAPI
- **Task Queue**: Celery with Redis broker
- **ORM**: SQLAlchemy 2.0+
- **Database Migrations**: Alembic (idempotent migrations)

### Databases
- **PostgreSQL 16+**: Conversation history, project configurations, indexing state
- **Qdrant**: Vector database for embeddings
- **Redis**: Celery broker and result backend

### AI/ML
- **LLM Provider**: OpenAI API
- **Model**: GPT 5.1 Thinking (configurable via environment variable)
- **Embeddings**: OpenAI `text-embedding-3-small` or `text-embedding-3-large`

### Infrastructure
- **Containerization**: Docker + Docker Compose
- **Build Automation**: Makefile

---

## Environment Variables

```bash
# GitLab Configuration
GITLAB_URL=https://gitlab.example.com
GITLAB_PAT=glpat-xxxxxxxxxxxxxxxxxxxx

# OpenAI Configuration
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxx
OPENAI_MODEL=gpt-5.1-thinking  # Configurable
OPENAI_EMBEDDING_MODEL=text-embedding-3-small

# Database Configuration
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=gitlab_chat
POSTGRES_USER=gitlab_chat
POSTGRES_PASSWORD=secure_password_here

# Qdrant Configuration
QDRANT_HOST=qdrant
QDRANT_PORT=6333

# Redis Configuration
REDIS_URL=redis://redis:6379/0

# Application Settings
CHUNK_SIZE=512
CHUNK_OVERLAP=50
TOP_K_RESULTS=10
```

---

## GitLab API Integration (v4)

### Authentication
All requests must include the Personal Access Token (PAT):
```http
PRIVATE-TOKEN: <your_access_token>
```

### Core Endpoints

#### Projects API
```http
# List accessible projects
GET /api/v4/projects?membership=true&per_page=100

# Get single project details
GET /api/v4/projects/:id

# Response includes:
# - id, name, description, path_with_namespace
# - http_url_to_repo, ssh_url_to_repo (for cloning)
# - default_branch
```

#### Issues API
```http
# List project issues with filters
GET /api/v4/projects/:id/issues
  ?state=opened|closed|all
  &labels=label1,label2
  &search=keyword
  &in=title,description
  &created_after=2024-01-01T00:00:00Z
  &created_before=2024-12-31T23:59:59Z
  &order_by=created_at|updated_at
  &sort=asc|desc
  &per_page=100
  &page=1

# Get single issue
GET /api/v4/projects/:id/issues/:issue_iid

# Response includes:
# - iid, title, description, state, labels
# - author, assignees, milestone
# - created_at, updated_at, closed_at
# - time_stats (time_estimate, total_time_spent)
# - user_notes_count
# - web_url
```

#### Issue Notes/Comments API
```http
# List all notes for an issue
GET /api/v4/projects/:id/issues/:issue_iid/notes
  ?sort=asc|desc
  &order_by=created_at|updated_at

# Response includes:
# - id, body, author
# - created_at, updated_at
# - system (boolean - system-generated vs user comment)
# - noteable_iid
```

#### Issue Discussions API (Threaded Comments)
```http
# List all discussion threads for an issue
GET /api/v4/projects/:id/issues/:issue_iid/discussions

# Response includes nested notes:
# - id (discussion_id)
# - individual_note (boolean)
# - notes[] array with:
#   - id, type, body, author
#   - created_at, updated_at
#   - noteable_id, noteable_type
```

#### Merge Requests API
```http
# List project merge requests
GET /api/v4/projects/:id/merge_requests
  ?state=opened|closed|merged|all
  &labels=label1,label2
  &search=keyword
  &order_by=created_at|updated_at
  &sort=asc|desc
  &per_page=100

# Get single merge request
GET /api/v4/projects/:id/merge_requests/:merge_request_iid

# Get MR changes/diffs
GET /api/v4/projects/:id/merge_requests/:merge_request_iid/diffs

# Get MR commits
GET /api/v4/projects/:id/merge_requests/:merge_request_iid/commits

# Response includes:
# - iid, title, description, state
# - source_branch, target_branch
# - author, assignee, reviewers
# - merged_by, merged_at
# - diff_refs, changes_count
# - web_url
```

#### MR Notes/Discussions API
```http
# List MR notes
GET /api/v4/projects/:id/merge_requests/:merge_request_iid/notes

# List MR discussions (threaded, includes diff comments)
GET /api/v4/projects/:id/merge_requests/:merge_request_iid/discussions

# MR diff discussions include position info:
# - position.new_line, position.old_line
# - position.new_path, position.old_path
```

#### Repository API
```http
# Get repository tree (file listing)
GET /api/v4/projects/:id/repository/tree
  ?path=subdir
  &ref=main
  &recursive=true
  &per_page=100

# Get file content
GET /api/v4/projects/:id/repository/files/:file_path
  ?ref=main

# Get raw file content
GET /api/v4/projects/:id/repository/files/:file_path/raw
  ?ref=main

# Note: file_path must be URL-encoded (e.g., src%2Fmain.py)
```

#### Pagination
GitLab uses offset-based pagination by default:
```http
GET /api/v4/projects/:id/issues?per_page=100&page=1

# Response headers:
# X-Page: current page
# X-Per-Page: items per page  
# X-Total: total items
# X-Total-Pages: total pages
# X-Next-Page: next page number
# X-Prev-Page: previous page number
```

---

## Database Schema (PostgreSQL)

### Migrations Strategy
Use Alembic with idempotent migrations. Each migration should be safe to run multiple times.

```python
# alembic/versions/001_initial_schema.py

def upgrade():
    # Projects table
    op.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id SERIAL PRIMARY KEY,
            gitlab_id INTEGER UNIQUE NOT NULL,
            name VARCHAR(255) NOT NULL,
            path_with_namespace VARCHAR(500) NOT NULL,
            description TEXT,
            default_branch VARCHAR(100) DEFAULT 'main',
            http_url_to_repo VARCHAR(500),
            is_indexed BOOLEAN DEFAULT FALSE,
            last_indexed_at TIMESTAMP,
            indexing_status VARCHAR(50) DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        )
    """)

    # Conversations table
    op.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            title VARCHAR(500),
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        )
    """)

    # Messages table
    op.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            conversation_id UUID REFERENCES conversations(id) ON DELETE CASCADE,
            role VARCHAR(20) NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
            content TEXT NOT NULL,
            metadata JSONB DEFAULT '{}',
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)

    # Indexed items tracking
    op.execute("""
        CREATE TABLE IF NOT EXISTS indexed_items (
            id SERIAL PRIMARY KEY,
            project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
            item_type VARCHAR(50) NOT NULL,
            item_id INTEGER NOT NULL,
            item_iid INTEGER,
            qdrant_point_ids TEXT[],
            last_updated_at TIMESTAMP,
            indexed_at TIMESTAMP DEFAULT NOW(),
            UNIQUE(project_id, item_type, item_id)
        )
    """)

    # Create indexes
    op.execute("CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_indexed_items_project ON indexed_items(project_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_indexed_items_type ON indexed_items(item_type)")
```

---

## RAG Implementation

### Chunking Strategy

Apply content-aware chunking based on document type:

```python
from typing import List, Dict, Any
from dataclasses import dataclass
import tiktoken

@dataclass
class Chunk:
    content: str
    metadata: Dict[str, Any]
    token_count: int

class ChunkingStrategy:
    def __init__(self, chunk_size: int = 512, chunk_overlap: int = 50):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.tokenizer = tiktoken.get_encoding("cl100k_base")
    
    def chunk_issue(self, issue: Dict) -> List[Chunk]:
        """Chunk an issue with semantic boundaries."""
        chunks = []
        
        # Chunk 1: Title + metadata (always first chunk)
        title_chunk = self._create_metadata_chunk(issue)
        chunks.append(title_chunk)
        
        # Chunk 2+: Description with semantic splitting
        if issue.get('description'):
            desc_chunks = self._semantic_chunk(
                issue['description'],
                base_metadata={
                    'type': 'issue_description',
                    'issue_iid': issue['iid'],
                    'project_id': issue['project_id']
                }
            )
            chunks.extend(desc_chunks)
        
        return chunks
    
    def chunk_comment(self, comment: Dict, parent_context: Dict) -> List[Chunk]:
        """Chunk a comment with parent context."""
        # Include parent context in metadata for retrieval
        metadata = {
            'type': 'comment',
            'comment_id': comment['id'],
            'author': comment['author']['username'],
            'parent_type': parent_context['type'],
            'parent_iid': parent_context['iid'],
            'project_id': parent_context['project_id'],
            'created_at': comment['created_at'],
            'is_system': comment.get('system', False)
        }
        
        # Skip system-generated comments for semantic search
        if comment.get('system', False):
            return []
        
        return self._semantic_chunk(comment['body'], metadata)
    
    def chunk_code_file(self, file_path: str, content: str, project_id: int) -> List[Chunk]:
        """Chunk code files with syntax-aware boundaries."""
        chunks = []
        
        # Detect language from extension
        language = self._detect_language(file_path)
        
        # Use language-specific chunking
        if language in ['python', 'javascript', 'typescript']:
            chunks = self._chunk_by_functions(content, language, file_path, project_id)
        else:
            chunks = self._chunk_by_lines(content, file_path, project_id)
        
        return chunks
    
    def _semantic_chunk(self, text: str, base_metadata: Dict) -> List[Chunk]:
        """Split text into semantic chunks respecting boundaries."""
        # Split by paragraphs first
        paragraphs = text.split('\n\n')
        
        chunks = []
        current_chunk = ""
        current_tokens = 0
        
        for para in paragraphs:
            para_tokens = len(self.tokenizer.encode(para))
            
            if current_tokens + para_tokens > self.chunk_size:
                if current_chunk:
                    chunks.append(Chunk(
                        content=current_chunk.strip(),
                        metadata=base_metadata.copy(),
                        token_count=current_tokens
                    ))
                
                # Handle paragraphs larger than chunk_size
                if para_tokens > self.chunk_size:
                    sub_chunks = self._split_large_paragraph(para, base_metadata)
                    chunks.extend(sub_chunks)
                    current_chunk = ""
                    current_tokens = 0
                else:
                    # Start new chunk with overlap from previous
                    overlap_text = self._get_overlap_text(current_chunk)
                    current_chunk = overlap_text + para
                    current_tokens = len(self.tokenizer.encode(current_chunk))
            else:
                current_chunk += "\n\n" + para if current_chunk else para
                current_tokens += para_tokens
        
        # Don't forget the last chunk
        if current_chunk.strip():
            chunks.append(Chunk(
                content=current_chunk.strip(),
                metadata=base_metadata.copy(),
                token_count=current_tokens
            ))
        
        return chunks
```

### Embedding Strategy

```python
from openai import OpenAI
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct
import hashlib

class EmbeddingService:
    def __init__(self):
        self.openai = OpenAI()
        self.qdrant = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
        self.embedding_model = OPENAI_EMBEDDING_MODEL
        self.collection_name = "gitlab_content"
        
        self._ensure_collection()
    
    def _ensure_collection(self):
        """Create collection if not exists."""
        collections = self.qdrant.get_collections().collections
        if not any(c.name == self.collection_name for c in collections):
            self.qdrant.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=1536,  # text-embedding-3-small
                    distance=Distance.COSINE
                )
            )
    
    def embed_chunks(self, chunks: List[Chunk]) -> List[str]:
        """Embed chunks and store in Qdrant."""
        # Batch embedding for efficiency
        texts = [c.content for c in chunks]
        
        response = self.openai.embeddings.create(
            model=self.embedding_model,
            input=texts
        )
        
        points = []
        point_ids = []
        
        for i, (chunk, embedding_data) in enumerate(zip(chunks, response.data)):
            # Generate deterministic ID based on content hash
            point_id = self._generate_point_id(chunk)
            point_ids.append(point_id)
            
            points.append(PointStruct(
                id=point_id,
                vector=embedding_data.embedding,
                payload={
                    "content": chunk.content,
                    "token_count": chunk.token_count,
                    **chunk.metadata
                }
            ))
        
        # Upsert to handle re-indexing
        self.qdrant.upsert(
            collection_name=self.collection_name,
            points=points
        )
        
        return point_ids
    
    def search(self, query: str, filters: Dict = None, top_k: int = 10) -> List[Dict]:
        """Search for relevant chunks."""
        # Embed query
        response = self.openai.embeddings.create(
            model=self.embedding_model,
            input=[query]
        )
        query_vector = response.data[0].embedding
        
        # Build filter conditions
        filter_conditions = None
        if filters:
            filter_conditions = self._build_filter(filters)
        
        results = self.qdrant.search(
            collection_name=self.collection_name,
            query_vector=query_vector,
            query_filter=filter_conditions,
            limit=top_k,
            with_payload=True
        )
        
        return [
            {
                "content": r.payload["content"],
                "metadata": {k: v for k, v in r.payload.items() if k != "content"},
                "score": r.score
            }
            for r in results
        ]
    
    def _generate_point_id(self, chunk: Chunk) -> str:
        """Generate deterministic ID for deduplication."""
        content_hash = hashlib.sha256(
            f"{chunk.metadata.get('project_id')}:"
            f"{chunk.metadata.get('type')}:"
            f"{chunk.metadata.get('item_id', '')}:"
            f"{chunk.content[:100]}"
            .encode()
        ).hexdigest()[:32]
        return content_hash
```

### Retrieval Strategy

Implement hybrid retrieval combining:
1. **Vector search**: Semantic similarity via Qdrant
2. **Keyword filtering**: GitLab API filters for structured queries
3. **Metadata filtering**: Project, date range, labels, etc.

```python
class HybridRetriever:
    def __init__(self, embedding_service: EmbeddingService, gitlab_client: GitLabClient):
        self.embeddings = embedding_service
        self.gitlab = gitlab_client
    
    async def retrieve(self, query: str, context: Dict) -> List[Dict]:
        """Hybrid retrieval combining vector search and API filters."""
        
        # Extract structured filters from query using LLM
        filters = await self._extract_filters(query)
        
        results = []
        
        # 1. Vector search for semantic matching
        vector_results = self.embeddings.search(
            query=query,
            filters={
                "project_id": context.get("selected_projects", []),
                **filters.get("vector_filters", {})
            },
            top_k=TOP_K_RESULTS
        )
        results.extend(vector_results)
        
        # 2. Direct API queries for structured data
        if filters.get("needs_api_query"):
            api_results = await self._query_gitlab_api(filters)
            results.extend(api_results)
        
        # 3. Deduplicate and rank
        ranked_results = self._rank_and_dedupe(results, query)
        
        return ranked_results[:TOP_K_RESULTS]
```

---

## Agentic Code Analysis

For code-related queries, implement an agentic approach similar to Claude CLI:

```python
import subprocess
import os
from pathlib import Path

class CodeAnalysisAgent:
    def __init__(self, repos_base_path: str = "/app/repos"):
        self.repos_path = Path(repos_base_path)
        self.repos_path.mkdir(parents=True, exist_ok=True)
    
    async def ensure_repo_cloned(self, project: Dict) -> Path:
        """Clone or update repository."""
        repo_path = self.repos_path / str(project['gitlab_id'])
        
        if repo_path.exists():
            # Pull latest changes
            subprocess.run(
                ["git", "pull", "--ff-only"],
                cwd=repo_path,
                capture_output=True
            )
        else:
            # Clone with PAT authentication
            clone_url = project['http_url_to_repo'].replace(
                "https://",
                f"https://oauth2:{GITLAB_PAT}@"
            )
            subprocess.run(
                ["git", "clone", "--depth=1", clone_url, str(repo_path)],
                capture_output=True
            )
        
        return repo_path
    
    async def analyze_code(self, query: str, project_id: int) -> Dict:
        """Agentically analyze code to answer query."""
        
        # Tools available to the agent
        tools = [
            {
                "name": "search_code",
                "description": "Search for patterns in code using ripgrep",
                "function": self._search_code
            },
            {
                "name": "read_file",
                "description": "Read contents of a specific file",
                "function": self._read_file
            },
            {
                "name": "list_directory",
                "description": "List files in a directory",
                "function": self._list_directory
            },
            {
                "name": "find_definitions",
                "description": "Find function/class definitions",
                "function": self._find_definitions
            }
        ]
        
        # Run agent loop
        repo_path = self.repos_path / str(project_id)
        
        messages = [
            {"role": "system", "content": self._get_code_agent_prompt(repo_path)},
            {"role": "user", "content": query}
        ]
        
        max_iterations = 10
        for _ in range(max_iterations):
            response = await self._call_llm_with_tools(messages, tools)
            
            if response.get("done"):
                return response["answer"]
            
            # Execute tool calls
            tool_results = await self._execute_tools(
                response["tool_calls"], 
                repo_path
            )
            messages.append({"role": "assistant", "content": response["content"]})
            messages.append({"role": "user", "content": f"Tool results:\n{tool_results}"})
        
        return {"error": "Max iterations reached"}
    
    def _search_code(self, repo_path: Path, pattern: str, file_type: str = None) -> str:
        """Search code using ripgrep."""
        cmd = ["rg", "--json", "-C", "3", pattern]
        if file_type:
            cmd.extend(["-t", file_type])
        
        result = subprocess.run(
            cmd,
            cwd=repo_path,
            capture_output=True,
            text=True
        )
        return result.stdout
    
    def _read_file(self, repo_path: Path, file_path: str) -> str:
        """Read file contents."""
        full_path = repo_path / file_path
        if not full_path.exists():
            return f"File not found: {file_path}"
        if not full_path.is_relative_to(repo_path):
            return "Access denied: path traversal attempt"
        return full_path.read_text()[:10000]  # Limit size
    
    def _get_code_agent_prompt(self, repo_path: Path) -> str:
        return f"""You are a code analysis agent. You have access to a repository at {repo_path}.

Your goal is to answer questions about the codebase by:
1. Searching for relevant code patterns
2. Reading specific files
3. Understanding the code structure
4. Synthesizing findings into a clear answer

Use the available tools to explore the codebase. When you have enough information, provide your final answer.

Always cite specific files and line numbers when referencing code."""
```

---

## Celery Task Queue

```python
# backend/tasks/indexing.py
from celery import Celery, chain, group
from celery.utils.log import get_task_logger

celery_app = Celery(
    'gitlab_chat',
    broker=REDIS_URL,
    backend=REDIS_URL
)

celery_app.conf.update(
    task_serializer='json',
    result_serializer='json',
    accept_content=['json'],
    task_routes={
        'tasks.indexing.*': {'queue': 'indexing'},
        'tasks.code_analysis.*': {'queue': 'code_analysis'},
        'tasks.gitlab_sync.*': {'queue': 'gitlab_sync'},
    }
)

logger = get_task_logger(__name__)


@celery_app.task(bind=True, max_retries=3)
def index_project(self, project_id: int):
    """Index all content from a GitLab project."""
    try:
        # Update status
        update_project_status(project_id, 'indexing')
        
        # Chain of indexing tasks
        workflow = chain(
            fetch_and_index_issues.s(project_id),
            fetch_and_index_merge_requests.s(project_id),
            clone_and_index_code.s(project_id),
            finalize_indexing.s(project_id)
        )
        workflow.apply_async()
        
    except Exception as exc:
        update_project_status(project_id, 'error')
        raise self.retry(exc=exc, countdown=60)


@celery_app.task(bind=True)
def fetch_and_index_issues(self, project_id: int):
    """Fetch and index all issues for a project."""
    gitlab = GitLabClient()
    chunker = ChunkingStrategy()
    embedder = EmbeddingService()
    
    page = 1
    while True:
        issues = gitlab.get_issues(project_id, page=page, per_page=100)
        if not issues:
            break
        
        for issue in issues:
            # Chunk issue content
            chunks = chunker.chunk_issue(issue)
            
            # Fetch and chunk comments
            comments = gitlab.get_issue_notes(project_id, issue['iid'])
            for comment in comments:
                comment_chunks = chunker.chunk_comment(
                    comment,
                    {'type': 'issue', 'iid': issue['iid'], 'project_id': project_id}
                )
                chunks.extend(comment_chunks)
            
            # Embed and store
            point_ids = embedder.embed_chunks(chunks)
            
            # Track indexed item
            track_indexed_item(project_id, 'issue', issue['id'], issue['iid'], point_ids)
        
        page += 1
        
        # Rate limiting
        time.sleep(0.5)
    
    return {"issues_indexed": page - 1}


@celery_app.task(bind=True)
def clone_and_index_code(self, project_id: int):
    """Clone repository and index code files."""
    agent = CodeAnalysisAgent()
    chunker = ChunkingStrategy()
    embedder = EmbeddingService()
    
    project = get_project(project_id)
    repo_path = agent.ensure_repo_cloned(project)
    
    # Index code files
    for file_path in repo_path.rglob("*"):
        if file_path.is_file() and is_indexable_file(file_path):
            try:
                content = file_path.read_text()
                rel_path = str(file_path.relative_to(repo_path))
                
                chunks = chunker.chunk_code_file(rel_path, content, project_id)
                embedder.embed_chunks(chunks)
            except Exception as e:
                logger.warning(f"Failed to index {file_path}: {e}")
    
    return {"code_indexed": True}


def is_indexable_file(path: Path) -> bool:
    """Check if file should be indexed."""
    # Skip binary files, node_modules, etc.
    skip_dirs = {'.git', 'node_modules', '__pycache__', 'venv', '.venv', 'dist', 'build'}
    skip_extensions = {'.pyc', '.pyo', '.so', '.dll', '.exe', '.bin', '.jpg', '.png', '.gif'}
    
    if any(part in skip_dirs for part in path.parts):
        return False
    if path.suffix.lower() in skip_extensions:
        return False
    if path.stat().st_size > 1_000_000:  # Skip files > 1MB
        return False
    
    return True
```

---

## Frontend Implementation

### Next.js Structure

```
frontend/
├── app/
│   ├── layout.tsx
│   ├── page.tsx                 # Chat interface
│   ├── projects/
│   │   └── page.tsx             # Project selection
│   └── api/                     # API routes (proxy to backend)
├── components/
│   ├── ChatInterface.tsx
│   ├── MessageList.tsx
│   ├── MessageInput.tsx
│   ├── ProjectSelector.tsx
│   ├── ConversationHistory.tsx
│   └── IndexingStatus.tsx
├── lib/
│   ├── api.ts                   # Backend API client
│   └── types.ts
└── hooks/
    ├── useChat.ts
    └── useProjects.ts
```

### Chat Interface Component

```tsx
// components/ChatInterface.tsx
'use client';

import { useState, useRef, useEffect } from 'react';
import { useChat } from '@/hooks/useChat';
import MessageList from './MessageList';
import MessageInput from './MessageInput';
import ConversationHistory from './ConversationHistory';

export default function ChatInterface() {
  const {
    messages,
    isLoading,
    sendMessage,
    conversations,
    currentConversation,
    selectConversation,
    clearHistory,
    createNewConversation
  } = useChat();
  
  const messagesEndRef = useRef<HTMLDivElement>(null);
  
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);
  
  return (
    <div className="flex h-screen bg-gray-50">
      {/* Sidebar - Conversation History */}
      <div className="w-64 bg-white border-r border-gray-200 flex flex-col">
        <div className="p-4 border-b">
          <button
            onClick={createNewConversation}
            className="w-full px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
          >
            New Chat
          </button>
        </div>
        
        <ConversationHistory
          conversations={conversations}
          currentId={currentConversation?.id}
          onSelect={selectConversation}
        />
        
        <div className="p-4 border-t mt-auto">
          <button
            onClick={clearHistory}
            className="w-full px-4 py-2 text-red-600 hover:bg-red-50 rounded-lg"
          >
            Clear History
          </button>
        </div>
      </div>
      
      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col">
        <header className="bg-white border-b px-6 py-4">
          <h1 className="text-xl font-semibold">GitLab Chat Community</h1>
        </header>
        
        <MessageList messages={messages} />
        <div ref={messagesEndRef} />
        
        <MessageInput
          onSend={sendMessage}
          isLoading={isLoading}
          placeholder="Ask about issues, merge requests, or code..."
        />
      </div>
    </div>
  );
}
```

### API Client

```typescript
// lib/api.ts
const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export const api = {
  // Chat endpoints
  async sendMessage(conversationId: string | null, message: string) {
    const response = await fetch(`${API_BASE}/api/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ conversation_id: conversationId, message })
    });
    return response.json();
  },
  
  async getConversations() {
    const response = await fetch(`${API_BASE}/api/conversations`);
    return response.json();
  },
  
  async getConversation(id: string) {
    const response = await fetch(`${API_BASE}/api/conversations/${id}`);
    return response.json();
  },
  
  async deleteConversation(id: string) {
    await fetch(`${API_BASE}/api/conversations/${id}`, { method: 'DELETE' });
  },
  
  async clearAllConversations() {
    await fetch(`${API_BASE}/api/conversations`, { method: 'DELETE' });
  },
  
  // Project endpoints
  async getProjects() {
    const response = await fetch(`${API_BASE}/api/projects`);
    return response.json();
  },
  
  async refreshProjects() {
    const response = await fetch(`${API_BASE}/api/projects/refresh`, {
      method: 'POST'
    });
    return response.json();
  },
  
  async selectProject(projectId: number) {
    const response = await fetch(`${API_BASE}/api/projects/${projectId}/select`, {
      method: 'POST'
    });
    return response.json();
  },
  
  async indexProject(projectId: number) {
    const response = await fetch(`${API_BASE}/api/projects/${projectId}/index`, {
      method: 'POST'
    });
    return response.json();
  },
  
  async getIndexingStatus(projectId: number) {
    const response = await fetch(`${API_BASE}/api/projects/${projectId}/status`);
    return response.json();
  }
};
```

---

## Docker Configuration

### docker-compose.yml

```yaml
version: '3.8'

services:
  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    ports:
      - "3000:3000"
    environment:
      - NEXT_PUBLIC_API_URL=http://backend:8000
    depends_on:
      - backend

  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    environment:
      - GITLAB_URL=${GITLAB_URL}
      - GITLAB_PAT=${GITLAB_PAT}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - OPENAI_MODEL=${OPENAI_MODEL:-gpt-5.1-thinking}
      - OPENAI_EMBEDDING_MODEL=${OPENAI_EMBEDDING_MODEL:-text-embedding-3-small}
      - POSTGRES_HOST=postgres
      - POSTGRES_PORT=5432
      - POSTGRES_DB=gitlab_chat
      - POSTGRES_USER=gitlab_chat
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
      - QDRANT_HOST=qdrant
      - QDRANT_PORT=6333
      - REDIS_URL=redis://redis:6379/0
    volumes:
      - repos_data:/app/repos
    depends_on:
      - postgres
      - qdrant
      - redis

  celery_worker:
    build:
      context: ./backend
      dockerfile: Dockerfile
    command: celery -A tasks worker -l info -Q indexing,code_analysis,gitlab_sync
    environment:
      - GITLAB_URL=${GITLAB_URL}
      - GITLAB_PAT=${GITLAB_PAT}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - OPENAI_EMBEDDING_MODEL=${OPENAI_EMBEDDING_MODEL:-text-embedding-3-small}
      - POSTGRES_HOST=postgres
      - POSTGRES_PORT=5432
      - POSTGRES_DB=gitlab_chat
      - POSTGRES_USER=gitlab_chat
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
      - QDRANT_HOST=qdrant
      - QDRANT_PORT=6333
      - REDIS_URL=redis://redis:6379/0
    volumes:
      - repos_data:/app/repos
    depends_on:
      - postgres
      - qdrant
      - redis

  postgres:
    image: postgres:16-alpine
    environment:
      - POSTGRES_DB=gitlab_chat
      - POSTGRES_USER=gitlab_chat
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U gitlab_chat"]
      interval: 5s
      timeout: 5s
      retries: 5

  qdrant:
    image: qdrant/qdrant:latest
    ports:
      - "6333:6333"
    volumes:
      - qdrant_data:/qdrant/storage
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:6333/health"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 5s
      retries: 5

volumes:
  postgres_data:
  qdrant_data:
  redis_data:
  repos_data:
```

### Backend Dockerfile

```dockerfile
# backend/Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    ripgrep \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Run migrations on startup
CMD ["sh", "-c", "alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port 8000"]
```

### Frontend Dockerfile

```dockerfile
# frontend/Dockerfile
FROM node:20-alpine AS builder

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build

FROM node:20-alpine AS runner

WORKDIR /app

ENV NODE_ENV=production

COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public

EXPOSE 3000

CMD ["node", "server.js"]
```

---

## Makefile

```makefile
.PHONY: dev dev-build logs down clean migrate test

# Development
dev:
	docker compose up

dev-build:
	docker compose up --build

logs:
	docker compose logs -f

down:
	docker compose down

# Database
migrate:
	docker compose exec backend alembic upgrade head

migrate-new:
	docker compose exec backend alembic revision --autogenerate -m "$(name)"

# Cleanup
clean:
	docker compose down -v
	rm -rf backend/__pycache__ backend/.pytest_cache
	rm -rf frontend/.next frontend/node_modules

# Testing
test:
	docker compose exec backend pytest
	docker compose exec frontend npm test

# Utility
shell-backend:
	docker compose exec backend /bin/bash

shell-frontend:
	docker compose exec frontend /bin/sh

# Celery monitoring
celery-monitor:
	docker compose exec celery_worker celery -A tasks inspect active

# Rebuild specific service
rebuild-%:
	docker compose up --build -d $*
```

---

## RAG Best Practices Summary

### Chunking Guidelines

1. **Chunk Size**: Start with 512 tokens, experiment between 256-1024
2. **Overlap**: Use 50-100 tokens overlap to maintain context across boundaries
3. **Semantic Boundaries**: Respect natural document structure (paragraphs, sections, functions)
4. **Metadata Enrichment**: Include rich metadata (source, type, author, date, labels)

### Embedding Best Practices

1. **Batch Processing**: Embed in batches for efficiency
2. **Deterministic IDs**: Use content hashes for deduplication
3. **Incremental Updates**: Only re-embed changed content

### Retrieval Optimization

1. **Hybrid Search**: Combine vector similarity with metadata filters
2. **Re-ranking**: Use cross-encoder or LLM to re-rank top results
3. **Context Window Management**: Limit total tokens in prompt
4. **Citation Tracking**: Track which chunks informed the response

### Quality Improvements

1. **Query Understanding**: Use LLM to extract structured filters from natural language
2. **Fallback Strategies**: If vector search fails, fall back to keyword search
3. **Confidence Scoring**: Return confidence scores with results
4. **Feedback Loop**: Allow users to rate responses for future improvement

---

## Project Directory Structure

```
gitlab-chat-community/
├── docker-compose.yml
├── Makefile
├── .env.example
├── README.md
│
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── main.py                    # FastAPI app entry
│   ├── config.py                  # Configuration management
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes/
│   │   │   ├── chat.py
│   │   │   ├── projects.py
│   │   │   └── conversations.py
│   │   └── dependencies.py
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   ├── gitlab_client.py       # GitLab API wrapper
│   │   ├── agent.py               # LLM agent orchestration
│   │   ├── chunking.py            # Chunking strategies
│   │   ├── embedding.py           # Embedding service
│   │   ├── retrieval.py           # Hybrid retrieval
│   │   └── code_analysis.py       # Code agent
│   │
│   ├── db/
│   │   ├── __init__.py
│   │   ├── database.py            # SQLAlchemy setup
│   │   ├── models.py              # ORM models
│   │   └── repositories.py        # Data access layer
│   │
│   ├── tasks/
│   │   ├── __init__.py
│   │   ├── celery_app.py          # Celery configuration
│   │   ├── indexing.py            # Indexing tasks
│   │   └── sync.py                # GitLab sync tasks
│   │
│   └── alembic/
│       ├── alembic.ini
│       ├── env.py
│       └── versions/
│
└── frontend/
    ├── Dockerfile
    ├── package.json
    ├── next.config.js
    ├── tailwind.config.js
    │
    ├── app/
    │   ├── layout.tsx
    │   ├── page.tsx
    │   ├── projects/
    │   │   └── page.tsx
    │   └── globals.css
    │
    ├── components/
    │   ├── ChatInterface.tsx
    │   ├── MessageList.tsx
    │   ├── MessageInput.tsx
    │   ├── ProjectSelector.tsx
    │   ├── ConversationHistory.tsx
    │   └── IndexingStatus.tsx
    │
    ├── lib/
    │   ├── api.ts
    │   └── types.ts
    │
    └── hooks/
        ├── useChat.ts
        └── useProjects.ts
```

---

## Implementation Checklist

### Phase 1: Foundation

- [x] Set up Docker Compose environment
- [x] Create FastAPI backend skeleton
- [x] Set up PostgreSQL with Alembic migrations
- [x] Implement GitLab API client
- [x] Create basic Next.js frontend

### Phase 2: Indexing Pipeline

- [x] Implement chunking strategies
- [x] Set up Qdrant collections
- [x] Create embedding service
- [x] Build Celery indexing tasks
- [x] Implement project selection UI

### Phase 3: RAG Chat

- [x] Build hybrid retrieval system
- [x] Implement LLM agent with tools
- [x] Create chat API endpoints
- [x] Build chat interface components
- [x] Add conversation history

### Phase 4: Code Analysis

- [x] Implement repository cloning
- [x] Build code analysis agent
- [x] Add code search tools
- [x] Integrate with chat flow

### Phase 5: UX

- [ ] Models selection with open-source capabilities

---

## Notes for Development

1. **No Authentication**: The frontend has no auth since secrets are backend-only
2. **Configurable LLM**: Model is set via `OPENAI_MODEL` env variable
3. **Incremental Indexing**: Support re-indexing without duplicating data
4. **Rate Limiting**: Respect GitLab API rate limits (use pagination, add delays)
5. **Error Recovery**: Celery tasks should be idempotent and retry-safe