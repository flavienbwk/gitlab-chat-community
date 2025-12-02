"""Application configuration using pydantic-settings."""

from functools import lru_cache
from typing import Literal, Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # GitLab Configuration
    gitlab_url: str = "https://gitlab.com"
    gitlab_pat: str = ""

    # LLM Configuration (for chat/inference)
    llm_provider: Literal["openai"] = "openai"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"
    openai_base_url: Optional[str] = None  # For OpenAI-compatible APIs

    # Embedding Configuration
    embedding_provider: Literal["openai", "local"] = "openai"
    # OpenAI embeddings
    openai_embedding_model: str = "text-embedding-3-small"
    # Local embeddings (sentence-transformers via embedding-server)
    local_embedding_url: str = "http://embedding-server:8080"
    local_embedding_dimension: int = 384  # MiniLM-L6-v2 outputs 384 dimensions

    # Database Configuration
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "gitlab_chat"
    postgres_user: str = "gitlab_chat"
    postgres_password: str = ""

    # Qdrant Configuration
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333

    # Redis Configuration
    redis_url: str = "redis://localhost:6379/0"

    # Application Settings
    chunk_size: int = 512
    chunk_overlap: int = 50
    top_k_results: int = 10

    # Repos path for cloned repositories
    repos_path: str = "/app/repos"

    @property
    def database_url(self) -> str:
        """Construct async database URL."""
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def sync_database_url(self) -> str:
        """Construct sync database URL for Alembic."""
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
