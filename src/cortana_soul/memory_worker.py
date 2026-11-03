"""Independent worker, scheduling, metrics and lifecycle tools for SOUL CORE v1.9.0.

The worker is intentionally single-active-consumer per outbox database. Run
recovery before starting it; do not start multiple workers against the same
outbox until row leasing/ownership is introduced.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Callable

from .memory_integration import MemoryEventBus, TransactionalOutbox


@dataclass(frozen=True)
class MemoryMetricsSnapshot:
    cycles: int
    delivered: int
    pending: int
    dead_lettered: int
    last_cycle_seconds: float
    total_cycle_seconds: float
    last_success_at: float | None
    last_error: str | None


class MemoryMetrics:
    """Thread-safe in-process operational counters; no memory content is recorded."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._cycles = self._delivered = 0
        self._last_cycle = self._total_cycle = 0.0
        self._last_success: float | None = None
        self._last_error: str | None = None

    def record_cycle(self, *, delivered: int, duration: float,
                     pending: int, dead_lettered: int, error: str | None = None) -> None:
        with self._lock:
            self._cycles += 1
            self._delivered += delivered
            self._last_cycle = max(0.0, duration)
            self._total_cycle += self._last_cycle
            if error is None:
                self._last_success = time.time()
                self._last_error = None
            else:
                self._last_error = error[:500]
            self._pending = pending
            self._dead_lettered = dead_lettered

    def snapshot(self) -> MemoryMetricsSnapshot:
        with self._lock:
            return MemoryMetricsSnapshot(
                self._cycles, self._delivered, getattr(self, "_pending", 0),
                getattr(self, "_dead_lettered", 0), self._last_cycle,
                self._total_cycle, self._last_success, self._last_error,
            )


class DeadLetterQueue:
    """Operator-facing access to exhausted events; no automatic deletion."""

    def __init__(self, outbox: TransactionalOutbox) -> None:
        self.outbox = outbox

    def list(self, *, limit: int = 100) -> tuple[dict, ...]:
        return self.outbox.list_failed(limit=limit)

    def requeue(self, event_id: str) -> bool:
        return self.outbox.requeue_failed(event_id)


class MemoryWorker:
    """Cooperative outbox worker with bounded batches and graceful shutdown."""

    def __init__(self, event_bus: MemoryEventBus, *, batch_size: int = 50,
                 idle_seconds: float = 1.0, metrics: MemoryMetrics | None = None) -> None:
        if isinstance(batch_size, bool) or not isinstance(batch_size, int) or not 1 <= batch_size <= 500:
            raise ValueError("batch_size must be from 1 to 500")
        if isinstance(idle_seconds, bool) or not isinstance(idle_seconds, (int, float)) or idle_seconds <= 0:
            raise ValueError("idle_seconds must be positive")
        self.event_bus = event_bus
        self.batch_size = batch_size
        self.idle_seconds = float(idle_seconds)
        self.metrics = metrics or MemoryMetrics()
        self._stop = threading.Event()
        self._started = False

    def run_once(self) -> int:
        started = time.monotonic()
        before = self.event_bus.outbox.stats()
        error = None
        delivered = 0
        try:
            delivered = self.event_bus.dispatch(limit=self.batch_size)
        except Exception as exc:
            error = repr(exc)
        after = self.event_bus.outbox.stats()
        self.metrics.record_cycle(
            delivered=delivered, duration=time.monotonic() - started,
            pending=after.pending, dead_lettered=after.failed, error=error,
        )
        if error is not None:
            raise RuntimeError("memory worker cycle failed") from None
        return delivered

    def run_forever(self, *, recover_processing: bool = True) -> None:
        if self._started:
            raise RuntimeError("MemoryWorker cannot be started more than once")
        self._started = True
        self._stop.clear()
        if recover_processing:
            # Safe only for one active worker per outbox database.
            self.event_bus.outbox.recover_processing()
        while not self._stop.is_set():
            delivered = self.run_once()
            if delivered == 0:
                self._stop.wait(self.idle_seconds)

    def stop(self) -> None:
        """Request shutdown; the current dispatch cycle is allowed to finish."""
        self._stop.set()

    @property
    def stopped(self) -> bool:
        return self._stop.is_set()


class MemoryScheduler:
    """Single-thread periodic scheduler with interruptible waits and clean stop."""

    def __init__(self, *, interval_seconds: float = 60.0) -> None:
        if isinstance(interval_seconds, bool) or not isinstance(interval_seconds, (int, float)) or interval_seconds <= 0:
            raise ValueError("interval_seconds must be positive")
        self.interval_seconds = float(interval_seconds)
        self._stop = threading.Event()
        self._started = False

    def run_forever(self, task: Callable[[], object], *, run_immediately: bool = True) -> None:
        if not callable(task):
            raise TypeError("task must be callable")
        if self._started:
            raise RuntimeError("MemoryScheduler cannot be started more than once")
        self._started = True
        self._stop.clear()
        if run_immediately:
            task()
        while not self._stop.wait(self.interval_seconds):
            task()

    def stop(self) -> None:
        self._stop.set()


class MemoryLifecycleManager:
    """Retention controls for queue metadata; never purges failed events implicitly."""

    def __init__(self, outbox: TransactionalOutbox) -> None:
        self.outbox = outbox

    def purge_delivered(self, *, older_than_seconds: float, now: float | None = None) -> int:
        if isinstance(older_than_seconds, bool) or not isinstance(older_than_seconds, (int, float)) or older_than_seconds < 0:
            raise ValueError("older_than_seconds must be non-negative")
        cutoff = (time.time() if now is None else now) - float(older_than_seconds)
        return self.outbox.purge_delivered_before(cutoff)
