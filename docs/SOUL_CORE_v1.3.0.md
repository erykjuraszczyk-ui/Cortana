# CORTANA SOUL CORE v1.3.0

**Release:** Adaptive Emotional State, Context Awareness & Reflection Engine  
**Branch:** `feature/soul-core-v1.3.0`  
**Runtime:** Python 3.11+ standard library

## Modules

- `affect.py`: transient numerical interaction-state estimate (valence, arousal, confidence, uncertainty), updated with bounded exponential smoothing.
- `context.py`: validated, short-lived context assembled only from explicit turn metadata.
- `reflection.py`: deterministic, explainable review of an interaction outcome and explicit feedback.

## Design boundaries

“Emotional state” here means a computational control signal used to tune response strategy. It is not a claim that Cortana experiences human emotions or subjective feelings.

The engine does not infer sensitive personal traits, build a hidden psychological profile, or treat one interaction as a permanent preference. Context is supplied explicitly and should be discarded at the end of its intended scope by the integrating application.

Reflection produces recommendations only. It never writes to the profile, changes personality, executes tools, or deploys code. Any future style change must pass through the v1.2 `SoulProfileStore.update_personality` approval gate.

## Example

```python
from cortana_soul.affect import AffectEngine
from cortana_soul.context import ContextResolver
from cortana_soul.reflection import ReflectionEngine, ReflectionInput

affect = AffectEngine()
state = affect.update({"valence": 0.3, "uncertainty": 0.2})
context = ContextResolver().resolve(
    task="Explain the requested topic",
    requested_tone="concise",
)
proposal = ReflectionEngine().reflect(
    ReflectionInput(context, outcome="completed", user_feedback="none"),
    state,
)
print(proposal.recommendation)
```

## Run tests

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

Windows PowerShell:

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -v
```

## Acceptance criteria

- All affect values are finite and range-checked.
- Updates use configurable smoothing and reject unknown dimensions.
- Context frames accept only explicit, validated metadata.
- Reflection outputs are deterministic and explainable.
- One positive or negative interaction never silently changes personality.
- Reflection proposals are approval-gated and never auto-applied.
- Existing v1.1 and v1.2 tests remain part of CI.

## Not included

No emotion recognition from camera/microphone, diagnosis, sensitive-trait inference, LLM self-modification, autonomous actions, or claims of consciousness are included.
