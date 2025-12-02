# Embedding Models Guide

This document compares embedding models available for local deployment with the embedding-server container.

## Model Comparison

| Model                            | Dimensions | Parameters | VRAM (FP16) | VRAM (FP32) | Speed     | Quality   |
| -------------------------------- | ---------- | ---------- | ----------- | ----------- | --------- | --------- |
| **bge-base-en-v1.5** (default)   | 768        | 110M       | ~250 MB     | ~500 MB     | Moderate  | Excellent |
| **all-MiniLM-L6-v2**             | 384        | 22M        | ~50 MB      | ~100 MB     | Fastest   | Good      |
| **all-MiniLM-L12-v2**          | 384        | 33M        | ~66 MB      | ~130 MB     | Very Fast | Good+     |
| **bge-small-en-v1.5**          | 384        | 33M        | ~80 MB      | ~150 MB     | Very Fast | Good+     |
| **e5-small-v2**                | 384        | 33M        | ~80 MB      | ~150 MB     | Very Fast | Good+     |
| **all-mpnet-base-v2**            | 768        | 110M       | ~250 MB     | ~500 MB     | Moderate  | Excellent |
| **e5-base-v2**                 | 768        | 110M       | ~250 MB     | ~500 MB     | Moderate  | Excellent |
| **nomic-embed-text-v1**        | 768        | 137M       | ~275 MB     | ~550 MB     | Slower    | Best      |

## Recommendations by Hardware

### Limited VRAM (4GB or less)

- **Recommended**: `all-MiniLM-L6-v2` or `bge-small-en-v1.5`
- These models use minimal memory and are very fast

### Standard Laptop GPU (6-8GB)

- **Recommended**: `bge-base-en-v1.5` or `e5-base-v2`
- Best quality/speed tradeoff for most use cases

### High-end GPU (12GB+)

- **Recommended**: Any model, consider `bge-base-en-v1.5` or `nomic-embed-text-v1`
- Can use larger batch sizes for faster indexing

## Changing the Embedding Model

All model configuration is done in `.env` - no need to edit docker-compose.yml.

### 1. Update .env

Set the model and its corresponding dimension:

```bash
# Available models (image tags):
# - baai-bge-base-en-v1.5        (768 dims, recommended)
# - baai-bge-small-en-v1.5       (384 dims)
# - sentence-transformers-all-MiniLM-L6-v2   (384 dims, fastest)
# - sentence-transformers-all-mpnet-base-v2  (768 dims)

LOCAL_EMBEDDING_MODEL=baai-bge-base-en-v1.5
LOCAL_EMBEDDING_DIMENSION=768
```

### 2. Dimension Reference

| Model Tag | Dimension |
|-----------|-----------|
| `baai-bge-base-en-v1.5` | 768 |
| `baai-bge-small-en-v1.5` | 384 |
| `sentence-transformers-all-MiniLM-L6-v2` | 384 |
| `sentence-transformers-all-MiniLM-L12-v2` | 384 |
| `sentence-transformers-all-mpnet-base-v2` | 768 |

### 3. Re-index All Projects

**Important**: Embeddings from different models are incompatible. After changing models:

1. Clear the Qdrant collection (or delete the volume)
2. Re-index all projects from the UI

```bash
# Option 1: Clear via UI
# Go to Projects page and click "Clear" on each indexed project

# Option 2: Reset Qdrant volume (removes all vectors)
docker compose down
docker volume rm gitlab-chat-community_qdrant_data
docker compose up -d
```

## Performance Benchmarks

### Speed (sentences/second on GPU)

| Model             | GPU Speed | CPU Speed |
| ----------------- | --------- | --------- |
| all-MiniLM-L6-v2  | ~18,000/s | ~4,000/s  |
| bge-small-en-v1.5 | ~14,000/s | ~3,000/s  |
| all-mpnet-base-v2 | ~4,000/s  | ~800/s    |
| bge-base-en-v1.5  | ~4,000/s  | ~800/s    |

### Quality (approximate MTEB scores)

| Model             | Retrieval | Semantic Similarity |
| ----------------- | --------- | ------------------- |
| all-MiniLM-L6-v2  | ~78%      | ~84%                |
| bge-small-en-v1.5 | ~81%      | ~85%                |
| all-mpnet-base-v2 | ~85%      | ~87%                |
| bge-base-en-v1.5  | ~85%      | ~86%                |
| e5-base-v2        | ~84%      | ~86%                |

## References

- [Sentence Transformers Pretrained Models](https://www.sbert.net/docs/sentence_transformer/pretrained_models.html)
- [MTEB Leaderboard](https://huggingface.co/spaces/mteb/leaderboard)
- [BGE Models on HuggingFace](https://huggingface.co/BAAI/bge-base-en-v1.5)
- [Weaviate embedding-server](https://weaviate.io/developers/weaviate/modules/retriever-vectorizer-modules/text2vec-transformers)
