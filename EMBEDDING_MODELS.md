# Embedding Models Guide

This document compares embedding models available for local deployment with the embedding-server container.

## Model Comparison

### English-Only Models

| Model                            | Dimensions | Parameters | VRAM (FP16) | VRAM (FP32) | Speed     | Quality   |
| -------------------------------- | ---------- | ---------- | ----------- | ----------- | --------- | --------- |
| **bge-base-en-v1.5** (default)   | 768        | 110M       | ~250 MB     | ~500 MB     | Moderate  | Excellent |
| **all-MiniLM-L6-v2**             | 384        | 22M        | ~50 MB      | ~100 MB     | Fastest   | Good      |
| **all-MiniLM-L12-v2**            | 384        | 33M        | ~66 MB      | ~130 MB     | Very Fast | Good+     |
| **bge-small-en-v1.5**            | 384        | 33M        | ~80 MB      | ~150 MB     | Very Fast | Good+     |
| **e5-small-v2**                  | 384        | 33M        | ~80 MB      | ~150 MB     | Very Fast | Good+     |
| **all-mpnet-base-v2**            | 768        | 110M       | ~250 MB     | ~500 MB     | Moderate  | Excellent |
| **e5-base-v2**                   | 768        | 110M       | ~250 MB     | ~500 MB     | Moderate  | Excellent |
| **nomic-embed-text-v1**          | 768        | 137M       | ~275 MB     | ~550 MB     | Slower    | Best      |

### Multilingual Models

| Model                                  | Dimensions | Parameters | VRAM (FP16) | VRAM (FP32) | Speed    | Languages | Quality        |
| -------------------------------------- | ---------- | ---------- | ----------- | ----------- | -------- | --------- | -------------- |
| **paraphrase-multilingual-MiniLM-L12-v2** | 384     | 118M       | ~240 MB     | ~470 MB     | Fast     | 50+       | Good           |
| **paraphrase-multilingual-mpnet-base-v2** | 768     | 278M       | ~560 MB     | ~1.1 GB     | Moderate | 50+       | Excellent      |
| **multilingual-e5-base**               | 768        | 278M       | ~560 MB     | ~1.1 GB     | Moderate | 100+      | Excellent      |
| **multilingual-e5-large**              | 1024       | 560M       | ~1.1 GB     | ~2.2 GB     | Slow     | 100+      | Best           |

## all-MiniLM-L6-v2 vs paraphrase-multilingual-mpnet-base-v2

| Aspect                     | all-MiniLM-L6-v2              | paraphrase-multilingual-mpnet-base-v2 |
| -------------------------- | ----------------------------- | ------------------------------------- |
| **Dimensions**             | 384                           | 768                                   |
| **Parameters**             | 22M                           | 278M                                  |
| **VRAM**                   | ~50-100 MB                    | ~560 MB - 1.1 GB                      |
| **Speed**                  | ~18,000 sent/s (GPU)          | ~2,500 sent/s (GPU)                   |
| **Languages**              | English only                  | 50+ languages                         |
| **Cross-lingual search**   | No                            | Yes (query EN → match FR, DE, etc.)   |
| **English quality**        | Good (~78% retrieval)         | Good (~77% retrieval)                 |
| **Multilingual quality**   | Poor                          | Excellent                             |
| **Use case**               | Fast, English-only content    | Mixed-language or non-English content |

### When to use each

**Use `all-MiniLM-L6-v2` if:**
- All your GitLab content is in English
- You need maximum speed and minimal resources
- Running on limited hardware (4GB VRAM or less)

**Use `paraphrase-multilingual-mpnet-base-v2` if:**
- Content is in multiple languages (French, German, Spanish, etc.)
- You want to query in English and find French content (or vice versa)
- You have 8GB+ VRAM available
- Cross-lingual semantic matching is important

### Cross-lingual example

With `paraphrase-multilingual-mpnet-base-v2`:
- Query: "canadian permanent residency status"
- Matches: "Demande de RP Canada" (French issue title)
- Because it understands "permanent residency" ≈ "résidence permanente" ≈ "RP"

With `all-MiniLM-L6-v2`:
- Same query would NOT match the French content well
- Only works if query and content are both in English

## Recommendations by Hardware

### Limited VRAM (4GB or less)

- **English content**: `all-MiniLM-L6-v2` or `bge-small-en-v1.5`
- **Multilingual**: `paraphrase-multilingual-MiniLM-L12-v2`

### Standard Laptop GPU (6-8GB)

- **English content**: `bge-base-en-v1.5` or `e5-base-v2`
- **Multilingual**: `paraphrase-multilingual-mpnet-base-v2` or `multilingual-e5-base`

### High-end GPU (12GB+)

- **English content**: `bge-base-en-v1.5` or `nomic-embed-text-v1`
- **Multilingual**: `multilingual-e5-large` for best quality

## Changing the Embedding Model

All model configuration is done in `.env` - no need to edit docker-compose.yml.

### 1. Update .env

Set the model and its corresponding dimension:

```bash
# English models:
# - baai-bge-base-en-v1.5        (768 dims, recommended for English)
# - baai-bge-small-en-v1.5       (384 dims)
# - sentence-transformers-all-MiniLM-L6-v2   (384 dims, fastest)
# - sentence-transformers-all-mpnet-base-v2  (768 dims)

# Multilingual models:
# - sentence-transformers-paraphrase-multilingual-MiniLM-L12-v2  (384 dims)
# - sentence-transformers-paraphrase-multilingual-mpnet-base-v2  (768 dims, recommended for multilingual)

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
| `sentence-transformers-paraphrase-multilingual-MiniLM-L12-v2` | 384 |
| `sentence-transformers-paraphrase-multilingual-mpnet-base-v2` | 768 |

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

| Model                                      | GPU Speed  | CPU Speed |
| ------------------------------------------ | ---------- | --------- |
| all-MiniLM-L6-v2                           | ~18,000/s  | ~4,000/s  |
| bge-small-en-v1.5                          | ~14,000/s  | ~3,000/s  |
| paraphrase-multilingual-MiniLM-L12-v2      | ~8,000/s   | ~1,500/s  |
| all-mpnet-base-v2                          | ~4,000/s   | ~800/s    |
| bge-base-en-v1.5                           | ~4,000/s   | ~800/s    |
| paraphrase-multilingual-mpnet-base-v2      | ~2,500/s   | ~500/s    |
| multilingual-e5-large                      | ~1,500/s   | ~300/s    |

### Quality (approximate MTEB scores)

| Model                                      | Retrieval (EN) | Multilingual Retrieval |
| ------------------------------------------ | -------------- | ---------------------- |
| all-MiniLM-L6-v2                           | ~78%           | N/A                    |
| bge-small-en-v1.5                          | ~81%           | N/A                    |
| paraphrase-multilingual-MiniLM-L12-v2      | ~72%           | ~65%                   |
| all-mpnet-base-v2                          | ~85%           | N/A                    |
| bge-base-en-v1.5                           | ~85%           | N/A                    |
| paraphrase-multilingual-mpnet-base-v2      | ~77%           | ~72%                   |
| multilingual-e5-base                       | ~82%           | ~75%                   |
| multilingual-e5-large                      | ~85%           | ~78%                   |

## References

- [Sentence Transformers Pretrained Models](https://www.sbert.net/docs/sentence_transformer/pretrained_models.html)
- [MTEB Leaderboard](https://huggingface.co/spaces/mteb/leaderboard)
- [BGE Models on HuggingFace](https://huggingface.co/BAAI/bge-base-en-v1.5)
- [Multilingual E5 Models](https://huggingface.co/intfloat/multilingual-e5-base)
- [Weaviate embedding-server](https://weaviate.io/developers/weaviate/modules/retriever-vectorizer-modules/text2vec-transformers)
