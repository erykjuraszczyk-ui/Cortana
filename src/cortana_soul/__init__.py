"""Cortana Soul Core: identity, persistence, affect, context and memory."""

from .affect import AffectEngine, AffectState
from .context import ContextFrame, ContextResolver
from .core import SoulCore, SoulProfile, load_profile
from .memory import EpisodicMemoryStore, MemoryEvent, MemorySummary
from .memory_reflection import MemoryAwareReflectionEngine, MemoryReflectionProposal
from .persistence import SoulProfileStore
from .reflection import ReflectionEngine, ReflectionInput, ReflectionProposal
from .semantic import (
    ContextItem, EmbeddingProvider, LongTermContextAssembler,
    RetrievedContext, SemanticMemoryRecord, SemanticMemoryStore,
    SemanticSearchResult, split_into_chunks,
)

__all__ = [
    "AffectEngine", "AffectState", "ContextFrame", "ContextResolver",
    "ContextItem", "EmbeddingProvider", "EpisodicMemoryStore",
    "LongTermContextAssembler", "MemoryEvent", "MemorySummary",
    "MemoryAwareReflectionEngine", "MemoryReflectionProposal",
    "RetrievedContext", "SemanticMemoryRecord", "SemanticMemoryStore",
    "SemanticSearchResult", "ReflectionEngine", "ReflectionInput",
    "ReflectionProposal", "SoulCore", "SoulProfile", "SoulProfileStore",
    "load_profile", "split_into_chunks",
]
