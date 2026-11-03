"""Cortana Soul Core: identity, persistence, affect, context and memory."""

from .affect import AffectEngine, AffectState
from .context import ContextFrame, ContextResolver
from .core import SoulCore, SoulProfile, load_profile
from .embeddings import LocalSentenceTransformer
from .memory import EpisodicMemoryStore, MemoryEvent, MemorySummary
from .memory_reflection import MemoryAwareReflectionEngine, MemoryReflectionProposal
from .memory_integration import (MemoryEvent, MemoryEventBus, MemoryIntegrationService, MemoryRecoveryEngine, MemoryConsistencyGuard, OutboxStats, RetryManager, TransactionalOutbox)
from .persistence import SoulProfileStore
from .persistent_memory import HybridReranker, IndexHealth, MemoryIndexSynchronizer, PersistentBM25Index
from .qdrant_store import QdrantSemanticMemoryStore
from .reflection import ReflectionEngine, ReflectionInput, ReflectionProposal
from .retrieval import BM25Index, HybridRetriever, LexicalSearchResult, tokenize
from .semantic import (
    ContextItem, EmbeddingProvider, LongTermContextAssembler,
    RetrievedContext, SemanticMemoryRecord, SemanticMemoryStore,
    SemanticSearchResult, split_into_chunks,
)

__all__ = [
    "AffectEngine", "AffectState", "BM25Index", "PersistentBM25Index", "MemoryIndexSynchronizer", "HybridReranker", "IndexHealth", "ContextFrame", "ContextResolver",
    "ContextItem", "EmbeddingProvider", "EpisodicMemoryStore",
    "LongTermContextAssembler", "MemoryEvent", "MemorySummary",
    "MemoryAwareReflectionEngine", "MemoryReflectionProposal", "MemoryIntegrationService", "MemoryEventBus", "MemoryEvent", "TransactionalOutbox", "RetryManager", "MemoryConsistencyGuard", "MemoryRecoveryEngine", "OutboxStats",
    "RetrievedContext", "LocalSentenceTransformer", "QdrantSemanticMemoryStore",
    "HybridRetriever", "LexicalSearchResult", "tokenize",
    "SemanticMemoryRecord", "SemanticMemoryStore", "SemanticSearchResult",
    "ReflectionEngine", "ReflectionInput", "ReflectionProposal",
    "SoulCore", "SoulProfile", "SoulProfileStore", "load_profile",
    "split_into_chunks",
]
