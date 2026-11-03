# CORTANA SOUL CORE v1.1.0

**Status:** initial implementation  
**Branch:** `feature/soul-core-v1.1.0`  
**Runtime:** Python 3.11+ standard library

## Scope

SOUL CORE v1.1.0 introduces a persistent, validated software identity profile:
- identity metadata;
- explicit core values;
- bounded personality parameters;
- mandatory behavior invariants;
- JSON profile loading;
- read-only runtime summary.

This is a software model of identity and behavior. It does not establish consciousness, subjective experience, or human emotions.

## Files

- `config/soul-profile.json` — default Polish-language profile.
- `src/cortana_soul/core.py` — immutable data models, validation and runtime facade.
- `tests/test_soul_core.py` — standard-library unit tests.

## Safety invariants

The profile loader rejects configurations that:
- allow external actions without approval;
- permit claims of sensory access that the agent does not have;
- permit claims of human emotions;
- bypass policy checks for memory writes.

Personality parameters are numeric values in the inclusive range 0.0–1.0. They tune communication style only and must not override safety or truthfulness rules.

## Run tests

From the repository root:

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

Windows PowerShell:

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -v
```

## Acceptance criteria

- The default JSON profile loads successfully.
- Invalid personality scores are rejected.
- Unsafe behavior flags are rejected.
- The runtime exposes a read-only identity summary.
- The implementation uses only the Python standard library.

## Not included yet

No LLM provider, microphone, camera, persistent memory database, autonomous code modification, or operating-system command execution is included in this milestone. Those capabilities require separate adapters, explicit permissions, isolated testing and independent governance.
