"""Explicit, short-lived interaction context with no hidden user profiling."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Urgency = Literal["low", "normal", "high"]
Tone = Literal["neutral", "concise", "detailed", "supportive", "formal", "playful"]


@dataclass(frozen=True)
class ContextFrame:
    task: str
    language: str = "pl-PL"
    urgency: Urgency = "normal"
    requested_tone: Tone = "neutral"
    source: str = "conversation"
    requires_confirmation: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.task, str) or not self.task.strip():
            raise ValueError("task must be a non-empty string")
        if self.urgency not in {"low", "normal", "high"}:
            raise ValueError("unsupported urgency")
        if self.requested_tone not in {
            "neutral", "concise", "detailed", "supportive", "formal", "playful"
        }:
            raise ValueError("unsupported requested tone")
        if self.source not in {"conversation", "user_feedback", "system"}:
            raise ValueError("unsupported context source")
        if not isinstance(self.requires_confirmation, bool):
            raise ValueError("requires_confirmation must be boolean")


class ContextResolver:
    """Builds a context frame only from explicitly supplied turn metadata."""

    def resolve(
        self, *, task: str, language: str = "pl-PL",
        urgency: Urgency = "normal", requested_tone: Tone = "neutral",
        source: str = "conversation", requires_confirmation: bool = False,
    ) -> ContextFrame:
        return ContextFrame(
            task=task.strip() if isinstance(task, str) else task,
            language=language,
            urgency=urgency,
            requested_tone=requested_tone,
            source=source,
            requires_confirmation=requires_confirmation,
        )
