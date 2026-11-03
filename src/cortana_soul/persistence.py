"""Persistent Soul Core profile with audited, approval-gated adaptation.

SQLite is used from the Python standard library. Core identity, values and
behavioral invariants are immutable through this API; only bounded style
parameters may be adapted.
"""
from __future__ import annotations

import json
import math
import sqlite3
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .core import SoulProfile, profile_from_dict

PERSONALITY_FIELDS = frozenset({
    "curiosity", "warmth", "humor", "directness", "formality"
})
MAX_PERSONALITY_STEP = 0.10


def _profile_dict(profile: SoulProfile) -> dict[str, Any]:
    return asdict(profile)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SoulProfileStore:
    """SQLite-backed profile store with append-only change history."""

    def __init__(self, database: str | Path) -> None:
        self.database = str(database)
        Path(self.database).parent.mkdir(parents=True, exist_ok=True) if self.database != ":memory:" else None
        self._initialize_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database, timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize_schema(self) -> None:
        with self._connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS soul_profile (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    revision INTEGER NOT NULL CHECK (revision >= 1),
                    profile_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS soul_change_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    revision INTEGER NOT NULL,
                    event_type TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    before_json TEXT,
                    after_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TRIGGER IF NOT EXISTS soul_change_log_no_update
                BEFORE UPDATE ON soul_change_log
                BEGIN SELECT RAISE(ABORT, 'change history is append-only'); END;
                CREATE TRIGGER IF NOT EXISTS soul_change_log_no_delete
                BEFORE DELETE ON soul_change_log
                BEGIN SELECT RAISE(ABORT, 'change history is append-only'); END;
            """)

    def initialize(self, profile: SoulProfile) -> int:
        """Create the initial persisted profile once; never overwrite existing data."""
        snapshot = json.dumps(_profile_dict(profile), ensure_ascii=False, sort_keys=True)
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT revision FROM soul_profile WHERE id = 1").fetchone()
            if row:
                db.commit()
                return int(row["revision"])
            db.execute(
                "INSERT INTO soul_profile(id, revision, profile_json) VALUES(1, 1, ?)",
                (snapshot,),
            )
            db.execute(
                """INSERT INTO soul_change_log
                   (revision, event_type, reason, before_json, after_json, created_at)
                   VALUES(1, 'initialized', 'Initial profile registration', NULL, ?, ?)""",
                (snapshot, _utc_now()),
            )
            db.commit()
            return 1

    def get(self) -> tuple[int, SoulProfile]:
        with self._connect() as db:
            row = db.execute(
                "SELECT revision, profile_json FROM soul_profile WHERE id = 1"
            ).fetchone()
        if row is None:
            raise RuntimeError("Soul profile store is not initialized")
        return int(row["revision"]), profile_from_dict(json.loads(row["profile_json"]))

    def update_personality(
        self,
        changes: Mapping[str, float],
        *,
        reason: str,
        approved: bool = False,
        expected_revision: int | None = None,
    ) -> int:
        """Apply a small, explicitly approved style change and append an audit event."""
        if approved is not True:
            raise PermissionError("personality changes require explicit approval")
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("a non-empty change reason is required")
        if not isinstance(changes, Mapping) or not changes:
            raise ValueError("changes must be a non-empty mapping")
        unknown = set(changes) - PERSONALITY_FIELDS
        if unknown:
            raise ValueError(f"only personality style fields may change: {sorted(unknown)}")

        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT revision, profile_json FROM soul_profile WHERE id = 1"
            ).fetchone()
            if row is None:
                db.rollback()
                raise RuntimeError("Soul profile store is not initialized")

            revision = int(row["revision"])
            if expected_revision is not None and expected_revision != revision:
                db.rollback()
                raise RuntimeError(
                    f"stale profile revision: expected {expected_revision}, current {revision}"
                )

            before = json.loads(row["profile_json"])
            after = json.loads(row["profile_json"])
            personality = after["personality"]
            for field, raw_value in changes.items():
                if isinstance(raw_value, bool) or not isinstance(raw_value, (int, float)):
                    db.rollback()
                    raise ValueError(f"{field} must be a number between 0 and 1")
                value = float(raw_value)
                current = float(personality[field])
                if not math.isfinite(value) or not 0.0 <= value <= 1.0:
                    db.rollback()
                    raise ValueError(f"{field} must be finite and between 0 and 1")
                if abs(value - current) > MAX_PERSONALITY_STEP:
                    db.rollback()
                    raise ValueError(
                        f"{field} change exceeds the per-update limit of {MAX_PERSONALITY_STEP}"
                    )
                personality[field] = value

            # Re-run all v1.1 invariants before committing the new snapshot.
            validated = profile_from_dict(after)
            before_json = json.dumps(before, ensure_ascii=False, sort_keys=True)
            after_json = json.dumps(_profile_dict(validated), ensure_ascii=False, sort_keys=True)
            new_revision = revision + 1
            db.execute(
                "UPDATE soul_profile SET revision = ?, profile_json = ? WHERE id = 1",
                (new_revision, after_json),
            )
            db.execute(
                """INSERT INTO soul_change_log
                   (revision, event_type, reason, before_json, after_json, created_at)
                   VALUES(?, 'personality_updated', ?, ?, ?, ?)""",
                (new_revision, reason.strip(), before_json, after_json, _utc_now()),
            )
            db.commit()
            return new_revision

    def history(self, *, limit: int = 100) -> list[dict[str, Any]]:
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 1000:
            raise ValueError("limit must be an integer from 1 to 1000")
        with self._connect() as db:
            rows = db.execute(
                """SELECT revision, event_type, reason, before_json, after_json, created_at
                   FROM soul_change_log ORDER BY id DESC LIMIT ?""",
                (limit,),
            ).fetchall()
        return [
            {
                "revision": int(row["revision"]),
                "event_type": row["event_type"],
                "reason": row["reason"],
                "before": json.loads(row["before_json"]) if row["before_json"] else None,
                "after": json.loads(row["after_json"]),
                "created_at": row["created_at"],
            }
            for row in rows
        ]
