# CORTANA SOUL CORE v1.9.0

**Release:** Autonomous Memory Worker & Lifecycle Management  
**Python:** 3.11+  
**Platforms:** Windows and Linux  
**Runtime dependencies:** Python standard library only

## Scope

v1.9.0 separates durable memory synchronization from the agent's request path. It adds a cooperative worker loop, periodic scheduler, dead-letter inspection and requeue, operational counters, and explicit retention for delivered queue metadata.

## Components

- `MemoryWorker`: bounded batch dispatcher with idle backoff, restart recovery and cooperative shutdown.
- `MemoryScheduler`: single-thread periodic task runner with interruptible waits and clean stop.
- `DeadLetterQueue`: lists exhausted events and allows an operator to requeue a selected event.
- `MemoryMetrics`: in-process counters for cycles, delivered events, pending/dead-letter counts, cycle duration and last error. It never records memory text.
- `MemoryLifecycleManager`: purges only delivered outbox metadata older than a caller-selected retention period. Failed events are never purged automatically.

## Quick start

```python
from cortana_soul import (
    DeadLetterQueue, MemoryMetrics, MemoryWorker,
    MemoryEventBus, MemoryIndexSynchronizer, PersistentBM25Index,
    TransactionalOutbox,
)

outbox = TransactionalOutbox("data/outbox.sqlite3")
index = PersistentBM25Index("data/lexical.sqlite3")
sync = MemoryIndexSynchronizer(index)
bus = MemoryEventBus(outbox, sync)

metrics = MemoryMetrics()
worker = MemoryWorker(bus, batch_size=50, idle_seconds=1.0, metrics=metrics)

try:
    worker.run_forever()
except KeyboardInterrupt:
    worker.stop()

print(metrics.snapshot())
print(DeadLetterQueue(outbox).list())
```

Run recovery from the authoritative store before serving retrieval traffic:

```python
health = recovery_engine.recover(authoritative_store.list_document_records())
```

A separate process can host the worker. The main agent should enqueue approved events and continue its request handling without waiting for a long queue drain.

## Operating model

1. Keep the authoritative memory store as source of truth; BM25 remains a rebuildable projection.
2. Run exactly one active `MemoryWorker` per outbox database. The current SQLite claim implementation does not yet use worker leases or ownership tokens, so multiple concurrent workers are not supported.
3. On worker startup, abandoned `processing` events are returned to `pending`. Set `recover_processing=False` only when an external recovery coordinator already handled this step.
4. Retry policy remains bounded by `RetryManager`. Exhausted events move to `failed` and are visible through `DeadLetterQueue`.
5. Requeue dead-letter events only after reviewing the failure; requeue resets their attempt count.
6. Use `MemoryScheduler` for periodic recovery/consistency work. Schedule one task per scheduler instance.
7. Purge delivered queue metadata only after an explicit retention decision. Failed events are intentionally excluded.

## Shutdown and restart

Call `MemoryWorker.stop()` or `MemoryScheduler.stop()` to request shutdown. The current synchronous dispatch/task is allowed to finish; waits are interruptible. The worker is single-use per instance; construct a new instance after shutdown. On restart, the worker recovers abandoned processing rows before polling.

## Metrics and limitations

- Metrics are in-process and reset when the process restarts. Export to Prometheus/OpenTelemetry is a future adapter, not included here.
- Worker and scheduler are standard-library threads; process supervision (systemd, Windows Service, Docker restart policy) belongs to deployment configuration.
- The outbox and authoritative store are not one distributed transaction. Reconciliation remains required to repair a crash between source mutation and enqueue.
- Current claim semantics are for a single active worker. Multi-worker leasing, heartbeat expiry and fencing tokens are future work.
- Dead-letter events require operator review; no automatic destructive cleanup is performed.
- No automatic chat transcript ingestion is introduced. Ingestion still requires explicit consent and deletion requires explicit confirmation.
- This is deterministic software memory orchestration, not human-like memory or consciousness.

## Tests

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

The suite covers dispatch, metrics, dead-letter review/requeue, delivered-event retention and scheduler/worker shutdown without model downloads or external services.
