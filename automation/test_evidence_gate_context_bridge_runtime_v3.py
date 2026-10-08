"""D.3D.4L.3D - RED tests for Evidence Gate Context Bridge."""

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


def raises_type_error(function, *args, **kwargs):
    try:
        function(*args, **kwargs)
    except TypeError:
        return True
    except Exception:
        return False
    return False


check("Runtime module exists", MODULE_PATH.is_file())

bridge = None

if MODULE_PATH.is_file():
    try:
        spec = importlib.util.spec_from_file_location(
            "evidence_gate_context_bridge_v3",
            MODULE_PATH,
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        bridge = getattr(
            module,
            "build_evidence_gate_runtime_inputs",
            None,
        )
    except Exception as exc:
        print(f"IMPORT ERROR: {type(exc).__name__}: {exc}")

check("Runtime function exists", callable(bridge))

if callable(bridge):

    radar = {
        "assets": [
            {
                "ticker": "VRT",
                "score": {
                    "status": "PARTIAL",
                    "publishable": False,
                },
                "signals": [{"signal": "UPSTREAM_ONLY"}],
            },
            {"ticker": "CRSP"},
        ],
    }

    publication = {
        "VRT": {
            "ticker": "VRT",
            "eligible": False,
            "components": {},
        }
    }

    risk = {
        "VRT": {
            "ticker": "VRT",
            "source": {"primary_source": "UPSTREAM"},
        }
    }

    before = copy.deepcopy((radar, publication, risk))

    output = bridge(radar, publication, risk)

    check("Output is dictionary", isinstance(output, dict))

    check(
        "Output has exactly three fields",
        isinstance(output, dict)
        and set(output) == {
            "radar",
            "publication_context_by_ticker",
            "risk_source_context_by_ticker",
        },
    )

    check(
        "Radar content preserved",
        output["radar"] == radar,
    )

    check(
        "Publication context preserved",
        output["publication_context_by_ticker"] == publication,
    )

    check(
        "Risk source context preserved",
        output["risk_source_context_by_ticker"] == risk,
    )

    check(
        "Inputs not mutated",
        (radar, publication, risk) == before,
    )

    check(
        "No synthetic CRSP publication",
        "CRSP" not in output["publication_context_by_ticker"],
    )

    check(
        "No synthetic CRSP risk",
        "CRSP" not in output["risk_source_context_by_ticker"],
    )

    check(
        "Missing CRSP signals preserved",
        "signals" not in output["radar"]["assets"][1],
    )

    check(
        "Missing CRSP score preserved",
        "score" not in output["radar"]["assets"][1],
    )

    missing = bridge({"assets": []})

    check(
        "Optional publication context is empty",
        missing["publication_context_by_ticker"] == {},
    )

    check(
        "Optional risk context is empty",
        missing["risk_source_context_by_ticker"] == {},
    )

    check(
        "Invalid radar rejected",
        raises_type_error(bridge, None),
    )

    check(
        "Invalid publication context rejected",
        raises_type_error(
            bridge,
            {"assets": []},
            publication_context_by_ticker=[],
        ),
    )

    check(
        "Invalid risk context rejected",
        raises_type_error(
            bridge,
            {"assets": []},
            risk_source_context_by_ticker=[],
        ),
    )

print()
print(f"CHECKS = {checks}")
print(f"FAILURES = {failures}")

if failures:
    print("RESULT = RED")
    raise SystemExit(1)

print("RESULT = GREEN")
raise SystemExit(0)
