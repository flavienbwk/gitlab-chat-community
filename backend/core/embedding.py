"""Embedding service for vector storage."""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import httpx
from openai import OpenAI
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchAny,
    MatchValue,
    PointStruct,
    VectorParams,
)

from config import get_settings

if TYPE_CHECKING:
    from core.chunking import Chunk


class EmbeddingService:
    """Service for generating and storing embeddings in Qdrant."""

    COLLECTION_NAME = "gitlab_content"

    def __init__(self):
        settings = get_settings()
        self.settings = settings
        self.embedding_provider = settings.embedding_provider

        # Initialize OpenAI client (used for OpenAI embeddings)
        if self.embedding_provider == "openai":
            # Only pass base_url if it's actually set (not empty string)
            base_url = settings.openai_base_url if settings.openai_base_url else None
            self.openai = OpenAI(api_key=settings.openai_api_key, base_url=base_url)
            self.embedding_model = settings.openai_embedding_model
            self.vector_size = 1536  # text-embedding-3-small default
        else:
            self.openai = None
            self.embedding_model = None
            self.vector_size = settings.local_embedding_dimension  # 384 for MiniLM-L6-v2

        self.qdrant = QdrantClient(
            host=settings.qdrant_host, port=settings.qdrant_port
        )

        self._ensure_collection()

    def _ensure_collection(self):
        """Create collection if it doesn't exist or recreate if dimension changed."""
        collections = self.qdrant.get_collections().collections
        existing = next((c for c in collections if c.name == self.COLLECTION_NAME), None)

        if existing:
            # Check if vector size matches
            collection_info = self.qdrant.get_collection(self.COLLECTION_NAME)
            current_size = collection_info.config.params.vectors.size
            if current_size != self.vector_size:
                # Vector size changed (switched providers), need to recreate
                self.qdrant.delete_collection(self.COLLECTION_NAME)
                existing = None

        if not existing:
            self.qdrant.create_collection(
                collection_name=self.COLLECTION_NAME,
                vectors_config=VectorParams(
                    size=self.vector_size,
                    distance=Distance.COSINE,
                ),
            )

    def _generate_point_id(self, chunk: Chunk) -> str:
        """Generate deterministic ID for deduplication."""
        # Create hash from key metadata and content prefix
        hash_input = (
            f"{chunk.metadata.get('project_id', '')}:"
            f"{chunk.metadata.get('type', '')}:"
            f"{chunk.metadata.get('issue_id', chunk.metadata.get('mr_id', chunk.metadata.get('file_path', '')))}:"
            f"{chunk.content[:200]}"
        )
        return hashlib.sha256(hash_input.encode()).hexdigest()[:32]

    def _embed_openai(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings using OpenAI API."""
        if not texts:
            return []

        batch_size = 100
        all_embeddings = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            response = self.openai.embeddings.create(
                model=self.embedding_model,
                input=batch,
            )
            all_embeddings.extend([d.embedding for d in response.data])

        return all_embeddings

    def _embed_local(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings using local t2v-transformers service."""
        if not texts:
            return []

        all_embeddings = []

        # t2v-transformers only supports single text at a time
        # POST to /vectors with {"text": "..."}
        with httpx.Client(timeout=120.0) as client:
            for text in texts:
                response = client.post(
                    f"{self.settings.local_embedding_url}/vectors",
                    json={"text": text},
                )
                response.raise_for_status()
                result = response.json()

                # Response format: {"text": "...", "vector": [...], "dim": 384}
                if "vector" in result:
                    all_embeddings.append(result["vector"])
                else:
                    raise ValueError(f"Unexpected response format: {result}")

        return all_embeddings

    def embed_text(self, text: str) -> List[float]:
        """Generate embedding for a single text."""
        embeddings = self.embed_texts([text])
        return embeddings[0] if embeddings else []

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts."""
        if self.embedding_provider == "openai":
            return self._embed_openai(texts)
        else:
            return self._embed_local(texts)

    def embed_chunks(self, chunks: List[Chunk]) -> List[str]:
        """Embed chunks and store in Qdrant. Returns point IDs."""
        if not chunks:
            return []

        # Generate embeddings
        texts = [c.content for c in chunks]
        embeddings = self.embed_texts(texts)

        # Create points
        points = []
        point_ids = []

        for chunk, embedding in zip(chunks, embeddings):
            point_id = self._generate_point_id(chunk)
            point_ids.append(point_id)

            # Prepare payload
            payload = {
                "content": chunk.content,
                "token_count": chunk.token_count,
                **chunk.metadata,
            }

            points.append(
                PointStruct(
                    id=point_id,
                    vector=embedding,
                    payload=payload,
                )
            )

        # Upsert to Qdrant (handles re-indexing)
        self.qdrant.upsert(
            collection_name=self.COLLECTION_NAME,
            points=points,
        )

        return point_ids

    def search(
        self,
        query: str,
        project_ids: Optional[List[int]] = None,
        content_types: Optional[List[str]] = None,
        top_k: int = 10,
    ) -> List[Dict[str, Any]]:
        """Search for relevant chunks."""
        # Generate query embedding
        query_embedding = self.embed_text(query)

        # Build filter conditions
        filter_conditions = []

        if project_ids:
            filter_conditions.append(
                FieldCondition(
                    key="project_id",
                    match=MatchAny(any=project_ids),
                )
            )

        if content_types:
            filter_conditions.append(
                FieldCondition(
                    key="type",
                    match=MatchAny(any=content_types),
                )
            )

        query_filter = None
        if filter_conditions:
            query_filter = Filter(must=filter_conditions)

        # Search using query_points (new API in qdrant-client >= 1.9)
        results = self.qdrant.query_points(
            collection_name=self.COLLECTION_NAME,
            query=query_embedding,
            query_filter=query_filter,
            limit=top_k,
            with_payload=True,
        )

        return [
            {
                "id": r.id,
                "score": r.score,
                "content": r.payload.get("content", ""),
                "metadata": {
                    k: v for k, v in r.payload.items() if k not in ["content"]
                },
            }
            for r in results.points
        ]

    def delete_by_project(self, project_id: int) -> None:
        """Delete all vectors for a project."""
        self.qdrant.delete(
            collection_name=self.COLLECTION_NAME,
            points_selector=Filter(
                must=[
                    FieldCondition(
                        key="project_id",
                        match=MatchValue(value=project_id),
                    )
                ]
            ),
        )

    def delete_by_ids(self, point_ids: List[str]) -> None:
        """Delete specific points by ID."""
        if point_ids:
            self.qdrant.delete(
                collection_name=self.COLLECTION_NAME,
                points_selector=point_ids,
            )

    def get_collection_info(self) -> Dict[str, Any]:
        """Get collection statistics."""
        info = self.qdrant.get_collection(self.COLLECTION_NAME)
        return {
            "name": self.COLLECTION_NAME,
            "vectors_count": info.vectors_count,
            "points_count": info.points_count,
            "status": info.status,
        }
