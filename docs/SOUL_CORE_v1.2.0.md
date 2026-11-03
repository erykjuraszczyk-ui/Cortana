# CORTANA SOUL CORE v1.2.0

**Release scope:** Persistent Identity, Personality Evolution & Behavioral Consistency  
**Branch:** `feature/soul-core-v1.2.0`  
**Runtime:** Python 3.11+ standard library

## Delivered capabilities

- SQLite persistence for the validated v1.1 profile.
- Monotonic profile revisions and optimistic concurrency checks.
- Append-only audit history for initialization and approved updates.
- Controlled personality adaptation: only `curiosity`, `warmth`, `humor`, `directness`, and `formality` are mutable.
- Maximum absolute change per parameter and update: `0.10`.
- Explicit approval required for every personality update.
- Existing v1.1 profile validation is rerun before every commit.
- Core identity, values, and behavior rules cannot be changed through the adaptation API.

## Storage model

The SQLite database contains:
- `soul_profile`: one current profile snapshot and its revision;
- `soul_change_log`: append-only event history with before/after snapshots, reason and UTC timestamp.

Database triggers reject update/delete operations on the audit table. This protects against accidental application-level edits; it is not tamper-proof storage against an administrator who controls the database file.

## Example

```python
from cortana_soul.core import load_profile
from cortana_soul.persistence import SoulProfileStore

profile = load_profile("config/soul-profile.json")
store = SoulProfileStore("data/cortana-soul.sqlite3")
store.initialize(profile)

new_revision = store.update_personality(
    {"humor": 0.50},
    reason="User feedback: slightly more humor",
    approved=True,
    expected_revision=1,
)
print(new_revision)
print(store.history())
```

Approval is an explicit API argument in this milestone. A production UI must bind it to a real authenticated user-confirmation flow; a caller must not silently set it to `True`.

## Run tests

Linux/macOS:
```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

Windows PowerShell:
```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -v
```

## Acceptance criteria

- Profile survives process restart through SQLite.
- Initialization never overwrites an existing profile.
- Every approved update increments the revision and appends an audit event.
- Unapproved, stale, invalid, or excessive changes are rejected.
- Identity, core values and behavior invariants remain unchanged through this API.
- Audit history rejects UPDATE and DELETE statements.
- All v1.1 validation rules remain active.

## Limitations

This milestone does not add LLM-driven self-modification, autonomous deployment, hardware sensing, or subjective emotion/consciousness. Personality values are communication-style parameters only. SQLite triggers provide application-level audit protection, not cryptographic immutability or protection against privileged file tampering.
