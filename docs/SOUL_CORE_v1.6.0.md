# CORTANA SOUL CORE v1.6.0

**Release:** Local Embedding Runtime, Qdrant Vector Database & Hybrid Retrieval Engine  
**Runtime:** Python 3.11+; core retrieval remains standard-library only  
**Platforms:** Windows and Linux

## Architecture

```text
Approved knowledge (explicit consent)
             |
       Chunking (v1.5)
             |
     Local embedding adapter
             |
      +------+----------------+
      |                       |
 SQLite semantic store   Qdrant adapter (optional)
      |                       |
      +-----------+-----------+
                  |
        Vector similarity results
                  |
       BM25 lexical candidate index
                  |
       Hybrid weighted rank fusion
                  |
      Bounded, source-attributed context
                  |
          Cortana agent layer
```

## Components

- `LocalSentenceTransformer`: optional adapter for local Sentence Transformers models. Default model: `sentence-transformers/all-MiniLM-L6-v2`; CPU is the default device. Set `local_files_only=True` to require a cached model and prevent model downloads during initialization.
- `QdrantSemanticMemoryStore`: optional Qdrant adapter. It accepts an injected Qdrant client or can create a local embedded client using `QdrantSemanticMemoryStore.local(path, embedder)`.
- `BM25Index`: dependency-free in-process BM25 lexical index. Rebuild it from approved records at startup; update it when records are added or deleted.
- `HybridRetriever`: combines semantic cosine similarity and normalized BM25 scores. Default weights are 0.65 semantic / 0.35 lexical and are normalized automatically.
- Existing `SemanticMemoryStore`: SQLite fallback remains supported.

## Optional dependencies

Install only the adapter you intend to use:

```bash
python -m pip install sentence-transformers
python -m pip install qdrant-client
```

For a local model already cached:

```python
embedder = LocalSentenceTransformer(local_files_only=True)
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

For hybrid retrieval, create or rebuild a lexical index from the same approved records. The index is deliberately separate from storage so deployments can choose a persistence/rebuild strategy:

```python
from cortana_soul import BM25Index, HybridRetriever

lexical = BM25Index()
lexical.add(approved_records)
retriever = HybridRetriever(store.search, lexical)
results = retriever.search("Qdrant vector memory", top_k=5)
```

## Privacy and operational controls

- Ingestion still requires explicit `consent=True`.
- No automatic chat transcript ingestion is introduced.
- Document deletion requires `confirmed=True`.
- Qdrant payloads contain approved chunk text, source label, document ID and timestamp only.
- Keep local database directories access-controlled and encrypted at the OS or volume layer where appropriate.
- The application must synchronize lexical-index updates with document ingestion/deletion. Rebuild the BM25 index from approved records after restart.
- Use one embedding model and dimension per collection. Model changes require re-embedding and rebuilding the collection.
- Do not put secrets, credentials, or payment data into semantic memory.

## Tests

The CI suite uses fake embedding providers and standard-library tests. It does not download ML models, start Qdrant, or require network access.

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

## Limitations

- Sentence Transformers and Qdrant are optional runtime integrations; CI tests their dependency-free contracts rather than launching heavyweight services.
- The BM25 index is in-memory and must be rebuilt from approved records at startup.
- Hybrid scores are ranking signals, not calibrated probabilities.
- Qdrant's delete API does not report an exact affected-point count through this adapter.
- This is controlled software retrieval, not human-like memory or consciousness.
