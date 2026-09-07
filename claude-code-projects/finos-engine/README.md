# Financial OS calculation engine — finos/

Plain Python + PyYAML, stdlib `pytest` for tests. No frameworks, no database,
no network calls. Owned by claude code (Engineering Agent), per
`financial-os/State/engineering.md` — the FinOS engineering carrier.

## What's here

| Module | Does |
|---|---|
| `bands.py` | `Unknown`/`UNKNOWN` sentinel, `Range` type, §1.9 rounding helpers. Everything else imports from here. |
| `profile_load.py` | Reads and validates a profile YAML into a `Profile`. Read-only, fail-closed. |
| `lifestyle.py` | Annual spending split (essential/lifestyle/discretionary) and sum-consistency check. |
| `buckets.py` | Assigns liquid/investment items to the six planning buckets by purpose, not account type. |
| `resilience.py` | Safety-reserve requirement vs. what's actually liquid enough to meet it. |
| `obligations.py` | Per-obligation funding gap; near-term (≤5y) gap aggregated separately. |
| `retirement.py` | Simple deterministic Base/Downside sustainability projection, with one flat annual contribution. |
| `surplus.py` | The decision-hierarchy gate — requires resilience + obligations + retirement results as arguments. Also builds `HierarchyStatus` via `attest_hierarchy`. |
| `packet.py` | Builds a sanitized Markdown decision packet. Cannot accept a `Profile`; requires a `HierarchyStatus`. |

## How to run it

From `finos-engine/`, using any Python 3.11+ with `pyyaml` and `pytest` installed
(no `pip install -e .` needed — `finos/` is importable from the repo root as-is):

```bash
python -m pytest tests/
```

Or run one module's calculation by hand against the synthetic fixture:

```python
from finos.profile_load import load_profile
from finos.lifestyle import compute_lifestyle
from finos.resilience import compute_resilience

profile = load_profile("tests/fixtures/synthetic-profile.yaml")
lifestyle_result = compute_lifestyle(profile)
resilience_result = compute_resilience(profile, lifestyle_result)
print(resilience_result)
```

Run from the repo root (`finos-engine/`) — plain `python` puts the current
directory on `sys.path`, which is what makes `finos` importable without a
package install.

## The one rule that matters most

**Never point this at a real profile.** `load_profile` refuses anything that
doesn't declare `synthetic: true|false` at all, but it does *not* refuse a
file that dishonestly claims `synthetic: true` while holding real numbers —
that check is structurally impossible for code to make. The real profile
lives at `E:\RBK_AUR_PRIVATE\Financial\profile.yaml` and nothing under this
repo or the `financial-os/` Workspace should ever read it. See
`financial-os/State/State.md` §2.

## Call order

**Corrected 2026-08-21 (Phase 3B-4a, C1/C6).** The original ordering here put
surplus before retirement, which contradicted the approved hierarchy in
`financial-os/State/State.md` §1.4 (RETIREMENT SUFFICIENCY sits *above* SURPLUS CAPITAL)
and left `RetirementResult` consumed by nothing. `surplus.compute_surplus`
now takes `resilience`, `obligations` **and `retirement`** results as
*required* arguments — there is no way to call it without all three — and
`packet.build_packet` requires a `HierarchyStatus` that only a completed run
can produce. Enforcement is structural, not conventional:

```
profile_load → lifestyle → buckets
                    ↓
      resilience, obligations, retirement
        (SAFETY)   (OBLIGATIONS)  (RETIREMENT)
                    ↓
            surplus (SURPLUS / OPTIMIZATION)
              also: attest_hierarchy(...)
                    ↓
        packet (only after a human has reviewed and banded the findings;
                requires the HierarchyStatus from attest_hierarchy)
```
