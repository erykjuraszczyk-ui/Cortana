# CORTANA SOUL CORE v1.5.0

**Release:** Semantic Memory, Knowledge Retrieval & Long-Term Context Integration  
**Branch:** `feature/soul-core-v1.5.0`  
**Runtime:** Python 3.11+ standard library

## Objective

Add an opt-in semantic knowledge store and bounded retrieval pipeline. Unlike
v1.4 episodic feedback records, semantic memory stores user-approved knowledge
snippets intended for later retrieval. It does not automatically ingest chat
transcripts or profile the user.

## Architecture

```text
Explicitly approved knowledge
        |
        v
Chunking -> EmbeddingProvider -> SQLite semantic store
                                      |
Current query -> EmbeddingProvider -> Vector similarity search
                                      |
                                      v
                           LongTermContextAssembler
                                      |
                                      v
                        Source-attributed bounded context
                                      |
                                      v
                         Existing reflection / agent layer
```

## Components

- `EmbeddingProvider`: protocol for local or remote embedding model adapters.
  The core does not download or select a model implicitly.
- `SemanticMemoryStore`: stores chunk text, source label, timestamps and
  embedding vectors in SQLite.
- `split_into_chunks`: deterministic bounded chunking with overlap.
- `LongTermContextAssembler`: selects unique results within a character budget
  and preserves source identifiers for traceability.

## Privacy and control

- Every ingestion call requires explicit `consent=True`.
- No automatic ingestion of conversation history.
- Source labels and knowledge text should be reviewed before persistence.
- Individual documents can be deleted with confirmation; full clear also
  requires confirmation.
- The integrating application must provide the real consent and deletion UI,
  OS-level database protection, and any retention policy required by deployment.
- Do not store passwords, authentication tokens, payment credentials, or other
  secrets in semantic memory.

## Embedding integration

The core accepts any provider implementing:

```python
class EmbeddingProvider(Protocol):
    @property
    def dimension(self) -> int: ...
    def embed(self, text: str) -> Sequence[float]: ...
```

A production integration should use the same model and vector dimension for
indexing and querying. Changing embedding models requires rebuilding stored
vectors; mixing incompatible vector spaces is rejected by dimension validation.

No built-in fake embedding model is presented as production semantic search.
Tests use a deterministic stub solely to verify ranking and data flow.

## Example

```python
from cortana_soul.semantic import SemanticMemoryStore, LongTermContextAssembler

# embedder is an application-provided local model adapter
store = SemanticMemoryStore("data/cortana-semantic.sqlite3", embedder)
document_id = store.ingest(
    approved_knowledge_text,
    source="project-notes",
    consent=True,  # only after explicit user approval
)
results = store.search("What did the project specify about memory?", top_k=5)
context = LongTermContextAssembler(max_characters=4000).assemble(
    "What did the project specify about memory?", results
)
```

## Tests

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

Windows PowerShell:

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -v
```

## Scope and limitations

This release supplies the storage, retrieval contract, cosine ranking and
context assembly. It does not yet include a concrete production embedding
model, automatic document ingestion pipeline, reranker, hybrid BM25/vector
search, or external vector database. Those should be separate, measurable
integrations. This memory architecture is software retrieval, not evidence of
human-like understanding or consciousness.
