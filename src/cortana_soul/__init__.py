"""Cortana Soul Core: identity, persistence, affect, context and memory-aware reflection."""

from .affect import AffectEngine, AffectState
from .context import ContextFrame, ContextResolver
from .core import SoulCore, SoulProfile, load_profile
from .memory import EpisodicMemoryStore, MemoryEvent, MemorySummary
from .memory_reflection import MemoryAwareReflectionEngine, MemoryReflectionProposal
from .persistence import SoulProfileStore
from .reflection import ReflectionEngine, ReflectionInput, ReflectionProposal

__all__ = [
    "AffectEngine", "AffectState", "ContextFrame", "ContextResolver",
    "EpisodicMemoryStore", "MemoryEvent", "MemorySummary",
    "MemoryAwareReflectionEngine", "MemoryReflectionProposal",
    "ReflectionEngine", "ReflectionInput", "ReflectionProposal",
    "SoulCore", "SoulProfile", "SoulProfileStore", "load_profile",
]
