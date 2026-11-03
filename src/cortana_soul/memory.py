"""Consent-based episodic memory for bounded reflection.

Only structured interaction outcomes and explicit feedback are stored. Raw
messages, sensitive traits, and inferred psychological attributes are not.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path


OUTCOMES = frozenset({"completed", "partial", "blocked", "unknown"})
FEEDBACK = frozenset({"positive", "negative", "mixed", "none"})
TONES = frozenset({"neutral", "concise", "detailed", "supportive", "formal", "playful"})


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("created_at must include a timezone")
    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True)
class MemoryEvent:
    outcome: str
    user_feedback: str = "none"
    requested_tone: str = "neutral"
    confidence: float = 0.5
    unresolved_questions: int = 0
    created_at: str = ""

    def __post_init__(self) -> None:
        if self.outcome not in OUTCOMES:
            raise ValueError("unsupported outcome")
        if self.user_feedback not in FEEDBACK:
            raise ValueError("unsupported feedback")
        if self.requested_tone not in TONES:
            raise ValueError("unsupported requested tone")
        if isinstance(self.confidence, bool) or not isinstance(self.confidence, (int, float)) or not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")
        if isinstance(self.unresolved_questions, bool) or not isinstance(self.unresolved_questions, int) or self.unresolved_questions < 0:
            raise ValueError("unresolved_questions must be a non-negative integer")
        if self.created_at:
            _parse_timestamp(self.created_at)


@dataclass(frozen=True)
class MemorySummary:
    event_count: int
    feedback_count: int
    positive_count: int
    negative_count: int
    mixed_count: int
    completed_count: int
    window_days: int
    requested_tone: str | None = None


class EpisodicMemoryStore:
    """SQLite store. Writes require explicit per-call consent."""

    def __init__(self, database: str | Path, *, retention_days: int = 90) -> None:
        if isinstance(retention_days, bool) or not isinstance(retention_days, int) or not 1 <= retention_days <= 3650:
            raise ValueError("retention_days must be from 1 to 3650")
        self.database = str(database)
        self.retention_days = retention_days
        if self.database != ":memory:":
            Path(self.database).parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.database, timeout=10)
        db.row_factory = sqlite3.Row
        return db

    def _initialize(self) -> None:
        with self._connect() as db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS episodic_memory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    user_feedback TEXT NOT NULL,
                    requested_tone TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    unresolved_questions INTEGER NOT NULL
                )
            """)
            db.execute("CREATE INDEX IF NOT EXISTS episodic_memory_created_at ON episodic_memory(created_at)")

    def record(self, event: MemoryEvent, *, consent: bool = False) -> int:
        if consent is not True:
            raise PermissionError("episodic memory requires explicit user consent")
        timestamp = event.created_at or _now().isoformat()
        with self._connect() as db:
            cursor = db.execute(
                """INSERT INTO episodic_memory
                   (created_at, outcome, user_feedback, requested_tone, confidence, unresolved_questions)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (timestamp, event.outcome, event.user_feedback, event.requested_tone,
                 float(event.confidence), event.unresolved_questions),
            )
            return int(cursor.lastrowid)

    def summarize(self, *, days: int = 30, requested_tone: str | None = None) -> MemorySummary:
        if isinstance(days, bool) or not isinstance(days, int) or not 1 <= days <= 365:
            raise ValueError("days must be from 1 to 365")
        if requested_tone is not None and requested_tone not in TONES:
            raise ValueError("unsupported requested tone")
        cutoff = (_now() - timedelta(days=days)).isoformat()
        query = """SELECT COUNT(*) AS event_count,
                   SUM(CASE WHEN user_feedback != 'none' THEN 1 ELSE 0 END) AS feedback_count,
                   SUM(CASE WHEN user_feedback = 'positive' THEN 1 ELSE 0 END) AS positive_count,
                   SUM(CASE WHEN user_feedback = 'negative' THEN 1 ELSE 0 END) AS negative_count,
                   SUM(CASE WHEN user_feedback = 'mixed' THEN 1 ELSE 0 END) AS mixed_count,
                   SUM(CASE WHEN outcome = 'completed' THEN 1 ELSE 0 END) AS completed_count
                   FROM episodic_memory WHERE created_at >= ?"""
        params: list[object] = [cutoff]
        if requested_tone is not None:
            query += " AND requested_tone = ?"
            params.append(requested_tone)
        with self._connect() as db:
            row = db.execute(query, params).fetchone()
        return MemorySummary(
            event_count=int(row["event_count"] or 0),
            feedback_count=int(row["feedback_count"] or 0),
            positive_count=int(row["positive_count"] or 0),
            negative_count=int(row["negative_count"] or 0),
            mixed_count=int(row["mixed_count"] or 0),
            completed_count=int(row["completed_count"] or 0),
            window_days=days,
            requested_tone=requested_tone,
        )

    def purge_expired(self, *, now: datetime | None = None) -> int:
        current = now or _now()
        if current.tzinfo is None:
            raise ValueError("now must include a timezone")
        cutoff = (current.astimezone(timezone.utc) - timedelta(days=self.retention_days)).isoformat()
        with self._connect() as db:
            cursor = db.execute("DELETE FROM episodic_memory WHERE created_at < ?", (cutoff,))
            return int(cursor.rowcount)

    def clear_all(self, *, confirmed: bool = False) -> int:
        if confirmed is not True:
            raise PermissionError("clearing memory requires explicit confirmation")
        with self._connect() as db:
            cursor = db.execute("DELETE FROM episodic_memory")
            return int(cursor.rowcount)
