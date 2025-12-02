"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import chat, conversations, projects, providers
from config import get_settings
from db.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    await init_db()
    yield
    # Shutdown
    pass


app = FastAPI(
    title="GitLab Chat Community",
    description="RAG-enabled chatbot for querying GitLab issues, merge requests, and code",
    version="1.0.0",
    lifespan=lifespan,
)

# Configure CORS
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://frontend:3000",
        "http://localhost",
        "http://nginx",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(chat.router, prefix="/api", tags=["chat"])
app.include_router(conversations.router, prefix="/api", tags=["conversations"])
app.include_router(projects.router, prefix="/api", tags=["projects"])
app.include_router(providers.router, prefix="/api", tags=["providers"])


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "GitLab Chat Community API",
        "docs": "/docs",
        "health": "/health",
    }
