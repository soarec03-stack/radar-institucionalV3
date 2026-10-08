import ast
import importlib.util
import inspect
from pathlib import Path


BASE = Path(__file__).resolve().parent.parent
AUTO = BASE / "automation"

PUBLICATION_PATH = AUTO / "publication_eligibility_v3.py"
GENERATOR_PATH = AUTO / "generate_radar_v3.py"
SCHEMA_PATH = AUTO / "schema_v3.json"

TARGET_FUNCTION = "build_publication_context_by_ticker"

checks = 0
failures = 0


def check(condition, message):
    global checks, failures
    checks += 1

    if condition:
        print(f"[PASS] {message}")
    else:
        failures += 1
        print(f"[FAIL] {message}")


def load_module():
    spec = importlib.util.spec_from_file_location(
        "publication_eligibility_v3_runtime_probe",
        PUBLICATION_PATH,
    )

    if spec is None or spec.loader is None:
        raise RuntimeError(
            "Unable to load publication_eligibility_v3.py"
        )

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    return module


print("=" * 78)
print(" D.3D.4I.1 - PUBLICATION CONTEXT INTERFACE RED BEHAVIORAL CONTRACT")
print("=" * 78)

# ----------------------------------------------------------------------
# 1. Production module remains structurally valid
# ----------------------------------------------------------------------

publication_text = PUBLICATION_PATH.read_text(encoding="utf-8-sig")
publication_ast = ast.parse(publication_text)

functions = {
    node.name: node
    for node in publication_ast.body
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
}

check(
    "evaluate_asset_publication" in functions,
    "canonical evaluate_asset_publication exists",
)

check(
    "apply_publication_eligibility" in functions,
    "existing apply_publication_eligibility exists",
)

# ----------------------------------------------------------------------
# 2. Existing API must remain unchanged
# ----------------------------------------------------------------------

apply_node = functions.get("apply_publication_eligibility")

if apply_node is not None:
    apply_args = [
        arg.arg
        for arg in apply_node.args.args
    ]

    check(
        apply_args
        == [
            "data",
            "registry",
            "policy",
            "risk_source_context_by_ticker",
        ],
        "existing apply API arguments remain canonical",
    )
else:
    check(
        False,
        "existing apply API arguments remain canonical",
    )

# ----------------------------------------------------------------------
# 3. Runtime module load
# ----------------------------------------------------------------------

try:
    module = load_module()
    module_loaded = True
except Exception as exc:
    module = None
    module_loaded = False
    print(
        "[INFO] publication module load failure:",
        type(exc).__name__,
        str(exc),
    )

check(
    module_loaded,
    "publication module loads successfully",
)

if module_loaded:
    evaluator = getattr(
        module,
        "evaluate_asset_publication",
        None,
    )

    existing_apply = getattr(
        module,
        "apply_publication_eligibility",
        None,
    )

    check(
        callable(evaluator),
        "canonical evaluator callable at runtime",
    )

    check(
        callable(existing_apply),
        "existing apply API callable at runtime",
    )

    if callable(existing_apply):
        existing_signature = inspect.signature(
            existing_apply
        )

        check(
            list(existing_signature.parameters.keys())
            == [
                "data",
                "registry",
                "policy",
                "risk_source_context_by_ticker",
            ],
            "runtime apply signature remains canonical",
        )
    else:
        check(
            False,
            "runtime apply signature remains canonical",
        )

else:
    check(
        False,
        "canonical evaluator callable at runtime",
    )

    check(
        False,
        "existing apply API callable at runtime",
    )

    check(
        False,
        "runtime apply signature remains canonical",
    )

# ----------------------------------------------------------------------
# 4. Generator compatibility remains untouched
# ----------------------------------------------------------------------

generator_text = GENERATOR_PATH.read_text(
    encoding="utf-8-sig"
)

generator_ast = ast.parse(generator_text)

apply_assignments = []

for node in ast.walk(generator_ast):
    if not isinstance(node, ast.Assign):
        continue

    if not isinstance(node.value, ast.Call):
        continue

    try:
        called = ast.unparse(node.value.func)
    except Exception:
        continue

    if called == "apply_publication_eligibility":
        apply_assignments.append(node)

check(
    len(apply_assignments) == 1,
    "Generator still has exactly one publication apply assignment",
)

if len(apply_assignments) == 1:
    target = apply_assignments[0].targets[0]

    check(
        isinstance(target, (ast.Tuple, ast.List))
        and len(target.elts) == 2,
        "Generator still unpacks exactly two publication returns",
    )
else:
    check(
        False,
        "Generator still unpacks exactly two publication returns",
    )

check(
    "publication_context_by_ticker"
    not in generator_text,
    "Generator does not yet integrate publication context",
)

# ----------------------------------------------------------------------
# 5. Schema must remain untouched
# ----------------------------------------------------------------------

schema_text = SCHEMA_PATH.read_text(
    encoding="utf-8-sig"
)

check(
    "publication_context_by_ticker"
    not in schema_text,
    "schema does not persist publication context",
)

# ----------------------------------------------------------------------
# 6. RED requirement
#
# This is the intentional RED assertion.
#
# D.3D.4G/H define that Publication Eligibility must eventually expose
# a dedicated transient interface:
#
# build_publication_context_by_ticker(
#     data,
#     registry,
#     policy=None,
#     risk_source_context_by_ticker=None
# )
#
# It must NOT be implemented by changing the return arity of
# apply_publication_eligibility().
# ----------------------------------------------------------------------

target_node = functions.get(TARGET_FUNCTION)

check(
    target_node is not None,
    "RED REQUIREMENT: dedicated publication context interface exists",
)

if target_node is not None:
    target_args = [
        arg.arg
        for arg in target_node.args.args
    ]

    check(
        target_args
        == [
            "data",
            "registry",
            "policy",
            "risk_source_context_by_ticker",
        ],
        "dedicated interface arguments are canonical",
    )

    target_callable = (
        getattr(module, TARGET_FUNCTION, None)
        if module_loaded
        else None
    )

    check(
        callable(target_callable),
        "dedicated publication context interface callable at runtime",
    )

    if callable(target_callable):
        signature = inspect.signature(
            target_callable
        )

        params = signature.parameters

        check(
            params["policy"].default is None,
            "dedicated interface policy defaults to None",
        )

        check(
            params[
                "risk_source_context_by_ticker"
            ].default is None,
            "dedicated interface risk context defaults to None",
        )

else:
    print()
    print(
        "[EXPECTED RED] "
        "build_publication_context_by_ticker is not implemented yet."
    )
    print(
        "[EXPECTED RED] "
        "No production file should be changed during D.3D.4I.1."
    )

# ----------------------------------------------------------------------
# Result
# ----------------------------------------------------------------------

print()
print("=" * 78)
print(" D.3D.4I.1 - RED BEHAVIORAL CONTRACT RESULT")
print("=" * 78)
print(f"Checks executed: {checks}")
print(f"Failures: {failures}")

if failures == 1 and target_node is None:
    print("RESULT: EXPECTED_RED")
    print(
        "RED CAUSE: "
        "build_publication_context_by_ticker is not implemented"
    )
else:
    print(
        "RESULT:",
        "UNEXPECTED_GREEN"
        if failures == 0
        else "UNEXPECTED_FAILURE",
    )

raise SystemExit(0 if failures == 0 else 1)