"""Cortana Soul Core: identity, persistence, affect, context and reflection."""

from .affect import AffectEngine, AffectState
from .context import ContextFrame, ContextResolver
from .core import SoulCore, SoulProfile, load_profile
from .persistence import SoulProfileStore
from .reflection import ReflectionEngine, ReflectionInput, ReflectionProposal

__all__ = [
    "AffectEngine", "AffectState", "ContextFrame", "ContextResolver",
    "ReflectionEngine", "ReflectionInput", "ReflectionProposal",
    "SoulCore", "SoulProfile", "SoulProfileStore", "load_profile",
]
