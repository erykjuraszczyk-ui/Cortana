# CORTANA SOUL CORE v1.4.0

**Release:** Memory-Aware Reflection  
**Branch:** `feature/soul-core-v1.4.0`  
**Runtime:** Python 3.11+ standard library

## Purpose

v1.4.0 adds consent-based episodic memory and uses aggregate, explicit feedback
to make reflection more context-aware over time. It does not store raw messages
or infer sensitive personal traits.

## Modules

- `memory.py`: SQLite-backed structured event store.
- `memory_reflection.py`: reflection layer that evaluates aggregate memory
  evidence and produces explainable recommendations.
- Existing `reflection.py`: remains the single-interaction reflection baseline.

## Stored fields

Each event stores only timestamp, task outcome, explicit feedback category,
requested response tone, confidence, and unresolved-question count. The event
does not store task text, message content, identity attributes, or inferred
psychological characteristics.

Writes require explicit consent on each call. Retention defaults to 90 days
and is configurable from 1 to 3650 days. Expired records can be purged, and
complete deletion requires an explicit confirmation flag.

## Reflection policy

- At least three feedback-bearing events are required before a repeated pattern
  is reported.
- At least 80% positive feedback produces a suggestion to ask whether the
  approach should be saved as a preference.
- At least 60% negative feedback produces a suggestion to ask what should change.
- Mixed evidence does not produce a stable preference.
- No proposal changes the profile or memory automatically.
- Any future profile adaptation must still use the v1.2 approval gate and its
  bounded per-update change limit.

## Example

```python
from cortana_soul.memory import EpisodicMemoryStore, MemoryEvent
from cortana_soul.memory_reflection import MemoryAwareReflectionEngine

store = EpisodicMemoryStore("data/cortana-memory.sqlite3", retention_days=90)
store.record(
    MemoryEvent(outcome="completed", user_feedback="positive", requested_tone="concise"),
    consent=True,  # obtain this permission from the user-facing application
)
summary = store.summarize(days=30, requested_tone="concise")
proposal = MemoryAwareReflectionEngine().reflect(event, affect, summary)
print(proposal.recommendation)
```

## Tests

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

Windows PowerShell:

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -v
```

## Limitations and safeguards

This is structured episodic memory, not a vector database or semantic retrieval
system. It does not establish consciousness, subjective emotion, or personal
understanding. The integrating application must provide a real consent UI,
protect the SQLite file with OS-level access controls, and invoke retention
cleanup. SQLite deletion is logical deletion; secure media sanitization is
outside this module's scope.
