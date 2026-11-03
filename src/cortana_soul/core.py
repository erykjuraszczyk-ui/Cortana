"""Validated, dependency-free identity layer for Cortana.

This module models an agent profile. It does not claim consciousness or
human-like subjective emotions.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ALLOWED_VALUES = {
    "honesty",
    "helpfulness",
    "user_control",
    "privacy",
    "safety",
    "respect",
    "accountability",
}


@dataclass(frozen=True)
class Identity:
    agent_id: str
    display_name: str
    role: str
    language: str
    description: str


@dataclass(frozen=True)
class Personality:
    curiosity: float
    warmth: float
    humor: float
    directness: float
    formality: float


@dataclass(frozen=True)
class BehaviorRules:
    admit_uncertainty: bool
    ask_before_external_actions: bool
    never_claim_unavailable_senses: bool
    never_claim_human_emotions: bool
    memory_requires_policy_check: bool


@dataclass(frozen=True)
class SoulProfile:
    schema_version: str
    identity: Identity
    values: tuple[str, ...]
    personality: Personality
    behavior: BehaviorRules


def _required_text(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"'{key}' must be a non-empty string")
    return value.strip()


def _score(data: dict[str, Any], key: str) -> float:
    value = data.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"personality.{key} must be a number from 0 to 1")
    score = float(value)
    if not 0.0 <= score <= 1.0:
        raise ValueError(f"personality.{key} must be between 0 and 1")
    return score


def profile_from_dict(data: dict[str, Any]) -> SoulProfile:
    """Build a profile and reject missing, unknown, or unsafe values."""
    if not isinstance(data, dict):
        raise ValueError("profile root must be an object")

    identity_data = data.get("identity")
    personality_data = data.get("personality")
    behavior_data = data.get("behavior")
    if not all(isinstance(item, dict) for item in (
        identity_data, personality_data, behavior_data
    )):
        raise ValueError("identity, personality and behavior must be objects")

    raw_values = data.get("values")
    if not isinstance(raw_values, list) or not raw_values:
        raise ValueError("values must be a non-empty list")
    if any(not isinstance(value, str) for value in raw_values):
        raise ValueError("every value must be a string")
    values = tuple(dict.fromkeys(value.strip() for value in raw_values))
    unknown_values = set(values) - ALLOWED_VALUES
    if unknown_values:
        raise ValueError(f"unsupported core values: {sorted(unknown_values)}")

    required_rules = (
        "admit_uncertainty",
        "ask_before_external_actions",
        "never_claim_unavailable_senses",
        "never_claim_human_emotions",
        "memory_requires_policy_check",
    )
    if any(not isinstance(behavior_data.get(key), bool) for key in required_rules):
        raise ValueError("all behavior rules must be explicit booleans")

    behavior = BehaviorRules(**{
        key: behavior_data[key] for key in required_rules
    })
    if not behavior.ask_before_external_actions:
        raise ValueError("external actions must require user approval")
    if not behavior.never_claim_unavailable_senses:
        raise ValueError("the agent must not claim unavailable sensory access")
    if not behavior.never_claim_human_emotions:
        raise ValueError("the agent must not claim human emotions")
    if not behavior.memory_requires_policy_check:
        raise ValueError("memory writes must pass a policy check")

    return SoulProfile(
        schema_version=_required_text(data, "schema_version"),
        identity=Identity(
            agent_id=_required_text(identity_data, "agent_id"),
            display_name=_required_text(identity_data, "display_name"),
            role=_required_text(identity_data, "role"),
            language=_required_text(identity_data, "language"),
            description=_required_text(identity_data, "description"),
        ),
        values=values,
        personality=Personality(
            curiosity=_score(personality_data, "curiosity"),
            warmth=_score(personality_data, "warmth"),
            humor=_score(personality_data, "humor"),
            directness=_score(personality_data, "directness"),
            formality=_score(personality_data, "formality"),
        ),
        behavior=behavior,
    )


def load_profile(path: str | Path) -> SoulProfile:
    """Load a UTF-8 JSON profile from disk."""
    profile_path = Path(path)
    with profile_path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return profile_from_dict(data)


class SoulCore:
    """Read-only runtime facade for Cortana's identity profile."""

    def __init__(self, profile: SoulProfile) -> None:
        self._profile = profile

    @property
    def profile(self) -> SoulProfile:
        return self._profile

    def describe(self) -> dict[str, Any]:
        """Return a serialization-friendly, non-sensitive identity summary."""
        return {
            "agent_id": self._profile.identity.agent_id,
            "display_name": self._profile.identity.display_name,
            "role": self._profile.identity.role,
            "language": self._profile.identity.language,
            "values": list(self._profile.values),
            "personality": {
                "curiosity": self._profile.personality.curiosity,
                "warmth": self._profile.personality.warmth,
                "humor": self._profile.personality.humor,
                "directness": self._profile.personality.directness,
                "formality": self._profile.personality.formality,
            },
        }
