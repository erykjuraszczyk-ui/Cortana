"""Memory-aware, explainable reflection with conservative evidence thresholds."""
from __future__ import annotations

from dataclasses import dataclass

from .affect import AffectState
from .memory import MemorySummary
from .reflection import ReflectionEngine, ReflectionInput, ReflectionProposal


@dataclass(frozen=True)
class MemoryReflectionProposal:
    base: ReflectionProposal
    memory_pattern: str
    evidence_count: int
    recommendation: str
    requires_user_approval: bool = True
    auto_applied: bool = False


class MemoryAwareReflectionEngine:
    """Uses aggregated, consented feedback; never changes profile or memory."""

    def __init__(self, *, minimum_feedback_events: int = 3) -> None:
        if isinstance(minimum_feedback_events, bool) or not isinstance(minimum_feedback_events, int) or minimum_feedback_events < 3:
            raise ValueError("minimum_feedback_events must be an integer >= 3")
        self.minimum_feedback_events = minimum_feedback_events
        self._base = ReflectionEngine()

    def reflect(
        self, event: ReflectionInput, affect: AffectState, memory: MemorySummary
    ) -> MemoryReflectionProposal:
        base = self._base.reflect(event, affect)
        if memory.feedback_count < self.minimum_feedback_events:
            return MemoryReflectionProposal(
                base=base,
                memory_pattern="insufficient_evidence",
                evidence_count=memory.feedback_count,
                recommendation=base.recommendation + " Memory evidence is below the minimum threshold.",
            )

        positive_ratio = memory.positive_count / memory.feedback_count
        negative_ratio = memory.negative_count / memory.feedback_count
        if positive_ratio >= 0.8:
            pattern = "repeated_positive_feedback"
            recommendation = (
                "Several explicit feedback events are positive. Ask the user whether "
                "this communication approach should be saved as a preference; do not "
                "change the profile without approval."
            )
        elif negative_ratio >= 0.6:
            pattern = "repeated_negative_feedback"
            recommendation = (
                "Repeated explicit feedback indicates this approach may not fit. "
                "Ask what should change; do not infer a replacement preference."
            )
        else:
            pattern = "mixed_or_no_stable_pattern"
            recommendation = (
                "The stored feedback does not show a stable preference. Keep the "
                "current profile and request explicit feedback when useful."
            )
        return MemoryReflectionProposal(
            base=base,
            memory_pattern=pattern,
            evidence_count=memory.feedback_count,
            recommendation=recommendation,
        )
