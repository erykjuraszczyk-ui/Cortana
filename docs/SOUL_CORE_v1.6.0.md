# CORTANA SOUL CORE v1.6.0

**Release:** Local Embedding Runtime, Qdrant Vector Database & Hybrid Retrieval Engine  
**Python:** 3.11+  
**Platforms:** Windows and Linux  
**Core dependencies:** Python standard library only

## Scope

v1.6.0 adds optional local embedding inference, an optional local Qdrant vector-store adapter, and dependency-free BM25 + hybrid ranking. The existing SQLite semantic store remains available as a lightweight fallback.

## Architecture

```text
Approved knowledge (explicit consent)
              |
          Chunking
              |
    Local embedding runtime
              |
       +------+-------+
       |              |
   SQLite store    Qdrant store
       |              |
       +------+-------+
              |
      Vector similarity
              |
        BM25 lexical index
              |
     Weighted hybrid fusion
              |
   Bounded, source-attributed context
              |
         Cortana Agent
```

## Components

- `LocalSentenceTransformer`: optional local adapter for Sentence Transformers. Default model is `sentence-transformers/all-MiniLM-L6-v2`; CPU is the default device. `local_files_only=True` requires a cached model.
- `QdrantSemanticMemoryStore`: optional Qdrant adapter. Accepts an injected client or creates an embedded local database with `QdrantSemanticMemoryStore.local(path, embedder)`. Existing collection dimensions are checked against the model.
- `BM25Index`: dependency-free lexical search index. Rebuild it from approved records after startup; update it after ingestion and deletion.
- `HybridRetriever`: combines semantic cosine similarity and normalized BM25 relevance. Default weights: 0.65 semantic / 0.35 lexical. Weights are normalized automatically.
- `SemanticMemoryStore`: existing SQLite fallback remains supported.

## Optional installation

Install only the components you intend to use:

```bash
python -m pip install sentence-transformers
python -m pip install qdrant-client
```

For an already cached local model:

```python
from cortana_soul import LocalSentenceTransformer

embedder = LocalSentenceTransformer(local_files_only=True, device="cpu")
```

For a local Qdrant database:

```python
from cortana_soul import LocalSentenceTransformer, QdrantSemanticMemoryStore

embedder = LocalSentenceTransformer(device="cpu")
store = QdrantSemanticMemoryStore.local("data/qdrant", embedder)
document_id = store.ingest(
    approved_text, source="project-notes", consent=True
)
results = store.search("What is the vector memory architecture?", top_k=5)
```

Hybrid retrieval:

```python
from cortana_soul import BM25Index, HybridRetriever

# approved_records must be records loaded from the same consented store.
lexical = BM25Index()
lexical.add(approved_records)
retriever = HybridRetriever(store.search, lexical)
results = retriever.search("Qdrant vector memory", top_k=5)
```

## Privacy and lifecycle

- Ingestion requires explicit `consent=True`.
- No automatic chat transcript ingestion is introduced.
- Deletion requires explicit confirmation through the store API.
- Qdrant payloads contain approved chunk text, source label, document ID, timestamp and model label only.
- The application must synchronize BM25 index updates with ingestion/deletion and rebuild the index from approved records after restart.
- Use one embedding model and vector dimension per Qdrant collection. Changing models requires re-embedding and rebuilding the collection.
- Protect local database directories with operating-system permissions and volume encryption where appropriate.
- Do not store credentials, secrets or payment information in semantic memory.

## Testing

CI uses deterministic fake embedding providers and standard-library tests. It does not download models, start Qdrant or require network access.

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

## Limitations

- Sentence Transformers and Qdrant are optional runtime integrations; their heavyweight runtimes are not started in CI.
- BM25 is an in-memory index and must be rebuilt after restart.
- Hybrid scores are ranking signals, not calibrated probabilities.
- Qdrant's delete API does not expose an exact affected-point count through this adapter.
- This is a controlled software retrieval system, not human-like memory or consciousness.
