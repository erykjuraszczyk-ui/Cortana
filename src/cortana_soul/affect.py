"""Bounded computational affect state; not a model of human feelings."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from math import isfinite
from typing import Mapping

AFFECT_DIMENSIONS = frozenset({"valence", "arousal", "confidence", "uncertainty"})
DEFAULTS = {"valence": 0.0, "arousal": 0.25, "confidence": 0.5, "uncertainty": 0.5}


@dataclass(frozen=True)
class AffectState:
    """Numerical interaction-state estimate in the inclusive range [-1, 1] or [0, 1]."""
    valence: float = 0.0
    arousal: float = 0.25
    confidence: float = 0.5
    uncertainty: float = 0.5
    updated_at: str = ""

    def __post_init__(self) -> None:
        if not -1.0 <= self.valence <= 1.0:
            raise ValueError("valence must be between -1 and 1")
        for name in ("arousal", "confidence", "uncertainty"):
            value = getattr(self, name)
            if not isfinite(value) or not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be finite and between 0 and 1")


class AffectEngine:
    """Updates a transient state from explicit, bounded signals."""

    def __init__(self, initial: AffectState | None = None, *, smoothing: float = 0.25):
        if isinstance(smoothing, bool) or not 0.0 < smoothing <= 1.0:
            raise ValueError("smoothing must be in (0, 1]")
        self._state = initial or AffectState()
        self._smoothing = smoothing

    @property
    def state(self) -> AffectState:
        return self._state

    def update(self, signals: Mapping[str, float]) -> AffectState:
        if not isinstance(signals, Mapping) or not signals:
            raise ValueError("signals must be a non-empty mapping")
        unknown = set(signals) - AFFECT_DIMENSIONS
        if unknown:
            raise ValueError(f"unsupported affect dimensions: {sorted(unknown)}")
        current = {
            "valence": self._state.valence,
            "arousal": self._state.arousal,
            "confidence": self._state.confidence,
            "uncertainty": self._state.uncertainty,
        }
        for key, raw in signals.items():
            if isinstance(raw, bool) or not isinstance(raw, (int, float)):
                raise ValueError(f"{key} must be numeric")
            value = float(raw)
            low = -1.0 if key == "valence" else 0.0
            if not isfinite(value) or not low <= value <= 1.0:
                raise ValueError(f"{key} is outside its permitted range")
            current[key] += self._smoothing * (value - current[key])
        self._state = AffectState(**current, updated_at=datetime.now(timezone.utc).isoformat())
        return self._state
