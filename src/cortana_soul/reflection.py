"""Rule-based reflection proposals; never self-apply profile changes."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .affect import AffectState
from .context import ContextFrame

Outcome = Literal["completed", "partial", "blocked", "unknown"]


@dataclass(frozen=True)
class ReflectionInput:
    context: ContextFrame
    outcome: Outcome
    user_feedback: Literal["positive", "negative", "mixed", "none"] = "none"
    confidence: float = 0.5
    unresolved_questions: int = 0

    def __post_init__(self) -> None:
        if self.outcome not in {"completed", "partial", "blocked", "unknown"}:
            raise ValueError("unsupported outcome")
        if self.user_feedback not in {"positive", "negative", "mixed", "none"}:
            raise ValueError("unsupported feedback")
        if isinstance(self.confidence, bool) or not isinstance(self.confidence, (int, float)):
            raise ValueError("confidence must be numeric")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")
        if isinstance(self.unresolved_questions, bool) or not isinstance(self.unresolved_questions, int) or self.unresolved_questions < 0:
            raise ValueError("unresolved_questions must be a non-negative integer")


@dataclass(frozen=True)
class ReflectionProposal:
    summary: str
    recommendation: str
    suggested_style_field: str | None
    suggested_delta: float
    requires_user_approval: bool = True
    auto_applied: bool = False


class ReflectionEngine:
    """Produces explainable recommendations from a single interaction outcome."""

    def reflect(self, event: ReflectionInput, affect: AffectState) -> ReflectionProposal:
        if event.user_feedback == "negative":
            return ReflectionProposal(
                summary="User feedback indicates the response may not have met expectations.",
                recommendation="Ask what should change before adapting the communication style.",
                suggested_style_field=None, suggested_delta=0.0,
            )
        if event.outcome in {"partial", "blocked"} or event.unresolved_questions:
            return ReflectionProposal(
                summary="The task remains incomplete or has unresolved questions.",
                recommendation="Clarify the missing information and state limitations explicitly.",
                suggested_style_field=None, suggested_delta=0.0,
            )
        if event.user_feedback == "positive" and event.outcome == "completed":
            return ReflectionProposal(
                summary="The user explicitly rated the completed interaction positively.",
                recommendation="Keep the current approach; do not infer a permanent preference from one event.",
                suggested_style_field=None, suggested_delta=0.0,
            )
        if event.confidence < 0.4 or affect.uncertainty > 0.7:
            return ReflectionProposal(
                summary="The available evidence is uncertain.",
                recommendation="Verify assumptions or ask a clarifying question.",
                suggested_style_field=None, suggested_delta=0.0,
            )
        return ReflectionProposal(
            summary="No actionable adaptation signal was identified.",
            recommendation="Retain the current profile and gather more explicit feedback.",
            suggested_style_field=None, suggested_delta=0.0,
        )
