"""Adversarial tests for Radar V3 Context Bridge."""

import copy
import importlib.util
from pathlib import Path

MODULE_PATH = Path(__file__).with_name(
    "evidence_gate_context_bridge_v3.py"
)

checks = 0
failures = 0


def check(name, condition):
    global checks, failures
    checks += 1
    passed = bool(condition)
    if not passed:
        failures += 1
    print(f"{'PASS' if passed else 'FAIL'}: {name}")


def rejects_type(function, *args, **kwargs):
    try:
        function(*args, **kwargs)
    except TypeError:
        return True
    except Exception:
        return False
    return False


spec = importlib.util.spec_from_file_location(
    "evidence_gate_context_bridge_v3",
    MODULE_PATH,
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

bridge = module.build_evidence_gate_runtime_inputs

# 1. Preserve upstream data without reconstruction.

radar = {
    "assets": [
        {
            "ticker": "VRT",
            "score": {
                "status": "INSUFFICIENT_DATA",
                "publishable": False,
            },
            "signals": [],
            "provenance": {},
        },
        {
            "ticker": "CRSP",
        },
        {
            "ticker": "ETON",
            "score": {"legacy_score": 87},
        },
    ],
    "decision_center": {
        "action_of_day": "UPSTREAM_VALUE",
    },
}

publication = {
    "VRT": {
        "ticker": "VRT",
        "eligible": False,
        "components": {"price": {"eligible": False}},
    },
}

risk = {
    "VRT": {
        "ticker": "VRT",
        "source": {"primary_source": "UPSTREAM"},
    },
}

snapshot = copy.deepcopy((radar, publication, risk))
output = bridge(radar, publication, risk)

check("Output exact fields", set(output) == {
    "radar",
    "publication_context_by_ticker",
    "risk_source_context_by_ticker",
})

check("Radar unchanged", radar == snapshot[0])
check("Publication unchanged", publication == snapshot[1])
check("Risk unchanged", risk == snapshot[2])

check("Radar transported faithfully", output["radar"] == radar)
check("Publication transported faithfully",
      output["publication_context_by_ticker"] == publication)
check("Risk transported faithfully",
      output["risk_source_context_by_ticker"] == risk)

check("CRSP score not reconstructed",
      "score" not in output["radar"]["assets"][1])
check("CRSP signals not reconstructed",
      "signals" not in output["radar"]["assets"][1])
check("CRSP provenance not reconstructed",
      "provenance" not in output["radar"]["assets"][1])
check("CRSP publication not synthesized",
      "CRSP" not in output["publication_context_by_ticker"])
check("CRSP risk not synthesized",
      "CRSP" not in output["risk_source_context_by_ticker"])

check("Legacy score not translated",
      output["radar"]["assets"][2]["score"] == {
          "legacy_score": 87
      })

check("No ETON publication synthesized",
      "ETON" not in output["publication_context_by_ticker"])
check("No ETON risk synthesized",
      "ETON" not in output["risk_source_context_by_ticker"])

check("Decision center preserved",
      output["radar"]["decision_center"] ==
      {"action_of_day": "UPSTREAM_VALUE"})

# 2. Optional contexts and empty structures.

empty = bridge({})

check("Empty radar preserved", empty["radar"] == {})
check("Missing publication returns empty dict",
      empty["publication_context_by_ticker"] == {})
check("Missing risk returns empty dict",
      empty["risk_source_context_by_ticker"] == {})

check("Optional contexts are distinct",
      empty["publication_context_by_ticker"]
      is not empty["risk_source_context_by_ticker"])

# 3. Invalid inputs must fail explicitly.

for value in (None, [], (), "", 0, False):
    check(
        f"Invalid radar rejected: {type(value).__name__}",
        rejects_type(bridge, value),
    )

for value in ([], (), "", 0, False):
    check(
        f"Invalid publication rejected: {type(value).__name__}",
        rejects_type(
            bridge,
            {},
            publication_context_by_ticker=value,
        ),
    )

for value in ([], (), "", 0, False):
    check(
        f"Invalid risk rejected: {type(value).__name__}",
        rejects_type(
            bridge,
            {},
            risk_source_context_by_ticker=value,
        ),
    )

# 4. Reference semantics: explicitly documented behavior.

check("Radar reference transported",
      output["radar"] is radar)

check("Publication reference transported",
      output["publication_context_by_ticker"] is publication)

check("Risk reference transported",
      output["risk_source_context_by_ticker"] is risk)

# 5. Ensure repeated calls do not share omitted contexts.

first = bridge({})
second = bridge({})

check("No shared default publication dictionary",
      first["publication_context_by_ticker"]
      is not second["publication_context_by_ticker"])

check("No shared default risk dictionary",
      first["risk_source_context_by_ticker"]
      is not second["risk_source_context_by_ticker"])

print()
print(f"CHECKS = {checks}")
print(f"FAILURES = {failures}")

if failures:
    print("RESULT = FAIL")
    raise SystemExit(1)

print("RESULT = PASS")
raise SystemExit(0)
